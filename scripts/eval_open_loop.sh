#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.conda/bin/python}"
CHECKPOINT_PATH="${CHECKPOINT_PATH:-checkpoints/m4_dummy/latest.pt}"
METADATA_PATH="${METADATA_PATH:-/private/tmp/vla_drive_carla/m1_smoke/metadata.jsonl}"
REPORT_PATH="${REPORT_PATH:-outputs/reports/open_loop_m4_dummy.json}"

"$PYTHON_BIN" -m vla_drive.evaluation.evaluator \
  --mode open_loop \
  --checkpoint-path "$CHECKPOINT_PATH" \
  --metadata-path "$METADATA_PATH" \
  --report-path "$REPORT_PATH" \
  --batch-size "${BATCH_SIZE:-4}" \
  --image-size "${IMAGE_SIZE:-64}" \
  --device "${DEVICE:-auto}"
