#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# 사용자 입력값
# 보통 이 블록만 수정하거나, 같은 이름의 환경변수로 override해서 실행한다.
# ============================================================

# 실행 모드: learned_closed_loop | open_loop | closed_loop
EVAL_MODE="${EVAL_MODE:-learned_closed_loop}"

# CARLA server/map. 05 시작 시 이 포트가 닫혀 있으면 01_카를라실행.command를 자동 실행한다.
CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
CARLA_PORT="${CARLA_PORT:-2000}"
CARLA_TOWN="${CARLA_TOWN:-Town01}"
CARLA_WEATHER="${CARLA_WEATHER:-ClearNoon}"
WAIT_FOR_CARLA_SECONDS="${WAIT_FOR_CARLA_SECONDS:-420}"
CARLA_TIMEOUT_SECONDS="${CARLA_TIMEOUT_SECONDS:-600.0}"

# Route/evaluation 범위.
# SPAWN_START_INDEX가 시작 스폰 위치, ROUTE_SECONDS가 평가 시간,
# ROUTE_COMPLETION_DISTANCE_M가 100% completion 기준 목표 거리다.
ROUTE_COUNT="${ROUTE_COUNT:-1}"
ROUTE_SECONDS="${ROUTE_SECONDS:-30}"
SPAWN_START_INDEX="${SPAWN_START_INDEX:-20}"
# SPAWN_GOAL_INDEX를 0 이상으로 주면 CARLA GlobalRoutePlanner가 시작→도착
# 글로벌 루트를 자동 생성하고, 그 루트에서 route-command를 만들어 모델에
# 입력한다. route waypoint는 HUD/분석용이다 (-1이면 기존 차선추종 방식).
# Town01 기준 0->130은 교차로 회전이 섞인 cross-town 루트가 나오도록 잡은 첫 시도값.
# 실행 로그의 GLOBAL_ROUTE_READY route_waypoints 수를 보고 너무 짧/길면 조정한다.
SPAWN_GOAL_INDEX="${SPAWN_GOAL_INDEX:-130}"
ROUTE_SAMPLING_RESOLUTION_M="${ROUTE_SAMPLING_RESOLUTION_M:-2.0}"
# 학습 수집 때 route_command lookahead가 meters=30.0이었으므로 평가도 30m로 맞춘다.
ROUTE_COMMAND_LOOKAHEAD_M="${ROUTE_COMMAND_LOOKAHEAD_M:-30.0}"
ARRIVAL_DISTANCE_M="${ARRIVAL_DISTANCE_M:-5.0}"
ROUTE_COMPLETION_DISTANCE_M="${ROUTE_COMPLETION_DISTANCE_M:-40.0}"
ROUTE_COMMAND="${ROUTE_COMMAND:-lane_follow}"

# Learned-policy checkpoint/input. 기본은 07에서 학습한 AutoVLA LoRA 생성 checkpoint다.
POLICY_TYPE="${POLICY_TYPE:-autovla}"
CHECKPOINT_PATH="${CHECKPOINT_PATH:-checkpoints/m10d_autovla_lora}"
BASE_MODEL_PATH="${BASE_MODEL_PATH:-data/offline/hf_models/Qwen2.5-VL-3B-Instruct}"
AUTOVLA_MAX_NEW_TOKENS="${AUTOVLA_MAX_NEW_TOKENS:-96}"
DEVICE="${DEVICE:-auto}"
OPEN_LOOP_IMAGE_SIZE="${OPEN_LOOP_IMAGE_SIZE:-224}"

# Learned-policy warm-up. Policy 평가 전 직접 throttle을 주고,
# 목표 속도(LEARNED_WARMUP_TARGET_SPEED_MPS) 도달 OR 시간(LEARNED_WARMUP_SECONDS)
# 둘 중 먼저 충족되면 해제하고 현재 속도로 평가를 시작한다.
LEARNED_WARMUP_SECONDS="${LEARNED_WARMUP_SECONDS:-3.0}"
LEARNED_WARMUP_TARGET_SPEED_MPS="${LEARNED_WARMUP_TARGET_SPEED_MPS:-3.0}"
LEARNED_WARMUP_THROTTLE="${LEARNED_WARMUP_THROTTLE:-0.7}"
LEARNED_WARMUP_STEER="${LEARNED_WARMUP_STEER:-0.0}"
LEARNED_WARMUP_BRAKE="${LEARNED_WARMUP_BRAKE:-0.0}"

