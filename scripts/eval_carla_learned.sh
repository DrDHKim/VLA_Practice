#!/usr/bin/env bash
set -euo pipefail

WINE_BIN="${WINE_BIN:-/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine}"
BOTTLE="${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}"
REPORT_PATH="${REPORT_PATH:-outputs/reports/learned_closed_loop.json}"

PYTHONIOENCODING=utf-8 "$WINE_BIN" --bottle "$BOTTLE" --cx-app 'C:\Python37\python.exe' \
  scripts/eval_carla_learned_closed_loop.py \
  --host "${CARLA_HOST:-127.0.0.1}" \
  --port "${CARLA_PORT:-2000}" \
  --timeout "${CARLA_TIMEOUT_SECONDS:-30.0}" \
  --town "${CARLA_TOWN:-Town01}" \
  --weather "${CARLA_WEATHER:-ClearNoon}" \
  --route-count "${ROUTE_COUNT:-1}" \
  --route-seconds "${ROUTE_SECONDS:-8}" \
  --fps "${LEARNED_EVAL_FPS:-5}" \
  --spawn-start-index "${SPAWN_START_INDEX:-0}" \
  --route-completion-distance-m "${ROUTE_COMPLETION_DISTANCE_M:-40.0}" \
  --route-command "${ROUTE_COMMAND:-lane_follow}" \
  --camera-width "${LEARNED_CAMERA_WIDTH:-320}" \
  --camera-height "${LEARNED_CAMERA_HEIGHT:-180}" \
  --camera-fov "${LEARNED_CAMERA_FOV:-90.0}" \
  --policy-host "${POLICY_SERVER_HOST:-127.0.0.1}" \
  --policy-port "${POLICY_SERVER_PORT:-8765}" \
  --checkpoint-path "${CHECKPOINT_PATH:-}" \
  --report-path "$REPORT_PATH" \
  --artifact-dir "${LEARNED_ARTIFACT_DIR:-outputs/reports/learned_closed_loop_artifacts}" \
  --route-waypoint-count "${ROUTE_WAYPOINT_COUNT:-10}" \
  --route-waypoint-spacing-m "${ROUTE_WAYPOINT_SPACING_M:-2.0}"
