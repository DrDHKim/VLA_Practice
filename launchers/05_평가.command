#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# 평가 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

EVAL_MODE="${EVAL_MODE:-open_loop}"

# Open-loop 평가
CHECKPOINT_PATH="${CHECKPOINT_PATH:-checkpoints/m10d_final_reasoning_aux_balanced/latest.pt}"
METADATA_PATH="${METADATA_PATH:-tmp/m10d_final/metadata_scene_balanced_100.jsonl}"
OPEN_LOOP_REPORT_PATH="${OPEN_LOOP_REPORT_PATH:-outputs/reports/m10d_final_reasoning_aux_balanced_open_loop.json}"
OPEN_LOOP_BATCH_SIZE="${OPEN_LOOP_BATCH_SIZE:-32}"
OPEN_LOOP_IMAGE_SIZE="${OPEN_LOOP_IMAGE_SIZE:-64}"
OPEN_LOOP_MAX_SAMPLES="${OPEN_LOOP_MAX_SAMPLES:-10000}"
DEVICE="${DEVICE:-auto}"

# Closed-loop 평가
CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
CARLA_PORT="${CARLA_PORT:-2000}"
CARLA_TOWN="${CARLA_TOWN:-Town01}"
CARLA_WEATHER="${CARLA_WEATHER:-ClearNoon}"
WAIT_FOR_CARLA_SECONDS="${WAIT_FOR_CARLA_SECONDS:-420}"
CARLA_TIMEOUT_SECONDS="${CARLA_TIMEOUT_SECONDS:-30.0}"

ROUTE_COUNT="${ROUTE_COUNT:-5}"
ROUTE_SECONDS="${ROUTE_SECONDS:-8}"
SPAWN_START_INDEX="${SPAWN_START_INDEX:-0}"

TARGET_SPEED_MPS="${TARGET_SPEED_MPS:-5.0}"
TM_PORT="${TM_PORT:-8000}"
SPEED_PERCENTAGE_DIFFERENCE="${SPEED_PERCENTAGE_DIFFERENCE:-0.0}"
IGNORE_LIGHTS_PERCENTAGE="${IGNORE_LIGHTS_PERCENTAGE:-100.0}"
IGNORE_SIGNS_PERCENTAGE="${IGNORE_SIGNS_PERCENTAGE:-100.0}"
IGNORE_VEHICLES_PERCENTAGE="${IGNORE_VEHICLES_PERCENTAGE:-100.0}"
DISTANCE_TO_LEADING_VEHICLE_M="${DISTANCE_TO_LEADING_VEHICLE_M:-3.0}"
ROUTE_COMPLETION_DISTANCE_M="${ROUTE_COMPLETION_DISTANCE_M:-40.0}"

CLOSED_LOOP_REPORT_PATH="${CLOSED_LOOP_REPORT_PATH:-/Volumes/DATASET/vla_drive_carla/closed_loop_report.json}"

