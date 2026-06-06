#!/usr/bin/env python
"""Build an AutoVLA-style instruction dataset for LoRA generation SFT.

Reads CARLA driving metadata (JSONL), fits a trajectory action tokenizer, and
writes one instruction example per sample:

    {sample_id, image_paths, prompt, completion, reasoning, action_token_ids}

The completion is "<reasoning> Trajectory: <act_..>..." which the VLM (LoRA) is
later trained to generate. Also saves the tokenizer codebook and the list of
action special tokens to register in the LM tokenizer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vla_drive.data.autovla_format import action_special_tokens, build_instruction_example
from vla_drive.data.datasets import JsonlDrivingDataset
from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AutoVLA instruction dataset.")
    parser.add_argument("--metadata-path", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--codebook-path", type=Path, default=None)
    parser.add_argument("--special-tokens-path", type=Path, default=None)
    parser.add_argument("--num-tokens", type=int, default=256)
    parser.add_argument("--frames-per-camera", type=int, default=1)
    parser.add_argument("--max-samples", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = JsonlDrivingDataset(args.metadata_path)
    count = len(dataset) if args.max_samples is None else min(args.max_samples, len(dataset))
    if count == 0:
        raise RuntimeError(f"No samples in {args.metadata_path}")

    trajectories = [
        np.asarray(dataset[i].target.future_waypoints_ego, dtype=np.float32) for i in range(count)
    ]
    tokenizer = TrajectoryActionTokenizer(num_tokens=args.num_tokens)
    tokenizer.fit(trajectories)

    codebook_path = args.codebook_path or args.output_path.with_suffix(".codebook.json")
    tokenizer.save(codebook_path)
    special_tokens = action_special_tokens(tokenizer.num_tokens)
    special_tokens_path = args.special_tokens_path or args.output_path.with_suffix(".special_tokens.json")
    special_tokens_path.parent.mkdir(parents=True, exist_ok=True)
    special_tokens_path.write_text(json.dumps(special_tokens), encoding="utf-8")

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.output_path.open("w", encoding="utf-8") as out:
        for i in range(count):
            example = build_instruction_example(
                dataset[i], tokenizer, frames_per_camera=args.frames_per_camera
            )
            out.write(json.dumps(example) + "\n")
            written += 1

    print(
        json.dumps(
            {
                "status": "AUTOVLA_DATASET_OK",
                "output": str(args.output_path),
                "codebook": str(codebook_path),
                "special_tokens": str(special_tokens_path),
                "num_tokens": tokenizer.num_tokens,
                "examples": written,
                "frames_per_camera": args.frames_per_camera,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    # Show one example for inspection.
    print(json.dumps(build_instruction_example(dataset[0], tokenizer, args.frames_per_camera), indent=2)[:1200])


if __name__ == "__main__":
    main()