# Learned-policy control 해석.
POLICY_TARGET_SPEED_MPS="${POLICY_TARGET_SPEED_MPS:-5.0}"
POLICY_HORIZON_SECONDS="${POLICY_HORIZON_SECONDS:-2.0}"
POLICY_STEER_GAIN="${POLICY_STEER_GAIN:-1.6}"
POLICY_SPEED_GAIN="${POLICY_SPEED_GAIN:-0.35}"
POLICY_BRAKE_GAIN="${POLICY_BRAKE_GAIN:-0.45}"
POLICY_LOOKAHEAD_MIN_M="${POLICY_LOOKAHEAD_MIN_M:-2.0}"

# HUD/route waypoint 표시.
LEARNED_EVAL_FPS="${LEARNED_EVAL_FPS:-5}"
LEARNED_SYNCHRONOUS_MODE="${LEARNED_SYNCHRONOUS_MODE:-1}"
LEARNED_FIXED_DELTA_SECONDS="${LEARNED_FIXED_DELTA_SECONDS:-0.2}"
LEARNED_CAMERA_WIDTH="${LEARNED_CAMERA_WIDTH:-320}"
LEARNED_CAMERA_HEIGHT="${LEARNED_CAMERA_HEIGHT:-180}"
LEARNED_CAMERA_FOV="${LEARNED_CAMERA_FOV:-90.0}"
# HUD 영상용 3인칭 체이스 카메라 (표준 게임 뷰: 뒤 7m, 위 3.5m, -15°).
# 모델 입력은 전방 카메라 유지, 영상만 체이스 뷰로 녹화. 0이면 전방 카메라 녹화.
LEARNED_CHASE_CAMERA="${LEARNED_CHASE_CAMERA:-1}"
LEARNED_CHASE_CAMERA_WIDTH="${LEARNED_CHASE_CAMERA_WIDTH:-640}"
LEARNED_CHASE_CAMERA_HEIGHT="${LEARNED_CHASE_CAMERA_HEIGHT:-360}"
LEARNED_CHASE_BACK_M="${LEARNED_CHASE_BACK_M:-7.0}"
LEARNED_CHASE_HEIGHT_M="${LEARNED_CHASE_HEIGHT_M:-3.5}"
LEARNED_CHASE_PITCH_DEG="${LEARNED_CHASE_PITCH_DEG:--15.0}"
ROUTE_WAYPOINT_COUNT="${ROUTE_WAYPOINT_COUNT:-10}"
ROUTE_WAYPOINT_SPACING_M="${ROUTE_WAYPOINT_SPACING_M:-2.0}"

# 출력 폴더. 기본값은 날짜별 run directory다.
LEARNED_RUN_ID="${LEARNED_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
LEARNED_RUN_DIR="${LEARNED_RUN_DIR:-outputs/reports/learned_closed_loop/$LEARNED_RUN_ID}"
LEARNED_CLOSED_LOOP_REPORT_PATH="${LEARNED_CLOSED_LOOP_REPORT_PATH:-$LEARNED_RUN_DIR/report.json}"
LEARNED_ARTIFACT_DIR="${LEARNED_ARTIFACT_DIR:-$LEARNED_RUN_DIR/artifacts}"
LEARNED_VIDEO_PATH="${LEARNED_VIDEO_PATH:-$LEARNED_RUN_DIR/hud.mp4}"

# Open-loop 전용 입력.
METADATA_PATH="${METADATA_PATH:-tmp/m10d_final/metadata_scene_balanced_100.jsonl}"
OPEN_LOOP_REPORT_PATH="${OPEN_LOOP_REPORT_PATH:-outputs/reports/m10d_final_reasoning_aux_balanced_open_loop.json}"
OPEN_LOOP_BATCH_SIZE="${OPEN_LOOP_BATCH_SIZE:-32}"
OPEN_LOOP_MAX_SAMPLES="${OPEN_LOOP_MAX_SAMPLES:-10000}"

