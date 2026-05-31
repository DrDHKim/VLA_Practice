#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.conda/bin/python}"
METADATA_PATH="${METADATA_PATH:-/Volumes/DATASET/vla_drive_carla/m1_smoke/metadata.jsonl}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-checkpoints/m4_dummy}"
LOG_DIR="${LOG_DIR:-outputs/logs/m4_dummy}"

ARGS=(
  -m vla_drive.training.train
  --stage "${STAGE:-dummy_overfit}"
  --waypoint-count "${WAYPOINT_COUNT:-10}"
  --waypoint-dim "${WAYPOINT_DIM:-3}"
  --metadata-path "$METADATA_PATH"
  --checkpoint-dir "$CHECKPOINT_DIR"
  --log-dir "$LOG_DIR"
  --epochs "${EPOCHS:-20}"
  --batch-size "${BATCH_SIZE:-2}"
  --num-workers "${NUM_WORKERS:-0}"
  --image-size "${IMAGE_SIZE:-64}"
  --max-samples "${MAX_SAMPLES:-10}"
  --device "${DEVICE:-auto}"
  --lr "${LR:-1e-3}"
  --weight-decay "${WEIGHT_DECAY:-0.0}"
  --grad-accum-steps "${GRAD_ACCUM_STEPS:-1}"
  --max-grad-norm "${MAX_GRAD_NORM:-1.0}"
  --l1-weight "${L1_WEIGHT:-1.0}"
  --fde-weight "${FDE_WEIGHT:-1.0}"
  --log-every "${LOG_EVERY:-5}"
  --model-path "${MODEL_PATH:-data/offline/hf_models/Qwen2.5-VL-3B-Instruct}"
  --lora-rank "${LORA_RANK:-8}"
  --lora-alpha "${LORA_ALPHA:-16}"
  --num-action-tokens "${NUM_ACTION_TOKENS:-256}"
  --reasoning-mode "${REASONING_MODE:-fast}"
  --reasoning-loss-weight "${REASONING_LOSS_WEIGHT:-0.1}"
)

if [[ -n "${NUM_REASONING_LABELS:-}" ]]; then
  ARGS+=(--num-reasoning-labels "$NUM_REASONING_LABELS")
fi

if [[ -n "${EARLY_STOP_PATIENCE:-}" ]]; then
  ARGS+=(
    --early-stop-patience "$EARLY_STOP_PATIENCE"
    --early-stop-min-delta "${EARLY_STOP_MIN_DELTA:-0.0}"
    --early-stop-min-epochs "${EARLY_STOP_MIN_EPOCHS:-1}"
  )
fi

if [[ -n "${TOKENIZER_PATH:-}" ]]; then
  ARGS+=(--tokenizer-path "$TOKENIZER_PATH")
fi

if [[ -n "${RESUME_FROM:-}" ]]; then
  ARGS+=(--resume-from "$RESUME_FROM")
fi

"$PYTHON_BIN" "${ARGS[@]}"