# Learned-policy closed-loop 평가
POLICY_SERVER_HOST="${POLICY_SERVER_HOST:-127.0.0.1}"
POLICY_SERVER_PORT="${POLICY_SERVER_PORT:-8765}"
LEARNED_RUN_ID="${LEARNED_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
LEARNED_RUN_DIR="${LEARNED_RUN_DIR:-outputs/reports/learned_closed_loop/$LEARNED_RUN_ID}"
LEARNED_CLOSED_LOOP_REPORT_PATH="${LEARNED_CLOSED_LOOP_REPORT_PATH:-$LEARNED_RUN_DIR/report.json}"
LEARNED_ARTIFACT_DIR="${LEARNED_ARTIFACT_DIR:-$LEARNED_RUN_DIR/artifacts}"
LEARNED_VIDEO_PATH="${LEARNED_VIDEO_PATH:-$LEARNED_RUN_DIR/hud.mp4}"
LEARNED_EVAL_FPS="${LEARNED_EVAL_FPS:-5}"
LEARNED_CAMERA_WIDTH="${LEARNED_CAMERA_WIDTH:-320}"
LEARNED_CAMERA_HEIGHT="${LEARNED_CAMERA_HEIGHT:-180}"
LEARNED_CAMERA_FOV="${LEARNED_CAMERA_FOV:-90.0}"
ROUTE_WAYPOINT_COUNT="${ROUTE_WAYPOINT_COUNT:-10}"
ROUTE_WAYPOINT_SPACING_M="${ROUTE_WAYPOINT_SPACING_M:-2.0}"
ROUTE_COMMAND="${ROUTE_COMMAND:-lane_follow}"
POLICY_TARGET_SPEED_MPS="${POLICY_TARGET_SPEED_MPS:-5.0}"
POLICY_STEER_GAIN="${POLICY_STEER_GAIN:-1.6}"
POLICY_SPEED_GAIN="${POLICY_SPEED_GAIN:-0.35}"
POLICY_BRAKE_GAIN="${POLICY_BRAKE_GAIN:-0.45}"
POLICY_LOOKAHEAD_MIN_M="${POLICY_LOOKAHEAD_MIN_M:-2.0}"

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ "$EVAL_MODE" == "open_loop" ]]; then
  if [[ ! -f "$CHECKPOINT_PATH" ]]; then
    echo "checkpoint가 없습니다: $CHECKPOINT_PATH"
    exit 1
  fi
  if [[ ! -f "$METADATA_PATH" ]]; then
    echo "metadata가 없습니다: $METADATA_PATH"
    exit 1
  fi

  echo "Starting open-loop evaluation..."
  echo "CHECKPOINT_PATH : $CHECKPOINT_PATH"
  echo "METADATA_PATH   : $METADATA_PATH"
  echo "REPORT_PATH     : $OPEN_LOOP_REPORT_PATH"
  echo "MAX_SAMPLES     : $OPEN_LOOP_MAX_SAMPLES"
  echo

  CHECKPOINT_PATH="$CHECKPOINT_PATH" \
  METADATA_PATH="$METADATA_PATH" \
  REPORT_PATH="$OPEN_LOOP_REPORT_PATH" \
  BATCH_SIZE="$OPEN_LOOP_BATCH_SIZE" \
  IMAGE_SIZE="$OPEN_LOOP_IMAGE_SIZE" \
  DEVICE="$DEVICE" \
    .conda/bin/python -m vla_drive.evaluation.evaluator \
      --mode open_loop \
      --checkpoint-path "$CHECKPOINT_PATH" \
      --metadata-path "$METADATA_PATH" \
      --report-path "$OPEN_LOOP_REPORT_PATH" \
      --batch-size "$OPEN_LOOP_BATCH_SIZE" \
      --image-size "$OPEN_LOOP_IMAGE_SIZE" \
      --max-samples "$OPEN_LOOP_MAX_SAMPLES" \
      --device "$DEVICE"
  exit 0
fi

if [[ "$EVAL_MODE" != "closed_loop" && "$EVAL_MODE" != "learned_closed_loop" ]]; then
  echo "EVAL_MODE must be open_loop, closed_loop, or learned_closed_loop: $EVAL_MODE"
  exit 1
fi

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

