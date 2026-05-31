#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.conda/bin/python}"
MANIFEST_PATH="${MANIFEST_PATH:-outputs/handoff/5090_manifest.json}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path


repo = Path.cwd()
manifest_path = Path(os.environ.get("MANIFEST_PATH", "outputs/handoff/5090_manifest.json"))


def git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def read_json(path: str) -> dict:
    p = repo / path
    if not p.exists():
        return {"missing": path}
    return json.loads(p.read_text(encoding="utf-8"))


def path_status(path: str) -> dict:
    p = repo / path
    return {
        "path": path,
        "exists": p.exists(),
        "type": "dir" if p.is_dir() else "file" if p.is_file() else "missing",
    }


mac_scale = read_json("outputs/reports/mac_scale_envelope.json")
nuscenes_comparison = read_json("outputs/reports/m9_nuscenes_checkpoint_comparison.json")
mac_carla_vla = read_json("outputs/reports/m10_mac_carla_60s_vla_training_summary.json")
collection = mac_scale.get("collection", {})
closed_loop = mac_scale.get("closed_loop", {})

manifest = {
    "created_on": "2026-05-31",
    "purpose": "RTX 5090 handoff manifest after MacBook smoke, scale envelope, and nuScenes mini path validation.",
    "repo": {
        "root": str(repo),
        "branch": git(["branch", "--show-current"]),
        "commit": git(["rev-parse", "HEAD"]),
        "commit_short": git(["rev-parse", "--short", "HEAD"]),
        "status_short": git(["status", "--short"]).splitlines(),
    },
    "host": {
        "system": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    },
    "macbook_evidence": {
        "scale_envelope_report": "outputs/reports/mac_scale_envelope.json",
        "scale_envelope": {
            "run_count": mac_scale.get("run_count"),
            "successful_count": mac_scale.get("successful_count"),
            "failed_count": mac_scale.get("failed_count"),
            "best_by_ade": mac_scale.get("best_by_ade"),
            "collection_status": collection.get("status"),
            "collection_successful_count": collection.get("successful_count"),
            "closed_loop_status": closed_loop.get("status"),
            "closed_loop_successful_count": closed_loop.get("successful_count"),
        },
        "nuscenes_report": "outputs/reports/m9_nuscenes_checkpoint_comparison.json",
        "nuscenes_delta_tiny_minus_carla": nuscenes_comparison.get("delta_tiny_minus_carla"),
        "mac_carla_vla_report": "outputs/reports/m10_mac_carla_60s_vla_training_summary.json",
        "mac_carla_vla_dataset": mac_carla_vla.get("dataset"),
        "mac_carla_vla_training": {
            key: {
                "steps": value.get("steps"),
                "initial_loss": value.get("initial_loss"),
                "final_loss": value.get("final_loss"),
                "loss_decreased": value.get("loss_decreased"),
            }
            for key, value in mac_carla_vla.get("training", {}).items()
        },
    },
    "resource_gate": {
        "from_machine": "MacBook",
        "to_machine": "RTX 5090",
        "reason_next_machine_required": (
            "MacBook validated the pipeline but remains a smoke-scale environment. "
            "RTX 5090 is for larger CARLA route/weather collection, CUDA LoRA/QLoRA, "
            "higher image sizes, and repeated open/closed-loop evaluation."
        ),
        "do_not_use_h100_yet": (
            "RTX 5090 must first reproduce MacBook-equivalent smoke, then attempt scaling with "
            "batch/image/model/LoRA/quantization reductions before any H100 handoff."
        ),
    },
    "required_paths": [
        path_status("requirements.offline.txt"),
        path_status("data/offline/wheels/linux-x86_64-cu12"),
        path_status("data/offline/hf_models/Qwen2.5-VL-3B-Instruct"),
        path_status("data/offline/datasets/nuscenes/v1.0-mini.tgz"),
        path_status("data/offline/datasets/bench2drive/Bench2Drive-mini"),
        path_status("src/vla_drive/configs/carla_rgb_waypoint.yaml"),
        path_status("src/vla_drive/configs/nuscenes_open_loop.yaml"),
    ],
    "reports": [
        "outputs/reports/mac_scale_envelope.json",
        "outputs/reports/m9_nuscenes_carla_checkpoint_open_loop.json",
        "outputs/reports/m9_nuscenes_tiny_checkpoint_open_loop.json",
        "outputs/reports/m9_nuscenes_checkpoint_comparison.json",
        "outputs/reports/m10_mac_carla_60s_reasoning_aux_open_loop.json",
        "outputs/reports/m10_mac_carla_60s_action_token_open_loop.json",
        "outputs/reports/m10_mac_carla_60s_frozen_vlm_open_loop.json",
        "outputs/reports/m10_mac_carla_60s_lora_vlm_open_loop.json",
        "outputs/reports/m10_mac_carla_60s_vla_training_summary.json",
    ],
    "first_5090_commands": {
        "environment_check": [
            "conda activate vla-drive-5090",
            "python -c \"import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))\"",
            "MPLCONFIGDIR=.matplotlib_cache python -m pytest -m 'not slow'",
        ],
        "carla_collection_smoke": [
            "python scripts/collect_carla_data.py --config src/vla_drive/configs/carla_rgb_waypoint.yaml --output-root /data/vla_drive/carla/e07_5090_smoke"
        ],
        "training_smoke": [
            "STAGE=reasoning_aux METADATA_PATH=/data/vla_drive/carla/e07_5090_smoke/metadata.jsonl EPOCHS=5 MAX_SAMPLES=200 BATCH_SIZE=4 IMAGE_SIZE=128 DEVICE=cuda CHECKPOINT_DIR=checkpoints/e07_5090_reasoning_aux LOG_DIR=outputs/logs/e07_5090_reasoning_aux scripts/train_lora.sh"
        ],
        "lora_smoke": [
            "STAGE=lora_vlm METADATA_PATH=/data/vla_drive/carla/e07_5090_smoke/metadata.jsonl EPOCHS=1 MAX_SAMPLES=64 BATCH_SIZE=1 IMAGE_SIZE=224 DEVICE=cuda CHECKPOINT_DIR=checkpoints/e07_5090_lora LOG_DIR=outputs/logs/e07_5090_lora scripts/train_lora.sh"
        ],
        "open_loop": [
            "CHECKPOINT_PATH=checkpoints/e07_5090_reasoning_aux/latest.pt METADATA_PATH=/data/vla_drive/carla/e07_5090_smoke/metadata.jsonl REPORT_PATH=outputs/reports/e07_5090_open_loop.json BATCH_SIZE=8 IMAGE_SIZE=128 DEVICE=cuda scripts/eval_open_loop.sh"
        ],
        "closed_loop": [
            "CARLA_HOST=127.0.0.1 CARLA_PORT=2000 ROUTE_COUNT=5 ROUTE_SECONDS=20 REPORT_PATH=outputs/reports/e07_5090_closed_loop.json scripts/eval_carla.sh"
        ],
    },
}

manifest_path.parent.mkdir(parents=True, exist_ok=True)
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
print("HANDOFF_MANIFEST_OK")
print(json.dumps({"manifest_path": str(manifest_path), "commit_short": manifest["repo"]["commit_short"]}, sort_keys=True))
PY
