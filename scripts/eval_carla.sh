#!/usr/bin/env bash
set -euo pipefail

WINE_BIN="${WINE_BIN:-/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine}"
BOTTLE="${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}"
REPORT_PATH="${REPORT_PATH:-/Volumes/DATASET/vla_drive_carla/closed_loop_report.json}"

PYTHONIOENCODING=utf-8 "$WINE_BIN" --bottle "$BOTTLE" --cx-app 'C:\Python37\python.exe' \
  scripts/eval_carla_closed_loop.py \
  --host "${CARLA_HOST:-127.0.0.1}" \
  --port "${CARLA_PORT:-2000}" \
  --timeout "${CARLA_TIMEOUT_SECONDS:-30.0}" \
  --town "${CARLA_TOWN:-Town01}" \
  --weather "${CARLA_WEATHER:-ClearNoon}" \
  --route-count "${ROUTE_COUNT:-5}" \
  --route-seconds "${ROUTE_SECONDS:-8}" \
  --target-speed-mps "${TARGET_SPEED_MPS:-5.0}" \
  --tm-port "${TM_PORT:-8000}" \
  --speed-percentage-difference "${SPEED_PERCENTAGE_DIFFERENCE:-0.0}" \
  --ignore-lights-percentage "${IGNORE_LIGHTS_PERCENTAGE:-100.0}" \
  --ignore-signs-percentage "${IGNORE_SIGNS_PERCENTAGE:-100.0}" \
  --ignore-vehicles-percentage "${IGNORE_VEHICLES_PERCENTAGE:-100.0}" \
  --distance-to-leading-vehicle-m "${DISTANCE_TO_LEADING_VEHICLE_M:-3.0}" \
  --route-completion-distance-m "${ROUTE_COMPLETION_DISTANCE_M:-40.0}" \
  --spawn-start-index "${SPAWN_START_INDEX:-0}" \
  --report-path "$REPORT_PATH"