if [[ "$EVAL_MODE" == "learned_closed_loop" ]]; then
  if [[ ! -f "$CHECKPOINT_PATH" ]]; then
    echo "checkpoint가 없습니다: $CHECKPOINT_PATH"
    exit 1
  fi

  echo "Starting learned-policy inference server..."
  echo "CHECKPOINT_PATH : $CHECKPOINT_PATH"
  echo "POLICY_SERVER   : $POLICY_SERVER_HOST:$POLICY_SERVER_PORT"
  echo "ROUTE_COMMAND   : $ROUTE_COMMAND"
  echo "REPORT_PATH     : $LEARNED_CLOSED_LOOP_REPORT_PATH"
  echo "ARTIFACT_DIR    : $LEARNED_ARTIFACT_DIR"
  echo "VIDEO_PATH      : $LEARNED_VIDEO_PATH"
  echo "RUN_DIR         : $LEARNED_RUN_DIR"
  echo

  mkdir -p "$LEARNED_RUN_DIR"
  POLICY_SERVER_LOG="$LEARNED_RUN_DIR/policy_server.log"
  LEARNED_EVAL_LOG="$LEARNED_RUN_DIR/eval.log"
  LEARNED_RENDER_LOG="$LEARNED_RUN_DIR/render.log"
  LEARNED_RUN_METADATA="$LEARNED_RUN_DIR/run_metadata.json"
  cat > "$LEARNED_RUN_METADATA" <<EOF
{
  "run_id": "$LEARNED_RUN_ID",
  "eval_mode": "$EVAL_MODE",
  "checkpoint_path": "$CHECKPOINT_PATH",
  "carla_host": "$CARLA_HOST",
  "carla_port": "$CARLA_PORT",
  "carla_town": "$CARLA_TOWN",
  "carla_weather": "$CARLA_WEATHER",
  "route_count": $ROUTE_COUNT,
  "route_seconds": $ROUTE_SECONDS,
  "route_command": "$ROUTE_COMMAND",
  "learned_eval_fps": $LEARNED_EVAL_FPS,
  "report_path": "$LEARNED_CLOSED_LOOP_REPORT_PATH",
  "artifact_dir": "$LEARNED_ARTIFACT_DIR",
  "video_path": "$LEARNED_VIDEO_PATH",
  "policy_server_log": "$POLICY_SERVER_LOG",
  "eval_log": "$LEARNED_EVAL_LOG",
  "render_log": "$LEARNED_RENDER_LOG"
}
EOF
  MPLCONFIGDIR=.matplotlib_cache .conda/bin/python scripts/serve_policy_inference.py \
    --checkpoint-path "$CHECKPOINT_PATH" \
    --host "$POLICY_SERVER_HOST" \
    --port "$POLICY_SERVER_PORT" \
    --device "$DEVICE" \
    --image-size "$OPEN_LOOP_IMAGE_SIZE" \
    --target-speed-mps "$POLICY_TARGET_SPEED_MPS" \
    --lookahead-min-m "$POLICY_LOOKAHEAD_MIN_M" \
    --steer-gain "$POLICY_STEER_GAIN" \
    --speed-gain "$POLICY_SPEED_GAIN" \
    --brake-gain "$POLICY_BRAKE_GAIN" \
    > "$POLICY_SERVER_LOG" 2>&1 &
  POLICY_SERVER_PID=$!
  cleanup_policy_server() {
    kill "$POLICY_SERVER_PID" 2>/dev/null || true
  }
  trap cleanup_policy_server EXIT

  deadline=$((SECONDS + 120))
  while ! nc -z "$POLICY_SERVER_HOST" "$POLICY_SERVER_PORT" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "policy inference server가 열리지 않았습니다: $POLICY_SERVER_HOST:$POLICY_SERVER_PORT"
      cat "$POLICY_SERVER_LOG" || true
      exit 1
    fi
    sleep 1
  done
  echo "Policy inference server is ready."

  CARLA_HOST="$CARLA_HOST" \
  CARLA_PORT="$CARLA_PORT" \
  CARLA_TOWN="$CARLA_TOWN" \
  CARLA_WEATHER="$CARLA_WEATHER" \
  CARLA_TIMEOUT_SECONDS="$CARLA_TIMEOUT_SECONDS" \
  ROUTE_COUNT="$ROUTE_COUNT" \
  ROUTE_SECONDS="$ROUTE_SECONDS" \
  ROUTE_COMPLETION_DISTANCE_M="$ROUTE_COMPLETION_DISTANCE_M" \
  SPAWN_START_INDEX="$SPAWN_START_INDEX" \
  ROUTE_COMMAND="$ROUTE_COMMAND" \
  LEARNED_EVAL_FPS="$LEARNED_EVAL_FPS" \
  LEARNED_CAMERA_WIDTH="$LEARNED_CAMERA_WIDTH" \
  LEARNED_CAMERA_HEIGHT="$LEARNED_CAMERA_HEIGHT" \
  LEARNED_CAMERA_FOV="$LEARNED_CAMERA_FOV" \
  LEARNED_ARTIFACT_DIR="$LEARNED_ARTIFACT_DIR" \
  ROUTE_WAYPOINT_COUNT="$ROUTE_WAYPOINT_COUNT" \
  ROUTE_WAYPOINT_SPACING_M="$ROUTE_WAYPOINT_SPACING_M" \
  POLICY_SERVER_HOST="$POLICY_SERVER_HOST" \
  POLICY_SERVER_PORT="$POLICY_SERVER_PORT" \
  CHECKPOINT_PATH="$CHECKPOINT_PATH" \
  REPORT_PATH="$LEARNED_CLOSED_LOOP_REPORT_PATH" \
    scripts/eval_carla_learned.sh | tee "$LEARNED_EVAL_LOG"

  MPLCONFIGDIR=.matplotlib_cache .conda/bin/python scripts/render_learned_closed_loop_video.py \
    --report-path "$LEARNED_CLOSED_LOOP_REPORT_PATH" \
    --video-path "$LEARNED_VIDEO_PATH" \
    --fps "$LEARNED_EVAL_FPS" | tee "$LEARNED_RENDER_LOG"
  exit 0
fi

echo "Starting closed-loop evaluation..."
echo "REPORT_PATH       : $CLOSED_LOOP_REPORT_PATH"
echo "ROUTE_COUNT       : $ROUTE_COUNT"
echo "ROUTE_SECONDS     : $ROUTE_SECONDS"
echo "SPAWN_START_INDEX : $SPAWN_START_INDEX"
echo "TARGET_SPEED_MPS  : $TARGET_SPEED_MPS"
echo "TM_PORT           : $TM_PORT"
echo "TIMEOUT_SECONDS   : $CARLA_TIMEOUT_SECONDS"
echo

CARLA_HOST="$CARLA_HOST" \
CARLA_PORT="$CARLA_PORT" \
CARLA_TOWN="$CARLA_TOWN" \
CARLA_WEATHER="$CARLA_WEATHER" \
CARLA_TIMEOUT_SECONDS="$CARLA_TIMEOUT_SECONDS" \
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
REPORT_PATH="$CLOSED_LOOP_REPORT_PATH" \
  scripts/eval_carla.sh
