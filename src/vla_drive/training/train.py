from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset

from vla_drive.data.collate import driving_collate_fn
from vla_drive.data.datasets import JsonlDrivingDataset
from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer
from vla_drive.models.vla_policy import build_action_token_policy, build_dummy_policy, build_vlm_policy
from vla_drive.training.losses import action_token_loss, waypoint_prediction_loss
from vla_drive.utils.io import ensure_dir
from vla_drive.utils.logging import get_logger
from vla_drive.utils.seed import seed_everything


LOGGER = get_logger(__name__)


def select_device(requested: str) -> torch.device:
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(requested)


def train(args: argparse.Namespace) -> dict:
    seed_everything(args.seed)
    device = select_device(args.device)

    dataset = JsonlDrivingDataset(args.metadata_path)
    if args.max_samples is not None:
        dataset = Subset(dataset, list(range(min(args.max_samples, len(dataset)))))
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=lambda samples: driving_collate_fn(samples, image_size=args.image_size),
    )
    if len(loader) == 0:
        raise RuntimeError(f"No training samples found: {args.metadata_path}")

    tokenizer: TrajectoryActionTokenizer | None = None
    if args.stage == "action_token":
        tokenizer = _load_or_fit_tokenizer(args, dataset)
        model = build_action_token_policy(
            num_tokens=args.num_action_tokens,
            hidden_dim=args.hidden_dim,
            waypoint_count=args.waypoint_count,
        ).to(device)
    elif args.stage == "dummy_overfit":
        model = build_dummy_policy(hidden_dim=args.hidden_dim, waypoint_count=args.waypoint_count).to(device)
    elif args.stage == "frozen_vlm":
        model = build_vlm_policy(
            model_path=args.model_path,
            freeze=True,
            lora_rank=args.lora_rank,
            lora_alpha=args.lora_alpha,
            waypoint_count=args.waypoint_count,
        ).to(device)
    elif args.stage == "lora_vlm":
        model = build_vlm_policy(
            model_path=args.model_path,
            freeze=False,
            lora_rank=args.lora_rank,
            lora_alpha=args.lora_alpha,
            waypoint_count=args.waypoint_count,
        ).to(device)
    else:
        raise ValueError(f"Unsupported training stage: {args.stage}")

    trainable_params = [p for p in model.parameters() if p.requires_grad]
    LOGGER.info("trainable_params=%d total_params=%d", len(trainable_params), sum(1 for _ in model.parameters()))
    optimizer = torch.optim.AdamW(trainable_params, lr=args.lr, weight_decay=args.weight_decay)
    start_epoch = 0
    global_step = 0
    resume_path = args.resume_from
    if resume_path is not None:
        checkpoint = torch.load(resume_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_epoch = int(checkpoint.get("epoch", -1)) + 1
        global_step = int(checkpoint.get("global_step", 0))
        LOGGER.info("resumed checkpoint=%s start_epoch=%s global_step=%s", resume_path, start_epoch, global_step)

    checkpoint_dir = ensure_dir(args.checkpoint_dir)
    log_dir = ensure_dir(args.log_dir)
    log_path = log_dir / "train_log.jsonl"

    losses: list[float] = []
    optimizer.zero_grad(set_to_none=True)
    log_mode = "a" if args.resume_from is not None and log_path.exists() else "w"
    last_epoch = start_epoch - 1
    with log_path.open(log_mode, encoding="utf-8") as log_file:
        for epoch in range(start_epoch, start_epoch + args.epochs):
            last_epoch = epoch
            model.train()
            epoch_losses: list[float] = []
            for batch_index, batch in enumerate(loader):
                batch = _move_batch(batch, device)
                output = model(batch)
                if args.stage == "action_token" and tokenizer is not None:
                    loss = _action_token_step_loss(output, batch, tokenizer, device)
                else:
                    loss = waypoint_prediction_loss(
                        output["future_waypoints_ego"],
                        batch["future_waypoints_ego"],
                        l1_weight=args.l1_weight,
                        fde_weight=args.fde_weight,
                    )
                (loss / args.grad_accum_steps).backward()
                if (batch_index + 1) % args.grad_accum_steps == 0 or (batch_index + 1) == len(loader):
                    torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)

                loss_value = float(loss.detach().cpu().item())
                losses.append(loss_value)
                epoch_losses.append(loss_value)
                global_step += 1
                if global_step % args.log_every == 0 or global_step == 1:
                    record = {
                        "epoch": epoch,
                        "step": global_step,
                        "loss": loss_value,
                        "lr": optimizer.param_groups[0]["lr"],
                    }
                    log_file.write(json.dumps(record, sort_keys=True) + "\n")
                    log_file.flush()
                    LOGGER.info("epoch=%s step=%s loss=%.6f", epoch, global_step, loss_value)

            epoch_loss = sum(epoch_losses) / max(1, len(epoch_losses))
            _save_checkpoint(checkpoint_dir / f"epoch_{epoch:03d}.pt", model, optimizer, epoch, global_step, epoch_loss, args)

    final_loss = losses[-1]
    initial_loss = losses[0]
    _save_checkpoint(checkpoint_dir / "latest.pt", model, optimizer, last_epoch, global_step, final_loss, args)
    summary = {
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "loss_decreased": final_loss < initial_loss,
        "steps": global_step,
        "checkpoint": str(checkpoint_dir / "latest.pt"),
        "log": str(log_path),
    }
    (log_dir / "train_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print("TRAINING_OK")
    print(json.dumps(summary, sort_keys=True))
    return summary


def _move_batch(batch: dict, device: torch.device) -> dict:
    moved = {}
    for key, value in batch.items():
        if torch.is_tensor(value):
            moved[key] = value.to(device)
        else:
            moved[key] = value
    return moved


def _save_checkpoint(
    path: Path,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    global_step: int,
    loss: float,
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch,
            "global_step": global_step,
            "loss": loss,
            "args": _json_safe_args(args),
        },
        path,
    )


