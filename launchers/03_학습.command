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
STAGE="${STAGE:-frozen_vlm}"
RAW_METADATA_PATH="${RAW_METADATA_PATH:-tmp/m10d_final/metadata_scene_balanced_100.jsonl}"
# routewp(route_waypoints_ego 입력)는 경량 백본(reasoning_aux/action_token)에서만 쓴다.
# frozen_vlm/lora_vlm은 route_waypoints/reasoning head를 안 쓰고, 명령을 프롬프트 텍스트로 받는다.
USE_ROUTE_WAYPOINTS="${USE_ROUTE_WAYPOINTS:-0}"

# VLM 백본에 카메라당 넣을 프레임 수. M4 절충: 1=AutoVLA 3카메라 현재프레임만(3장).
# 4=3캠×4프레임=12장(정석이지만 M4에선 ~12배 느림). 경량 백본 스테이지에선 무시됨.
VLM_FRAMES_PER_CAMERA="${VLM_FRAMES_PER_CAMERA:-1}"

case "$STAGE" in
  frozen_vlm|lora_vlm)
    # Qwen2.5-VL-3B 백본. M4에선 연산이 벽이라 샘플 축소 + 시간축 1프레임으로 운용.
    USE_ROUTE_WAYPOINTS=0
    METADATA_PATH="${METADATA_PATH:-$RAW_METADATA_PATH}"
    CHECKPOINT_DIR="${CHECKPOINT_DIR:-checkpoints/m10d_final_${STAGE}}"
    LOG_DIR="${LOG_DIR:-outputs/logs/m10d_final_${STAGE}}"
    EPOCHS="${EPOCHS:-3}"
    BATCH_SIZE="${BATCH_SIZE:-4}"
    MAX_SAMPLES="${MAX_SAMPLES:-1500}"
    LR="${LR:-5e-4}"
    ;;
  *)
    if [[ "$USE_ROUTE_WAYPOINTS" == "1" ]]; then
      METADATA_PATH="${METADATA_PATH:-tmp/m10d_final/metadata_scene_balanced_100_routewp_town01.jsonl}"
      CHECKPOINT_DIR="${CHECKPOINT_DIR:-checkpoints/m10d_final_routewp_reasoning_aux_balanced}"
      LOG_DIR="${LOG_DIR:-outputs/logs/m10d_final_routewp_reasoning_aux_balanced}"
    else
      METADATA_PATH="${METADATA_PATH:-$RAW_METADATA_PATH}"
      CHECKPOINT_DIR="${CHECKPOINT_DIR:-checkpoints/m10d_final_reasoning_aux_balanced}"
      LOG_DIR="${LOG_DIR:-outputs/logs/m10d_final_reasoning_aux_balanced}"
    fi
    EPOCHS="${EPOCHS:-8}"
    BATCH_SIZE="${BATCH_SIZE:-64}"
    MAX_SAMPLES="${MAX_SAMPLES:-10000}"
    LR="${LR:-5e-4}"
    ;;
esac

DEVICE="${DEVICE:-auto}"
IMAGE_SIZE="${IMAGE_SIZE:-64}"
NUM_WORKERS="${NUM_WORKERS:-2}"
WEIGHT_DECAY="${WEIGHT_DECAY:-0.0}"
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-1}"
MAX_GRAD_NORM="${MAX_GRAD_NORM:-1.0}"
L1_WEIGHT="${L1_WEIGHT:-1.0}"
FDE_WEIGHT="${FDE_WEIGHT:-1.0}"
LOG_EVERY="${LOG_EVERY:-10}"

# Early stopping. 빈 값이면 비활성화.
EARLY_STOP_PATIENCE="${EARLY_STOP_PATIENCE:-3}"
EARLY_STOP_MIN_DELTA="${EARLY_STOP_MIN_DELTA:-0.001}"
EARLY_STOP_MIN_EPOCHS="${EARLY_STOP_MIN_EPOCHS:-5}"

REASONING_MODE="${REASONING_MODE:-fast}"
REASONING_LOSS_WEIGHT="${REASONING_LOSS_WEIGHT:-0.1}"
BACKFILL_ROUTE_WAYPOINTS="${BACKFILL_ROUTE_WAYPOINTS:-1}"
BACKFILL_CARLA_TOWN="${BACKFILL_CARLA_TOWN:-Town01}"
CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
CARLA_PORT="${CARLA_PORT:-2000}"
WAIT_FOR_CARLA_SECONDS="${WAIT_FOR_CARLA_SECONDS:-420}"
CARLA_TIMEOUT_SECONDS="${CARLA_TIMEOUT_SECONDS:-90.0}"

# Action-token stage 파라미터
NUM_ACTION_TOKENS="${NUM_ACTION_TOKENS:-64}"
TOKENIZER_PATH="${TOKENIZER_PATH:-}"

# Full VLM 연결 파라미터 (frozen_vlm / lora_vlm 사용 시)
# Mac에서는 frozen_vlm을 먼저 쓰고, lora_vlm은 rank를 낮게 시작한다.
MODEL_PATH="${MODEL_PATH:-data/offline/hf_models/Qwen2.5-VL-3B-Instruct}"
LORA_RANK="${LORA_RANK:-2}"
LORA_ALPHA="${LORA_ALPHA:-4}"

# 이어 학습할 때만 경로를 넣는다.
# 예: RESUME_FROM=checkpoints/m4_dummy/latest.pt
RESUME_FROM="${RESUME_FROM:-}"

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

