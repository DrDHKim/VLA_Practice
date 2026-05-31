#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.conda/bin/python}"
METADATA_PATH="${METADATA_PATH:-/private/tmp/vla_drive_carla/m1_smoke/metadata.jsonl}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-checkpoints/m4_dummy}"
LOG_DIR="${LOG_DIR:-outputs/logs/m4_dummy}"

ARGS=(
  -m vla_drive.training.train
  --stage "${STAGE:-dummy_overfit}"
  --metadata-path "$METADATA_PATH"
  --checkpoint-dir "$CHECKPOINT_DIR"
  --log-dir "$LOG_DIR"
  --epochs "${EPOCHS:-20}"
  --batch-size "${BATCH_SIZE:-2}"
  --image-size "${IMAGE_SIZE:-64}"
  --max-samples "${MAX_SAMPLES:-10}"
  --device "${DEVICE:-auto}"
)

if [[ -n "${RESUME_FROM:-}" ]]; then
  ARGS+=(--resume-from "$RESUME_FROM")
fi

"$PYTHON_BIN" "${ARGS[@]}"
