#!/usr/bin/env python
"""AutoVLA LoRA generation SFT (step 2-b).

Trains Qwen2.5-VL-3B (LoRA + trainable embed/lm_head) to GENERATE
"<reasoning> Trajectory: <act_..>..." from camera images + a navigation prompt.

Inputs: the instruction JSONL + codebook produced by build_autovla_dataset.py.
Requires the dataset images (e.g. /Volumes/DATASET) and is heavy — intended for
GPU; on M4 only a tiny --max-samples PoC is feasible.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vla_drive.data.autovla_sft import AutoVLASFTCollator, register_action_tokens
from vla_drive.training.lora import apply_lora


class InstructionDataset(Dataset):
    def __init__(self, path: Path, max_samples: int | None = None) -> None:
        with open(path, "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        self.rows = rows[:max_samples] if max_samples else rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int) -> dict:
        return self.rows[i]


def _build_action_class_weights(rows, tokenizer, vocab_size, power, cap, device):
    """Per-vocab CE weight: inverse-freq (smoothed) on action tokens, 1.0 elsewhere."""
    import numpy as np
    from collections import Counter

    counts = Counter()
    for r in rows:
        counts.update(int(t) for t in r.get("action_token_ids", []))
    if not counts:
        return None
    weights = torch.ones(vocab_size, dtype=torch.float32)
    ids = sorted(counts)
    freqs = np.array([counts[i] for i in ids], dtype=np.float64)
    raw = (1.0 / freqs) ** float(power)
    raw = raw / raw.mean()                       # mean weight ~1
    raw = np.clip(raw, 1.0 / cap, cap)           # bound extremes
    for action_id, w in zip(ids, raw):
        vocab_id = tokenizer.convert_tokens_to_ids(f"<act_{action_id}>")
        if vocab_id is not None and 0 <= vocab_id < vocab_size:
            weights[vocab_id] = float(w)
    return weights.to(device)


def _save_checkpoint(model, processor, codebook_path, output_dir, state, optimizer=None):
    """Save adapter + processor + codebook + training_state (+ optimizer for full resume)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    processor.save_pretrained(str(output_dir))
    (output_dir / "trajectory_codebook.json").write_text(
        Path(codebook_path).read_text(encoding="utf-8"), encoding="utf-8"
    )
    if optimizer is not None:
        torch.save(optimizer.state_dict(), output_dir / "optimizer.pt")
    (output_dir / "training_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def _rotate_milestones(output_dir, keep_last: int) -> None:
    """Keep only the most recent `keep_last` step_* milestone checkpoints."""
    if keep_last <= 0:
        return
    import shutil

    dirs = sorted(output_dir.glob("step_*"))
    for old in dirs[:-keep_last]:
        shutil.rmtree(old, ignore_errors=True)


def _select_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AutoVLA LoRA generation SFT.")
    p.add_argument("--instruction-path", type=Path, required=True)
    p.add_argument("--codebook-path", type=Path, required=True)
    p.add_argument("--num-tokens", type=int, default=256)
    p.add_argument("--model-path", type=Path, default=Path("data/offline/hf_models/Qwen2.5-VL-3B-Instruct"))
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--device", default="auto")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum-steps", type=int, default=4)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--max-grad-norm", type=float, default=1.0)
    p.add_argument("--lora-rank", type=int, default=8)
    p.add_argument("--lora-alpha", type=int, default=16)
    p.add_argument("--image-size", type=int, default=0, help="0=processor default")
    p.add_argument("--max-samples", type=int, default=None)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--log-every", type=int, default=5)
    p.add_argument("--balance-action-loss", type=int, default=1,
                   help="1=inverse-freq 가중으로 정지/전진 다수 토큰 다운웨이트(붕괴 방지)")
    p.add_argument("--action-weight-power", type=float, default=0.5)
    p.add_argument("--action-weight-cap", type=float, default=5.0)
    p.add_argument("--gradient-checkpointing", type=int, default=1, help="활성화 메모리 절감(메모리 빡빡할 때 1)")
    p.add_argument("--save-every", type=int, default=0, help="N step마다 latest 덮어쓰기 저장(0=끝에서만)")
    p.add_argument("--keep-every", type=int, default=0, help="N step마다 별도 보존 체크포인트(step_NNNNNN)")
    p.add_argument("--keep-last", type=int, default=3, help="보존 milestone 최대 개수(회전)")
    p.add_argument("--resume-from", default="", help="체크포인트 dir에서 완전 resume(adapter+optimizer+step)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    device = _select_device(args.device)
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(str(args.model_path), use_fast=True)
    added = register_action_tokens(processor.tokenizer, args.num_tokens)

    # fp16 backward on MPS produces NaN; train in fp32 on MPS/CPU, bf16 on CUDA.
    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    model = AutoModelForImageTextToText.from_pretrained(
        str(args.model_path), dtype=dtype, device_map=None, attn_implementation="eager"
    )
    model.resize_token_embeddings(len(processor.tokenizer))
    resume_dir = Path(args.resume_from) if args.resume_from else None
    if resume_dir is not None and resume_dir.exists():
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(resume_dir), is_trainable=True)
        print(json.dumps({"status": "RESUME_ADAPTER", "from": str(resume_dir)}), flush=True)
    else:
        model = apply_lora(model, rank=args.lora_rank, alpha=args.lora_alpha,
                           modules_to_save=["embed_tokens", "lm_head"])
    if args.gradient_checkpointing:
        # cut activation memory (big on a 3B VLM); needed to fit weighted CE on M4.
        model.config.use_cache = False
        model.gradient_checkpointing_enable()
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
    model = model.to(device)
    model.train()
    print(json.dumps({"status": "AUTOVLA_LORA_INIT", "added_action_tokens": added,
                      "device": str(device), "vocab": len(processor.tokenizer)}), flush=True)

    dataset = InstructionDataset(args.instruction_path, args.max_samples)
    if len(dataset) == 0:
        raise RuntimeError(f"No instruction samples: {args.instruction_path}")
    image_size = args.image_size if args.image_size > 0 else None
    collator = AutoVLASFTCollator(processor, image_size=image_size)

    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=args.lr)

    # Full resume: restore optimizer + epoch/step position.
    start_epoch, resume_skip, global_step = 0, 0, 0
    if resume_dir is not None and (resume_dir / "training_state.json").exists():
        st = json.loads((resume_dir / "training_state.json").read_text(encoding="utf-8"))
        global_step = int(st.get("step", 0))
        start_epoch = max(0, int(st.get("epoch", 1)) - 1)   # epoch is 1-indexed in state
        resume_skip = int(st.get("step_in_epoch", 0))       # batches done in that epoch
        opt_path = resume_dir / "optimizer.pt"
        if opt_path.exists():
            optimizer.load_state_dict(torch.load(opt_path, map_location=device))
        print(json.dumps({"status": "RESUME_STATE", "start_epoch": start_epoch + 1,
                          "global_step": global_step, "skip_in_epoch": resume_skip}), flush=True)

    # Inverse-frequency class weights on action tokens to fight majority collapse
    # (stop/forward dominate; rare turn tokens get up-weighted). None = uniform CE.
    class_weights = None
    if args.balance_action_loss:
        class_weights = _build_action_class_weights(
            dataset.rows, processor.tokenizer, len(processor.tokenizer),
            power=args.action_weight_power, cap=args.action_weight_cap, device=device,
        )
        print(json.dumps({"status": "ACTION_LOSS_WEIGHTS", "power": args.action_weight_power,
                          "cap": args.action_weight_cap}), flush=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.output_dir / "train_log.jsonl"
    losses: list[float] = []
    log_mode = "a" if (resume_dir is not None and log_path.exists()) else "w"
    with log_path.open(log_mode, encoding="utf-8") as log_file:
        for epoch in range(start_epoch, args.epochs):
            # per-epoch seeded shuffle → reproducible order so resume can skip done batches.
            generator = torch.Generator().manual_seed(args.seed + epoch)
            loader = DataLoader(
                dataset, batch_size=args.batch_size, shuffle=True, generator=generator,
                num_workers=args.num_workers, collate_fn=collator,
            )
            skip = resume_skip if epoch == start_epoch else 0
            optimizer.zero_grad(set_to_none=True)
            for i, batch in enumerate(loader):
                if i < skip:
                    continue
                if batch is None:  # collator dropped all samples (images unreadable)
                    continue
                batch = {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in batch.items()}
                if class_weights is not None:
                    labels = batch.pop("labels")
                    logits = model(**batch).logits
                    shift_logits = logits[:, :-1, :].contiguous()
                    shift_labels = labels[:, 1:].contiguous()
                    loss = torch.nn.functional.cross_entropy(
                        shift_logits.view(-1, shift_logits.size(-1)),
                        shift_labels.view(-1),
                        weight=class_weights, ignore_index=-100,
                    ) / args.grad_accum_steps
                else:
                    loss = model(**batch).loss / args.grad_accum_steps
                loss.backward()
                if (i + 1) % args.grad_accum_steps == 0:
                    torch.nn.utils.clip_grad_norm_(trainable, args.max_grad_norm)
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                step_loss = float(loss.item()) * args.grad_accum_steps
                losses.append(step_loss)
                global_step += 1
                if global_step % args.log_every == 0:
                    rec = {"epoch": epoch + 1, "epochs": args.epochs, "step": global_step, "loss": step_loss}
                    log_file.write(json.dumps(rec) + "\n")
                    log_file.flush()
                    print(json.dumps(rec), flush=True)
                # step_in_epoch = batches consumed in this epoch (for mid-epoch resume).
                state = {"status": "checkpoint", "epoch": epoch + 1, "epochs": args.epochs,
                         "step": global_step, "step_in_epoch": i + 1, "loss": step_loss}
                if args.save_every > 0 and global_step % args.save_every == 0:
                    # latest: 자주, 덮어쓰기(안전망) + 옵티마이저(완전 resume)
                    _save_checkpoint(model, processor, args.codebook_path, args.output_dir, state, optimizer)
                    print(json.dumps({"status": "CHECKPOINT_LATEST", "step": global_step}), flush=True)
                if args.keep_every > 0 and global_step % args.keep_every == 0:
                    # milestone: 가끔, 별도 보존(step_NNNNNN), keep_last로 회전
                    keep_dir = args.output_dir / ("step_%06d" % global_step)
                    _save_checkpoint(model, processor, args.codebook_path, keep_dir, state, optimizer)
                    _rotate_milestones(args.output_dir, args.keep_last)
                    print(json.dumps({"status": "CHECKPOINT_KEPT", "step": global_step, "dir": str(keep_dir)}), flush=True)
            resume_skip = 0  # only the first resumed epoch skips

    summary = {
        "status": "AUTOVLA_LORA_OK",
        "output_dir": str(args.output_dir),
        "steps": global_step,
        "final_loss": losses[-1] if losses else None,
        "best_loss": min(losses) if losses else None,
    }
    _save_checkpoint(model, processor, args.codebook_path, args.output_dir, summary, optimizer)
    (args.output_dir / "train_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
