#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# PID / waypoint-to-control 튜닝 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

CARLA_HOST=127.0.0.1
CARLA_PORT=2000
CARLA_TOWN=Town01
CARLA_WEATHER=ClearNoon
WAIT_FOR_CARLA_SECONDS=420

ROUTE_COUNT=3
ROUTE_SECONDS=8
SPAWN_START_INDEX=0

TARGET_SPEEDS=(4.0 5.0)
STEER_GAINS=(0.9 1.2 1.5)
SPEED_KPS=(0.25 0.35)
BRAKE_KPS=(0.25)

OUT_DIR=/Volumes/DATASET/vla_drive_carla/pid_tuning

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

mkdir -p "$OUT_DIR"
SUMMARY="$OUT_DIR/summary.jsonl"
: > "$SUMMARY"

echo "Starting PID tuning..."
echo "OUT_DIR           : $OUT_DIR"
echo "ROUTE_COUNT       : $ROUTE_COUNT"
echo "ROUTE_SECONDS     : $ROUTE_SECONDS"
echo "SPAWN_START_INDEX : $SPAWN_START_INDEX"
echo

for target_speed in "${TARGET_SPEEDS[@]}"; do
  for steer_gain in "${STEER_GAINS[@]}"; do
    for speed_kp in "${SPEED_KPS[@]}"; do
      for brake_kp in "${BRAKE_KPS[@]}"; do
        label="speed_${target_speed}_steer_${steer_gain}_skp_${speed_kp}_bkp_${brake_kp}"
        report="$OUT_DIR/${label}.json"
        echo "==> $label"
        CARLA_HOST="$CARLA_HOST" \
        CARLA_PORT="$CARLA_PORT" \
        CARLA_TOWN="$CARLA_TOWN" \
        CARLA_WEATHER="$CARLA_WEATHER" \
        ROUTE_COUNT="$ROUTE_COUNT" \
        ROUTE_SECONDS="$ROUTE_SECONDS" \
        TARGET_SPEED_MPS="$target_speed" \
        STEER_GAIN="$steer_gain" \
        SPEED_KP="$speed_kp" \
        BRAKE_KP="$brake_kp" \
        SPAWN_START_INDEX="$SPAWN_START_INDEX" \
        REPORT_PATH="$report" \
          scripts/eval_carla.sh

        .conda/bin/python - "$report" "$SUMMARY" "$label" <<'PY'
import json
import sys
report_path, summary_path, label = sys.argv[1:4]
with open(report_path, "r", encoding="utf-8") as f:
    report = json.load(f)
record = {"label": label, **report["aggregate"]}
with open(summary_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True) + "\n")
print("SUMMARY", json.dumps(record, sort_keys=True))
PY
      done
    done
  done
done

echo
echo "PID tuning summary: $SUMMARY"
