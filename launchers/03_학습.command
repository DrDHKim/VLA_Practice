#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# 학습 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

STAGE=dummy_overfit
METADATA_PATH=/private/tmp/vla_drive_carla/m1_smoke/metadata.jsonl
CHECKPOINT_DIR=checkpoints/m4_dummy
LOG_DIR=outputs/logs/m4_dummy

DEVICE=auto
EPOCHS=20
BATCH_SIZE=2
IMAGE_SIZE=64
MAX_SAMPLES=10

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
RESUME_FROM="$RESUME_FROM" \
  scripts/train_lora.sh
