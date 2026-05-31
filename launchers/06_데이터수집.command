#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# CARLA 데이터 수집 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

SCENE_COUNT=3
SECONDS_PER_SCENE=60
FPS=10
IMAGE_WIDTH=320
IMAGE_HEIGHT=180
TARGET_SPEED_MPS=5.0
ROUTE_LENGTH=120
TOWN=Town01
WEATHER=ClearNoon
OUTPUT_ROOT=/Volumes/DATASET/vla_drive_carla/mac_scenes
CONFIG_PATH=src/vla_drive/configs/carla_mac_dataset.yaml
WAIT_FOR_CARLA_SECONDS=420
SCENE_RETRY_COUNT=2
SCENE_RETRY_SLEEP_SECONDS=20

# CrossOver CARLA 설정
CARLA_HOST=127.0.0.1
CARLA_PORT=2000
CARLA_CROSSOVER_BOTTLE=carla-rgb64
SPAWN_SEED_BASE=2601

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if ! nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; then
  echo "CARLA server가 꺼져 있습니다. 01_카를라실행.command를 자동으로 실행합니다..."
  open "$SCRIPT_DIR/01_카를라실행.command"
fi

echo "Waiting for CARLA server: $CARLA_HOST:$CARLA_PORT (최대 ${WAIT_FOR_CARLA_SECONDS}초)"
deadline=$((SECONDS + WAIT_FOR_CARLA_SECONDS))
while ! nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "CARLA server가 열리지 않았습니다: $CARLA_HOST:$CARLA_PORT"
    echo "01_카를라실행.command 창을 확인하세요."
    exit 1
  fi
  sleep 5
done
echo "CARLA server is ready."
echo

SCENE_COUNT="$SCENE_COUNT" \
SECONDS_PER_SCENE="$SECONDS_PER_SCENE" \
FPS="$FPS" \
IMAGE_WIDTH="$IMAGE_WIDTH" \
IMAGE_HEIGHT="$IMAGE_HEIGHT" \
TARGET_SPEED_MPS="$TARGET_SPEED_MPS" \
ROUTE_LENGTH="$ROUTE_LENGTH" \
TOWN="$TOWN" \
WEATHER="$WEATHER" \
OUTPUT_ROOT="$OUTPUT_ROOT" \
CONFIG_PATH="$CONFIG_PATH" \
CARLA_CROSSOVER_BOTTLE="$CARLA_CROSSOVER_BOTTLE" \
SPAWN_SEED_BASE="$SPAWN_SEED_BASE" \
CARLA_HOST="$CARLA_HOST" \
CARLA_PORT="$CARLA_PORT" \
WAIT_FOR_CARLA_SECONDS="$WAIT_FOR_CARLA_SECONDS" \
SCENE_RETRY_COUNT="$SCENE_RETRY_COUNT" \
SCENE_RETRY_SLEEP_SECONDS="$SCENE_RETRY_SLEEP_SECONDS" \
  scripts/collect_carla_scenes.sh
