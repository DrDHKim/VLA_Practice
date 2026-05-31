from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset

from vla_drive.data.collate import driving_collate_fn
from vla_drive.data.datasets import JsonlDrivingDataset
from vla_drive.evaluation.open_loop_metrics import (
    average_displacement_error,
    collision_proxy_rate,
    final_displacement_error,
    route_deviation_error,
)
from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer
from vla_drive.models.vla_policy import (
    build_action_token_policy,
    build_dummy_policy,
    build_reasoning_aux_policy,
    build_vlm_policy,
)
from vla_drive.utils.io import ensure_dir


class OpenLoopEvaluator:
    def __init__(
        self,
        checkpoint_path: str | Path,
        metadata_path: str | Path,
        report_path: str | Path,
        batch_size: int = 4,
        image_size: int = 64,
        max_samples: int | None = None,
        device: str = "auto",
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.metadata_path = Path(metadata_path)
        self.report_path = Path(report_path)
        self.batch_size = batch_size
        self.image_size = image_size
        self.max_samples = max_samples
        self.device = _select_device(device)

    def evaluate(self) -> dict:
        checkpoint = torch.load(self.checkpoint_path, map_location=self.device, weights_only=False)
        checkpoint_args = checkpoint.get("args", {})
        stage = checkpoint_args.get("stage", "dummy_overfit")
        waypoint_count = int(checkpoint_args.get("waypoint_count", 8))
        hidden_dim = int(checkpoint_args.get("hidden_dim", 64))
        model, tokenizer = _build_model_for_checkpoint(
            stage=stage,
            checkpoint_args=checkpoint_args,
            checkpoint_path=self.checkpoint_path,
            hidden_dim=hidden_dim,
            waypoint_count=waypoint_count,
            device=self.device,
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        dataset = JsonlDrivingDataset(self.metadata_path)
        if self.max_samples is not None:
            dataset = Subset(dataset, list(range(min(self.max_samples, len(dataset)))))
        loader = DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=0,
            collate_fn=lambda samples: driving_collate_fn(samples, image_size=self.image_size),
        )

        total_samples = 0
        ade_sum = 0.0
        fde_sum = 0.0
        route_deviation_sum = 0.0
        collision_proxy_sum = 0.0
        with torch.no_grad():
            for batch in loader:
                batch = _move_batch(batch, self.device)
                pred = _predict_waypoints(model, batch, stage=stage, tokenizer=tokenizer, device=self.device)
                target = batch["future_waypoints_ego"]
                batch_size = int(target.shape[0])
                total_samples += batch_size
                ade_sum += float(average_displacement_error(pred, target).cpu().item()) * batch_size
                fde_sum += float(final_displacement_error(pred, target).cpu().item()) * batch_size
                route_deviation_sum += float(route_deviation_error(pred, target).cpu().item()) * batch_size
                collision_proxy_sum += float(collision_proxy_rate(pred, target).cpu().item()) * batch_size

        if total_samples == 0:
            raise RuntimeError(f"No samples found: {self.metadata_path}")

        report = {
            "checkpoint_path": str(self.checkpoint_path),
            "stage": stage,
            "reasoning_mode": checkpoint_args.get("reasoning_mode"),
            "metadata_path": str(self.metadata_path),
            "sample_count": total_samples,
            "ade": ade_sum / total_samples,
            "fde": fde_sum / total_samples,
            "route_deviation": route_deviation_sum / total_samples,
            "collision_proxy_rate": collision_proxy_sum / total_samples,
        }
        ensure_dir(self.report_path.parent)
        self.report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print("EVAL_OPEN_LOOP_OK")
        print(json.dumps(report, sort_keys=True))
        return report


class Evaluator(OpenLoopEvaluator):
    """Backward-compatible alias for the current open-loop evaluator."""


def _build_model_for_checkpoint(
    stage: str,
    checkpoint_args: dict,
    checkpoint_path: Path,
    hidden_dim: int,
    waypoint_count: int,
    device: torch.device,
):
    if stage == "action_token":
        tokenizer = TrajectoryActionTokenizer(num_tokens=int(checkpoint_args.get("num_action_tokens", 256)))
        tokenizer_path = checkpoint_args.get("tokenizer_path")
        if tokenizer_path is not None and Path(tokenizer_path).exists():
            tokenizer.load(tokenizer_path)
        else:
            tokenizer.load(checkpoint_path.parent / "tokenizer.json")
        model = build_action_token_policy(
            num_tokens=tokenizer.num_tokens,
            hidden_dim=hidden_dim,
            waypoint_count=waypoint_count,
        ).to(device)
        return model, tokenizer
    if stage == "reasoning_aux":
        model = build_reasoning_aux_policy(
            hidden_dim=hidden_dim,
            waypoint_count=waypoint_count,
            num_reasoning_labels=int(checkpoint_args.get("num_reasoning_labels", 4)),
        ).to(device)
        return model, None
    if stage == "dummy_overfit":
        model = build_dummy_policy(hidden_dim=hidden_dim, waypoint_count=waypoint_count).to(device)
        return model, None
    if stage in {"frozen_vlm", "lora_vlm"}:
        model = build_vlm_policy(
            model_path=checkpoint_args.get("model_path", "data/offline/hf_models/Qwen2.5-VL-3B-Instruct"),
            freeze=stage == "frozen_vlm",
            lora_rank=int(checkpoint_args.get("lora_rank", 8)),
            lora_alpha=int(checkpoint_args.get("lora_alpha", 16)),
            waypoint_count=waypoint_count,
        ).to(device)
        return model, None
    raise ValueError(f"Unsupported checkpoint stage for open-loop evaluator: {stage}")


def _predict_waypoints(
    model,
    batch: dict,
    stage: str,
    tokenizer: TrajectoryActionTokenizer | None,
    device: torch.device,
) -> torch.Tensor:
    if stage == "action_token":
        if tokenizer is None:
            raise RuntimeError("action_token evaluation requires a tokenizer")
        return model.decode_waypoints(batch, tokenizer).to(device)
    return model(batch)["future_waypoints_ego"]


def _select_device(requested: str) -> torch.device:
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(requested)


def _move_batch(batch: dict, device: torch.device) -> dict:
    moved = {}
    for key, value in batch.items():
        if torch.is_tensor(value):
            moved[key] = value.to(device)
        else:
            moved[key] = value
    return moved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate waypoint policy on JSONL open-loop data.")
    parser.add_argument("--mode", default="open_loop", choices=["open_loop"])
    parser.add_argument("--checkpoint-path", type=Path, default=Path("checkpoints/m4_dummy/latest.pt"))
    parser.add_argument("--metadata-path", type=Path, default=Path("/Volumes/DATASET/vla_drive_carla/m1_smoke/metadata.jsonl"))
    parser.add_argument("--report-path", type=Path, default=Path("outputs/reports/open_loop_m4_dummy.json"))
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--image-size", type=int, default=64)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--device", default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OpenLoopEvaluator(
        checkpoint_path=args.checkpoint_path,
        metadata_path=args.metadata_path,
        report_path=args.report_path,
        batch_size=args.batch_size,
        image_size=args.image_size,
        max_samples=args.max_samples,
        device=args.device,
    ).evaluate()


if __name__ == "__main__":
    main()