ROUTE_WP_BACKFILL_NEEDED=0
if [[ "$USE_ROUTE_WAYPOINTS" == "1" && "$BACKFILL_ROUTE_WAYPOINTS" == "1" && -f "$RAW_METADATA_PATH" ]]; then
  if [[ ! -f "$METADATA_PATH" ]]; then
    ROUTE_WP_BACKFILL_NEEDED=1
  elif ! .conda/bin/python - "$METADATA_PATH" "$BACKFILL_CARLA_TOWN" <<'PY'
import json
import sys

path, expected_town = sys.argv[1], sys.argv[2]
if expected_town.lower() in {"current", "none"}:
    raise SystemExit(0)

with open(path, "r", encoding="utf-8") as src:
    for line in src:
        if not line.strip():
            continue
        source = (json.loads(line).get("observation") or {}).get("route_waypoint_source") or {}
        source_town = str(source.get("town") or "")
        source_map = str(source.get("map_name") or "")
        ok = expected_town.lower() == source_town.lower() or expected_town.lower() in source_map.lower()
        raise SystemExit(0 if ok else 1)
raise SystemExit(1)
PY
  then
    STALE_METADATA_PATH="${METADATA_PATH}.bad_map_$(date +%Y%m%d_%H%M%S)"
    echo "route waypoint metadata의 source map이 $BACKFILL_CARLA_TOWN 이 아닙니다."
    echo "기존 파일을 격리하고 다시 backfill합니다: $STALE_METADATA_PATH"
    mv "$METADATA_PATH" "$STALE_METADATA_PATH"
    ROUTE_WP_BACKFILL_NEEDED=1
  fi
fi

if [[ "$USE_ROUTE_WAYPOINTS" == "1" && "$BACKFILL_ROUTE_WAYPOINTS" == "1" && "$ROUTE_WP_BACKFILL_NEEDED" == "1" && -f "$RAW_METADATA_PATH" ]]; then
  echo "route waypoint metadata를 $BACKFILL_CARLA_TOWN map 기준으로 backfill합니다."
  echo "RAW_METADATA_PATH : $RAW_METADATA_PATH"
  echo "METADATA_PATH     : $METADATA_PATH"
  echo "BACKFILL_TOWN     : $BACKFILL_CARLA_TOWN"
  if nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; then
    echo "CARLA server is already running: $CARLA_HOST:$CARLA_PORT"
  else
    echo "CARLA server is not running. Starting launchers/01_카를라실행.command ..."
    open "$SCRIPT_DIR/01_카를라실행.command"
  fi
  deadline=$((SECONDS + WAIT_FOR_CARLA_SECONDS))
  while ! nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "CARLA server가 열리지 않아 route waypoint backfill을 진행할 수 없습니다: $CARLA_HOST:$CARLA_PORT"
      exit 1
    fi
    sleep 5
  done
  CARLA_HOST="$CARLA_HOST" \
  CARLA_PORT="$CARLA_PORT" \
  CARLA_TIMEOUT_SECONDS="$CARLA_TIMEOUT_SECONDS" \
  CARLA_TOWN="$BACKFILL_CARLA_TOWN" \
  ROUTE_WP_BACKFILL_INPUT="$RAW_METADATA_PATH" \
  ROUTE_WP_BACKFILL_OUTPUT="$METADATA_PATH" \
    scripts/backfill_route_waypoints.sh
fi

if [[ ! -f "$METADATA_PATH" ]]; then
  echo "metadata가 없습니다: $METADATA_PATH"
  echo "RAW_METADATA_PATH=$RAW_METADATA_PATH 에서 backfill할 수 있는 기존 metadata도 확인하세요."
  exit 1
fi

echo "Starting training..."
echo "STAGE          : $STAGE"
echo "METADATA_PATH  : $METADATA_PATH"
echo "RAW_METADATA   : $RAW_METADATA_PATH"
echo "CHECKPOINT_DIR : $CHECKPOINT_DIR"
echo "LOG_DIR        : $LOG_DIR"
echo "DEVICE         : $DEVICE"
echo "EPOCHS         : $EPOCHS"
echo "BATCH_SIZE     : $BATCH_SIZE"
echo "NUM_WORKERS    : $NUM_WORKERS"
echo "IMAGE_SIZE     : $IMAGE_SIZE"
echo "MAX_SAMPLES    : $MAX_SAMPLES"
echo "LOG_EVERY      : $LOG_EVERY"
echo "EARLY_STOP     : ${EARLY_STOP_PATIENCE:-<disabled>}"
echo "MODEL_PATH     : $MODEL_PATH"
echo "LORA_RANK      : $LORA_RANK"
echo "RESUME_FROM    : ${RESUME_FROM:-<none>}"
echo "ROUTE_WP_INPUT : $USE_ROUTE_WAYPOINTS"
echo "VLM_FRAMES/CAM : $VLM_FRAMES_PER_CAMERA"
echo

STAGE="$STAGE" \
METADATA_PATH="$METADATA_PATH" \
CHECKPOINT_DIR="$CHECKPOINT_DIR" \
LOG_DIR="$LOG_DIR" \
DEVICE="$DEVICE" \
EPOCHS="$EPOCHS" \
BATCH_SIZE="$BATCH_SIZE" \
IMAGE_SIZE="$IMAGE_SIZE" \
VLM_FRAMES_PER_CAMERA="$VLM_FRAMES_PER_CAMERA" \
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
USE_ROUTE_WAYPOINTS="$USE_ROUTE_WAYPOINTS" \
EARLY_STOP_PATIENCE="$EARLY_STOP_PATIENCE" \
EARLY_STOP_MIN_DELTA="$EARLY_STOP_MIN_DELTA" \
EARLY_STOP_MIN_EPOCHS="$EARLY_STOP_MIN_EPOCHS" \
RESUME_FROM="$RESUME_FROM" \
  scripts/train_lora.sh
