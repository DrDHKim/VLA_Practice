#!/usr/bin/env bash
set -euo pipefail

WINE_BIN="${WINE_BIN:-/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine}"
BOTTLE="${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}"
REPORT_PATH="${REPORT_PATH:-/Volumes/DATASET/vla_drive_carla/closed_loop_report.json}"

PYTHONIOENCODING=utf-8 "$WINE_BIN" --bottle "$BOTTLE" --cx-app 'C:\Python37\python.exe' \
  scripts/eval_carla_closed_loop.py \
  --host "${CARLA_HOST:-127.0.0.1}" \
  --port "${CARLA_PORT:-2000}" \
  --town "${CARLA_TOWN:-Town01}" \
  --weather "${CARLA_WEATHER:-ClearNoon}" \
  --route-count "${ROUTE_COUNT:-5}" \
  --route-seconds "${ROUTE_SECONDS:-8}" \
  --target-speed-mps "${TARGET_SPEED_MPS:-5.0}" \
  --steer-gain "${STEER_GAIN:-1.2}" \
  --speed-kp "${SPEED_KP:-0.35}" \
  --brake-kp "${BRAKE_KP:-0.25}" \
  --spawn-start-index "${SPAWN_START_INDEX:-0}" \
  --report-path "$REPORT_PATH"
