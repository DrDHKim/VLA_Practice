#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# 학습 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

# STAGE 선택:
# - dummy_overfit: 작은 CNN baseline
# - reasoning_aux: waypoint + reasoning auxiliary
# - action_token: trajectory token baseline
# - frozen_vlm: Qwen2.5-VL-3B frozen backbone + waypoint head
# - lora_vlm: Qwen2.5-VL-3B LoRA + waypoint head
STAGE=reasoning_aux
METADATA_PATH=/Volumes/DATASET/vla_drive_carla/mac_scenes/metadata.jsonl
CHECKPOINT_DIR=checkpoints/mac_vla
LOG_DIR=outputs/logs/mac_vla

DEVICE=auto
EPOCHS=30
BATCH_SIZE=8
IMAGE_SIZE=64
MAX_SAMPLES=300
NUM_WORKERS=0
LR=1e-3
WEIGHT_DECAY=0.0
GRAD_ACCUM_STEPS=1
MAX_GRAD_NORM=1.0
L1_WEIGHT=1.0
FDE_WEIGHT=1.0
LOG_EVERY=5

# Early stopping. 빈 값이면 비활성화.
EARLY_STOP_PATIENCE=5
EARLY_STOP_MIN_DELTA=0.001
EARLY_STOP_MIN_EPOCHS=5

REASONING_MODE=fast
REASONING_LOSS_WEIGHT=0.1

# Action-token stage 파라미터
NUM_ACTION_TOKENS=64
TOKENIZER_PATH=

# Full VLM 연결 파라미터 (frozen_vlm / lora_vlm 사용 시)
# Mac에서는 frozen_vlm을 먼저 쓰고, lora_vlm은 rank를 낮게 시작한다.
MODEL_PATH=data/offline/hf_models/Qwen2.5-VL-3B-Instruct
LORA_RANK=2
LORA_ALPHA=4

# 이어 학습할 때만 경로를 넣는다.
# 예: RESUME_FROM=checkpoints/m4_dummy/latest.pt
RESUME_FROM=

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "$METADATA_PATH" ]]; then
  echo "metadata가 없습니다: $METADATA_PATH"
  echo "먼저 01_카를라실행.command로 CARLA를 켠 뒤 scripts/collect_carla_data.py 또는 M1 수집을 실행하세요."
  exit 1
fi

echo "Starting training..."
echo "STAGE          : $STAGE"
echo "METADATA_PATH  : $METADATA_PATH"
echo "CHECKPOINT_DIR : $CHECKPOINT_DIR"
echo "LOG_DIR        : $LOG_DIR"
echo "DEVICE         : $DEVICE"
echo "EPOCHS         : $EPOCHS"
echo "BATCH_SIZE     : $BATCH_SIZE"
echo "IMAGE_SIZE     : $IMAGE_SIZE"
echo "MAX_SAMPLES    : $MAX_SAMPLES"
echo "EARLY_STOP     : ${EARLY_STOP_PATIENCE:-<disabled>}"
echo "MODEL_PATH     : $MODEL_PATH"
echo "LORA_RANK      : $LORA_RANK"
echo "RESUME_FROM    : ${RESUME_FROM:-<none>}"
echo

STAGE="$STAGE" \
METADATA_PATH="$METADATA_PATH" \
CHECKPOINT_DIR="$CHECKPOINT_DIR" \
LOG_DIR="$LOG_DIR" \
DEVICE="$DEVICE" \
EPOCHS="$EPOCHS" \
BATCH_SIZE="$BATCH_SIZE" \
IMAGE_SIZE="$IMAGE_SIZE" \
MAX_SAMPLES="$MAX_SAMPLES" \
NUM_WORKERS="$NUM_WORKERS" \
LR="$LR" \
WEIGHT_DECAY="$WEIGHT_DECAY" \
GRAD_ACCUM_STEPS="$GRAD_ACCUM_STEPS" \
MAX_GRAD_NORM="$MAX_GRAD_NORM" \
L1_WEIGHT="$L1_WEIGHT" \
FDE_WEIGHT="$FDE_WEIGHT" \
LOG_EVERY="$LOG_EVERY" \
MODEL_PATH="$MODEL_PATH" \
LORA_RANK="$LORA_RANK" \
LORA_ALPHA="$LORA_ALPHA" \
NUM_ACTION_TOKENS="$NUM_ACTION_TOKENS" \
TOKENIZER_PATH="$TOKENIZER_PATH" \
REASONING_MODE="$REASONING_MODE" \
REASONING_LOSS_WEIGHT="$REASONING_LOSS_WEIGHT" \
EARLY_STOP_PATIENCE="$EARLY_STOP_PATIENCE" \
EARLY_STOP_MIN_DELTA="$EARLY_STOP_MIN_DELTA" \
EARLY_STOP_MIN_EPOCHS="$EARLY_STOP_MIN_EPOCHS" \
RESUME_FROM="$RESUME_FROM" \
  scripts/train_lora.sh
