#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Closed-loop 평가 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

CARLA_HOST=127.0.0.1
CARLA_PORT=2000
CARLA_TOWN=Town01
CARLA_WEATHER=ClearNoon
WAIT_FOR_CARLA_SECONDS=420

ROUTE_COUNT=5
ROUTE_SECONDS=8
SPAWN_START_INDEX=0

TARGET_SPEED_MPS=5.0
TM_PORT=8000
SPEED_PERCENTAGE_DIFFERENCE=0.0
IGNORE_LIGHTS_PERCENTAGE=100.0
IGNORE_SIGNS_PERCENTAGE=100.0
IGNORE_VEHICLES_PERCENTAGE=100.0
DISTANCE_TO_LEADING_VEHICLE_M=3.0
ROUTE_COMPLETION_DISTANCE_M=40.0

REPORT_PATH=/Volumes/DATASET/vla_drive_carla/closed_loop_report.json

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "Waiting for CARLA server: $CARLA_HOST:$CARLA_PORT"
deadline=$((SECONDS + WAIT_FOR_CARLA_SECONDS))
while ! nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "CARLA server가 열리지 않았습니다: $CARLA_HOST:$CARLA_PORT"
    echo "먼저 launchers/01_카를라실행.command 를 실행하고 충분히 기다리세요."
    exit 1
  fi
  sleep 5
done
echo "CARLA server is ready."

echo "Starting closed-loop evaluation..."
echo "REPORT_PATH       : $REPORT_PATH"
echo "ROUTE_COUNT       : $ROUTE_COUNT"
echo "ROUTE_SECONDS     : $ROUTE_SECONDS"
echo "SPAWN_START_INDEX : $SPAWN_START_INDEX"
echo "TARGET_SPEED_MPS  : $TARGET_SPEED_MPS"
echo "TM_PORT           : $TM_PORT"
echo

CARLA_HOST="$CARLA_HOST" \
CARLA_PORT="$CARLA_PORT" \
CARLA_TOWN="$CARLA_TOWN" \
CARLA_WEATHER="$CARLA_WEATHER" \
ROUTE_COUNT="$ROUTE_COUNT" \
ROUTE_SECONDS="$ROUTE_SECONDS" \
TARGET_SPEED_MPS="$TARGET_SPEED_MPS" \
TM_PORT="$TM_PORT" \
SPEED_PERCENTAGE_DIFFERENCE="$SPEED_PERCENTAGE_DIFFERENCE" \
IGNORE_LIGHTS_PERCENTAGE="$IGNORE_LIGHTS_PERCENTAGE" \
IGNORE_SIGNS_PERCENTAGE="$IGNORE_SIGNS_PERCENTAGE" \
IGNORE_VEHICLES_PERCENTAGE="$IGNORE_VEHICLES_PERCENTAGE" \
DISTANCE_TO_LEADING_VEHICLE_M="$DISTANCE_TO_LEADING_VEHICLE_M" \
ROUTE_COMPLETION_DISTANCE_M="$ROUTE_COMPLETION_DISTANCE_M" \
SPAWN_START_INDEX="$SPAWN_START_INDEX" \
REPORT_PATH="$REPORT_PATH" \
  scripts/eval_carla.sh
