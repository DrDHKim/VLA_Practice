#!/usr/bin/env python
"""Quick AutoVLA generation check: load LoRA checkpoint, generate on a real
sample, print the reasoning + action tokens + decoded trajectory vs ground truth.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint-dir", type=Path, default=Path("checkpoints/m10d_autovla_lora"))
    p.add_argument("--base-model", type=Path, default=Path("data/offline/hf_models/Qwen2.5-VL-3B-Instruct"))
    p.add_argument("--codebook-path", type=Path, default=None)
    p.add_argument("--metadata-path", type=Path, default=Path("tmp/m10d_final/metadata_scene_balanced_100.jsonl"))
    p.add_argument("--sample-index", type=int, nargs="+", default=[15, 1500])
    p.add_argument("--image-size", type=int, default=224)
    p.add_argument("--device", default="auto")
    p.add_argument("--max-new-tokens", type=int, default=96)
    args = p.parse_args()

    import torch
    from PIL import Image

    from vla_drive.data.autovla_format import current_frame_image_paths
    from vla_drive.data.datasets import JsonlDrivingDataset
    from vla_drive.models.autovla_generate import generate_trajectory, load_autovla

    if args.device == "auto":
        device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
    else:
        device = torch.device(args.device)

    codebook = args.codebook_path or (args.checkpoint_dir / "trajectory_codebook.json")
    print(f"loading AutoVLA checkpoint {args.checkpoint_dir} on {device} ...", flush=True)
    model, processor, tokenizer = load_autovla(args.checkpoint_dir, args.base_model, codebook, device)

    dataset = JsonlDrivingDataset(args.metadata_path)
    for idx in args.sample_index:
        sample = dataset[idx]
        obs = sample.observation
        paths = current_frame_image_paths(obs, frames_per_camera=1)
        if not all(Path(pp).exists() for pp in paths):
            print(f"\n[skip {idx}] missing image: {paths}", flush=True)
            continue
        images = [Image.open(pp).convert("RGB").resize((args.image_size, args.image_size)) for pp in paths]
        out = generate_trajectory(
            model, processor, tokenizer, images,
            command=obs.route_command, speed_mps=obs.ego_speed_mps,
            device=device, max_new_tokens=args.max_new_tokens,
        )
        gt = np.asarray(sample.target.future_waypoints_ego, dtype=np.float32)
        pred = np.asarray(out["waypoints"], dtype=np.float32)
        print("\n==== sample", idx, "cmd=", obs.route_command, "speed=%.1f" % obs.ego_speed_mps, "====", flush=True)
        print("GENERATED:", out["completion"][:400], flush=True)
        print("n_action_tokens:", len(out["action_token_ids"]), flush=True)
        if pred.shape == gt.shape:
            ade = float(np.mean(np.linalg.norm(pred[:, :2] - gt[:, :2], axis=1)))
            print("pred final xy:", pred[-1, :2].tolist(), " gt final xy:", gt[-1, :2].tolist(), " ADE=%.2f" % ade, flush=True)
        else:
            print("pred shape", pred.shape, "gt shape", gt.shape, flush=True)


if __name__ == "__main__":
    main()
