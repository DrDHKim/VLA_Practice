#!/usr/bin/env bash
set -euo pipefail

WINE_BIN="${WINE_BIN:-/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine}"
BOTTLE="${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}"

PYTHONIOENCODING=utf-8 "$WINE_BIN" --bottle "$BOTTLE" --cx-app 'C:\Python37\python.exe' \
  scripts/backfill_route_waypoints.py \
  --host "${CARLA_HOST:-127.0.0.1}" \
  --port "${CARLA_PORT:-2000}" \
  --timeout "${CARLA_TIMEOUT_SECONDS:-90.0}" \
  --town "${CARLA_TOWN:-current}" \
  --input "${ROUTE_WP_BACKFILL_INPUT:-tmp/m10d_final/metadata_scene_balanced_100.jsonl}" \
  --output "${ROUTE_WP_BACKFILL_OUTPUT:-tmp/m10d_final/metadata_scene_balanced_100_routewp_town01.jsonl}" \
  --route-waypoint-count "${ROUTE_WAYPOINT_COUNT:-10}" \
  --route-waypoint-spacing-m "${ROUTE_WAYPOINT_SPACING_M:-2.0}"