def _load_or_fit_tokenizer(args: argparse.Namespace, dataset) -> TrajectoryActionTokenizer:
    """Load tokenizer from disk or fit on the dataset and save."""
    tokenizer = TrajectoryActionTokenizer(num_tokens=args.num_action_tokens)
    if args.tokenizer_path is not None and Path(args.tokenizer_path).exists():
        tokenizer.load(args.tokenizer_path)
        LOGGER.info("loaded tokenizer from %s (K=%d)", args.tokenizer_path, tokenizer.num_tokens)
    else:
        import numpy as np

        LOGGER.info("fitting tokenizer on %d samples (K=%d)...", len(dataset), args.num_action_tokens)
        trajectories = []
        for sample in dataset:
            trajectories.append(np.array(sample.target.future_waypoints_ego, dtype=np.float32))
        tokenizer.fit(trajectories)
        save_path = Path(args.checkpoint_dir) / "tokenizer.json"
        tokenizer.save(save_path)
        LOGGER.info("tokenizer fitted and saved to %s", save_path)
    return tokenizer


def _action_token_step_loss(
    output: dict,
    batch: dict,
    tokenizer: TrajectoryActionTokenizer,
    device: torch.device,
) -> torch.Tensor:
    """Encode batch waypoints with tokenizer and compute cross-entropy loss."""
    import numpy as np

    logits = output["action_logits"]              # [B, T, K]
    waypoints_np = batch["future_waypoints_ego"].cpu().numpy()  # [B, T, 2]
    token_targets = np.stack([tokenizer.encode(waypoints_np[b]) for b in range(waypoints_np.shape[0])])
    targets = torch.tensor(token_targets, dtype=torch.long, device=device)
    return action_token_loss(logits, targets)


def _json_safe_args(args: argparse.Namespace) -> dict:
    safe = {}
    for key, value in vars(args).items():
        if isinstance(value, Path):
            safe[key] = str(value)
        else:
            safe[key] = value
    return safe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a tiny VLA waypoint policy.")
    parser.add_argument("--stage", default="dummy_overfit", choices=["dummy_overfit", "frozen_vlm", "lora_vlm", "action_token"])
    parser.add_argument("--metadata-path", type=Path, default=Path("/private/tmp/vla_drive_carla/m1_smoke/metadata.jsonl"))
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("checkpoints/m4_dummy"))
    parser.add_argument("--log-dir", type=Path, default=Path("outputs/logs/m4_dummy"))
    parser.add_argument("--resume-from", type=Path, default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--image-size", type=int, default=64)
    parser.add_argument("--waypoint-count", type=int, default=8)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--max-samples", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-accum-steps", type=int, default=1)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--l1-weight", type=float, default=1.0)
    parser.add_argument("--fde-weight", type=float, default=1.0)
    parser.add_argument("--log-every", type=int, default=5)
    parser.add_argument("--model-path", type=str, default="data/offline/hf_models/Qwen2.5-VL-3B-Instruct")
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--num-action-tokens", type=int, default=256)
    parser.add_argument("--tokenizer-path", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train(args)


if __name__ == "__main__":
    main()
