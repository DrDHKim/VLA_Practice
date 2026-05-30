#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-data/offline}"
LIMIT_GB="${2:-120}"

if [ ! -d "$TARGET_DIR" ]; then
  echo "$TARGET_DIR does not exist."
  exit 0
fi

SIZE_KB="$(du -sk "$TARGET_DIR" | awk '{print $1}')"
LIMIT_KB="$((LIMIT_GB * 1024 * 1024))"
SIZE_GB="$(awk "BEGIN {printf \"%.2f\", $SIZE_KB / 1024 / 1024}")"

echo "$TARGET_DIR uses ${SIZE_GB}GB. Limit: ${LIMIT_GB}GB."

if [ "$SIZE_KB" -gt "$LIMIT_KB" ]; then
  echo "OVER BUDGET"
  exit 1
fi

echo "within budget"