# Traffic Manager closed-loop 전용 입력.
TARGET_SPEED_MPS="${TARGET_SPEED_MPS:-5.0}"
TM_PORT="${TM_PORT:-8000}"
SPEED_PERCENTAGE_DIFFERENCE="${SPEED_PERCENTAGE_DIFFERENCE:-0.0}"
IGNORE_LIGHTS_PERCENTAGE="${IGNORE_LIGHTS_PERCENTAGE:-100.0}"
IGNORE_SIGNS_PERCENTAGE="${IGNORE_SIGNS_PERCENTAGE:-100.0}"
IGNORE_VEHICLES_PERCENTAGE="${IGNORE_VEHICLES_PERCENTAGE:-100.0}"
DISTANCE_TO_LEADING_VEHICLE_M="${DISTANCE_TO_LEADING_VEHICLE_M:-3.0}"
CLOSED_LOOP_REPORT_PATH="${CLOSED_LOOP_REPORT_PATH:-/Volumes/DATASET/vla_drive_carla/closed_loop_report.json}"

# 내부 local inference server.
POLICY_SERVER_HOST="${POLICY_SERVER_HOST:-127.0.0.1}"
POLICY_SERVER_PORT="${POLICY_SERVER_PORT:-8765}"
# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ "$EVAL_MODE" == "open_loop" ]]; then
  if [[ "$POLICY_TYPE" == "autovla" ]]; then
    echo "AutoVLA 생성 모델의 open-loop evaluator는 아직 05에 연결되지 않았습니다."
    echo "기본값 EVAL_MODE=learned_closed_loop로 CARLA 평가를 실행하세요."
    exit 1
  fi
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

if nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; then
  echo "CARLA server is already running: $CARLA_HOST:$CARLA_PORT"
else
  echo "CARLA server is not running. Starting launchers/01_카를라실행.command ..."
  open "$SCRIPT_DIR/01_카를라실행.command"
fi

echo "Waiting for CARLA server: $CARLA_HOST:$CARLA_PORT"
deadline=$((SECONDS + WAIT_FOR_CARLA_SECONDS))
while ! nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "CARLA server가 열리지 않았습니다: $CARLA_HOST:$CARLA_PORT"
    echo "launchers/01_카를라실행.command 자동 실행 후에도 timeout이 발생했습니다."
    exit 1
  fi
  sleep 5
done
echo "CARLA server is ready."

