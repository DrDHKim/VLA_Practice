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
  --model-path "${MODEL_PATH:-data/offline/hf_models/Qwen2.5-VL-3B-Instruct}"
  --lora-rank "${LORA_RANK:-8}"
  --lora-alpha "${LORA_ALPHA:-16}"
  --num-action-tokens "${NUM_ACTION_TOKENS:-256}"
)

if [[ -n "${TOKENIZER_PATH:-}" ]]; then
  ARGS+=(--tokenizer-path "$TOKENIZER_PATH")
fi

if [[ -n "${RESUME_FROM:-}" ]]; then
  ARGS+=(--resume-from "$RESUME_FROM")
fi

"$PYTHON_BIN" "${ARGS[@]}"