if [[ "$EVAL_MODE" == "learned_closed_loop" ]]; then
  if [[ ! -e "$CHECKPOINT_PATH" ]]; then
    echo "checkpoint가 없습니다: $CHECKPOINT_PATH"
    exit 1
  fi
  if [[ "$POLICY_TYPE" == "autovla" ]]; then
    for required in adapter_config.json adapter_model.safetensors trajectory_codebook.json; do
      if [[ ! -f "$CHECKPOINT_PATH/$required" ]]; then
        echo "AutoVLA checkpoint 필수 파일이 없습니다: $CHECKPOINT_PATH/$required"
        exit 1
      fi
    done
    if [[ ! -d "$BASE_MODEL_PATH" ]]; then
      echo "AutoVLA base model이 없습니다: $BASE_MODEL_PATH"
      exit 1
    fi
  fi

  echo "Starting learned-policy inference server..."
  echo "POLICY_TYPE     : $POLICY_TYPE"
  echo "CHECKPOINT_PATH : $CHECKPOINT_PATH"
  echo "BASE_MODEL_PATH : $BASE_MODEL_PATH"
  echo "POLICY_SERVER   : $POLICY_SERVER_HOST:$POLICY_SERVER_PORT"
  echo "ROUTE_COMMAND   : $ROUTE_COMMAND"
  echo "SPAWN_START/GOAL: $SPAWN_START_INDEX -> $SPAWN_GOAL_INDEX"
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
  "policy_type": "$POLICY_TYPE",
  "base_model_path": "$BASE_MODEL_PATH",
  "carla_host": "$CARLA_HOST",
  "carla_port": "$CARLA_PORT",
  "carla_town": "$CARLA_TOWN",
  "carla_weather": "$CARLA_WEATHER",
  "route_count": $ROUTE_COUNT,
  "route_seconds": $ROUTE_SECONDS,
  "route_command": "$ROUTE_COMMAND",
  "learned_eval_fps": $LEARNED_EVAL_FPS,
  "synchronous_mode": $LEARNED_SYNCHRONOUS_MODE,
  "fixed_delta_seconds": $LEARNED_FIXED_DELTA_SECONDS,
  "learned_warmup_max_seconds": $LEARNED_WARMUP_SECONDS,
  "learned_warmup_target_speed_mps": $LEARNED_WARMUP_TARGET_SPEED_MPS,
  "learned_warmup_throttle": $LEARNED_WARMUP_THROTTLE,
  "policy_horizon_seconds": $POLICY_HORIZON_SECONDS,
  "report_path": "$LEARNED_CLOSED_LOOP_REPORT_PATH",
  "artifact_dir": "$LEARNED_ARTIFACT_DIR",
  "video_path": "$LEARNED_VIDEO_PATH",
  "policy_server_log": "$POLICY_SERVER_LOG",
  "eval_log": "$LEARNED_EVAL_LOG",
  "render_log": "$LEARNED_RENDER_LOG"
}
EOF
  # 이전 실행 터미널을 닫지 않아 남아있는 eval 클라이언트(wine python / bash)와
  # policy 서버가 같은 CARLA(2000)·policy 포트(8765)를 동시에 물면, policy 서버는
  # listen(1)로 한 번에 한 연결만 처리하므로 새 클라이언트가 connect 타임아웃으로
  # fatal error가 난다. 새 실행 전에 이전 실행 잔존 프로세스를 모두 정리한다.
  STALE_EVAL_PIDS="$(pgrep -f 'eval_carla_learned(_closed_loop\.py|\.sh)' 2>/dev/null || true)"
  if [[ -n "$STALE_EVAL_PIDS" ]]; then
    echo "이전 eval 클라이언트 정리: $(echo "$STALE_EVAL_PIDS" | tr '\n' ' ')"
    kill $STALE_EVAL_PIDS 2>/dev/null || true
    sleep 1
    STALE_EVAL_PIDS="$(pgrep -f 'eval_carla_learned(_closed_loop\.py|\.sh)' 2>/dev/null || true)"
    [[ -n "$STALE_EVAL_PIDS" ]] && kill -9 $STALE_EVAL_PIDS 2>/dev/null || true
  fi

  # 이전 실행에서 남은 policy 서버가 포트를 점유하면 새 서버 bind가 실패한다.
  # (Address already in use) 시작 전에 점유 프로세스를 정리한다.
  STALE_POLICY_PIDS="$(lsof -ti tcp:"$POLICY_SERVER_PORT" 2>/dev/null || true)"
  if [[ -n "$STALE_POLICY_PIDS" ]]; then
    echo "포트 $POLICY_SERVER_PORT 점유 프로세스 정리: $STALE_POLICY_PIDS"
    kill $STALE_POLICY_PIDS 2>/dev/null || true
    sleep 1
    STALE_POLICY_PIDS="$(lsof -ti tcp:"$POLICY_SERVER_PORT" 2>/dev/null || true)"
    [[ -n "$STALE_POLICY_PIDS" ]] && kill -9 $STALE_POLICY_PIDS 2>/dev/null || true
    sleep 1
  fi

  MPLCONFIGDIR=.matplotlib_cache .conda/bin/python scripts/serve_policy_inference.py \
    --checkpoint-path "$CHECKPOINT_PATH" \
    --policy-type "$POLICY_TYPE" \
    --base-model-path "$BASE_MODEL_PATH" \
    --host "$POLICY_SERVER_HOST" \
    --port "$POLICY_SERVER_PORT" \
    --device "$DEVICE" \
    --image-size "$OPEN_LOOP_IMAGE_SIZE" \
    --target-speed-mps "$POLICY_TARGET_SPEED_MPS" \
    --horizon-seconds "$POLICY_HORIZON_SECONDS" \
    --lookahead-min-m "$POLICY_LOOKAHEAD_MIN_M" \
    --steer-gain "$POLICY_STEER_GAIN" \
    --speed-gain "$POLICY_SPEED_GAIN" \
    --brake-gain "$POLICY_BRAKE_GAIN" \
    --max-new-tokens "$AUTOVLA_MAX_NEW_TOKENS" \
    > "$POLICY_SERVER_LOG" 2>&1 &
  POLICY_SERVER_PID=$!
  cleanup_policy_server() {
    kill "$POLICY_SERVER_PID" 2>/dev/null || true
  }
  trap cleanup_policy_server EXIT

  # 포트 열림만이 아니라 (1) 방금 띄운 서버 프로세스가 살아 있고 (2) 로그에
  # POLICY_SERVER_READY가 찍혔는지 확인한다. 그래야 낡은 서버가 포트를 쥔 채
  # 새 서버가 bind 실패로 죽은 상황을 "ready"로 오인하지 않는다.
  deadline=$((SECONDS + 300))
  until grep -q "POLICY_SERVER_READY" "$POLICY_SERVER_LOG" 2>/dev/null \
        && nc -z "$POLICY_SERVER_HOST" "$POLICY_SERVER_PORT" >/dev/null 2>&1; do
    if ! kill -0 "$POLICY_SERVER_PID" 2>/dev/null; then
      echo "policy inference server가 시작 직후 종료되었습니다 (PID $POLICY_SERVER_PID)."
      cat "$POLICY_SERVER_LOG" || true
      exit 1
    fi
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
  SPAWN_GOAL_INDEX="$SPAWN_GOAL_INDEX" \
  ROUTE_SAMPLING_RESOLUTION_M="$ROUTE_SAMPLING_RESOLUTION_M" \
  ROUTE_COMMAND_LOOKAHEAD_M="$ROUTE_COMMAND_LOOKAHEAD_M" \
  ARRIVAL_DISTANCE_M="$ARRIVAL_DISTANCE_M" \
  ROUTE_COMMAND="$ROUTE_COMMAND" \
  LEARNED_EVAL_FPS="$LEARNED_EVAL_FPS" \
  LEARNED_SYNCHRONOUS_MODE="$LEARNED_SYNCHRONOUS_MODE" \
  LEARNED_FIXED_DELTA_SECONDS="$LEARNED_FIXED_DELTA_SECONDS" \
  LEARNED_CAMERA_WIDTH="$LEARNED_CAMERA_WIDTH" \
  LEARNED_CAMERA_HEIGHT="$LEARNED_CAMERA_HEIGHT" \
  LEARNED_CAMERA_FOV="$LEARNED_CAMERA_FOV" \
  LEARNED_CHASE_CAMERA="$LEARNED_CHASE_CAMERA" \
  LEARNED_CHASE_CAMERA_WIDTH="$LEARNED_CHASE_CAMERA_WIDTH" \
  LEARNED_CHASE_CAMERA_HEIGHT="$LEARNED_CHASE_CAMERA_HEIGHT" \
  LEARNED_CHASE_BACK_M="$LEARNED_CHASE_BACK_M" \
  LEARNED_CHASE_HEIGHT_M="$LEARNED_CHASE_HEIGHT_M" \
  LEARNED_CHASE_PITCH_DEG="$LEARNED_CHASE_PITCH_DEG" \
  LEARNED_WARMUP_SECONDS="$LEARNED_WARMUP_SECONDS" \
  LEARNED_WARMUP_TARGET_SPEED_MPS="$LEARNED_WARMUP_TARGET_SPEED_MPS" \
  LEARNED_WARMUP_THROTTLE="$LEARNED_WARMUP_THROTTLE" \
  LEARNED_WARMUP_STEER="$LEARNED_WARMUP_STEER" \
  LEARNED_WARMUP_BRAKE="$LEARNED_WARMUP_BRAKE" \
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
