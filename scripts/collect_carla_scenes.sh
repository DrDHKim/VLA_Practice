#!/usr/bin/env bash
set -euo pipefail

WINE_BIN="${WINE_BIN:-/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine}"
BOTTLE="${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}"
CONFIG_PATH="${CONFIG_PATH:-src/vla_drive/configs/carla_mac_dataset.yaml}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/Volumes/DATASET/vla_drive_carla/mac_scenes}"
SCENE_COUNT="${SCENE_COUNT:-3}"
SECONDS_PER_SCENE="${SECONDS_PER_SCENE:-60}"
FPS="${FPS:-10}"
IMAGE_WIDTH="${IMAGE_WIDTH:-320}"
IMAGE_HEIGHT="${IMAGE_HEIGHT:-180}"
TARGET_SPEED_MPS="${TARGET_SPEED_MPS:-5.0}"
SPEED_CONTROL="${SPEED_CONTROL:-percentage}"
IGNORE_LIGHTS_PERCENTAGE="${IGNORE_LIGHTS_PERCENTAGE:-0.0}"
IGNORE_SIGNS_PERCENTAGE="${IGNORE_SIGNS_PERCENTAGE:-0.0}"
IGNORE_VEHICLES_PERCENTAGE="${IGNORE_VEHICLES_PERCENTAGE:-0.0}"
NPC_VEHICLE_COUNT="${NPC_VEHICLE_COUNT:-20}"
NPC_VEHICLE_FILTER="${NPC_VEHICLE_FILTER:-vehicle.tesla.model3}"
NPC_VEHICLE_TARGET_SPEED_MPS="${NPC_VEHICLE_TARGET_SPEED_MPS:-4.0}"
PEDESTRIAN_COUNT="${PEDESTRIAN_COUNT:-30}"
PEDESTRIAN_CROSS_FACTOR="${PEDESTRIAN_CROSS_FACTOR:-0.7}"
PEDESTRIAN_RUNNING_PERCENTAGE="${PEDESTRIAN_RUNNING_PERCENTAGE:-0.1}"
SYNCHRONOUS_MODE="${SYNCHRONOUS_MODE:-true}"
FIXED_DELTA_SECONDS="${FIXED_DELTA_SECONDS:-0.05}"
ROUTE_LENGTH="${ROUTE_LENGTH:-120}"
CONTROL_MODE="${CONTROL_MODE:-autopilot}"
ROUTE_COMMAND_LOOKAHEAD_MODE="${ROUTE_COMMAND_LOOKAHEAD_MODE:-meters}"
ROUTE_COMMAND_LOOKAHEAD_METERS="${ROUTE_COMMAND_LOOKAHEAD_METERS:-30.0}"
ROUTE_COMMAND_LOOKAHEAD_FRAMES="${ROUTE_COMMAND_LOOKAHEAD_FRAMES:-20}"
ROUTE_COMMAND_YAW_THRESHOLD_RAD="${ROUTE_COMMAND_YAW_THRESHOLD_RAD:-0.35}"
TOWN="${TOWN:-Town01}"
WEATHER="${WEATHER:-ClearNoon}"
SPAWN_SEED_BASE="${SPAWN_SEED_BASE:-2601}"
CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
CARLA_PORT="${CARLA_PORT:-2000}"
WAIT_FOR_CARLA_SECONDS="${WAIT_FOR_CARLA_SECONDS:-420}"
CARLA_INTERNAL_WAIT_SECONDS="${CARLA_INTERNAL_WAIT_SECONDS:-300}"
SCENE_RETRY_COUNT="${SCENE_RETRY_COUNT:-2}"
SCENE_RETRY_SLEEP_SECONDS="${SCENE_RETRY_SLEEP_SECONDS:-20}"
OVERWRITE_SCENE_DIRS="${OVERWRITE_SCENE_DIRS:-0}"
PYTHON_BIN="${PYTHON_BIN:-.conda/bin/python}"
GIF_FPS="${GIF_FPS:-10}"
GIF_STRIDE="${GIF_STRIDE:-2}"
GIF_CAM_WIDTH="${GIF_CAM_WIDTH:-320}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ "$SCENE_COUNT" -lt 1 ]]; then
  echo "SCENE_COUNT must be >= 1" >&2
  exit 1
fi

mkdir -p "$OUTPUT_ROOT"
COMBINED_METADATA="$OUTPUT_ROOT/metadata.jsonl"
SUMMARY_PATH="$OUTPUT_ROOT/collection_summary.json"
: > "$COMBINED_METADATA"
COLLECTED_SCENE_COUNT=0
SKIPPED_SCENE_COUNT=0

echo "Waiting for CARLA server: $CARLA_HOST:$CARLA_PORT"
deadline=$((SECONDS + WAIT_FOR_CARLA_SECONDS))
while ! nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "CARLA server did not open: $CARLA_HOST:$CARLA_PORT" >&2
    exit 1
  fi
  sleep 5
done
echo "CARLA server port is open."
echo "CARLA 내부 초기화 대기 중 (${CARLA_INTERNAL_WAIT_SECONDS}초)..."
sleep "$CARLA_INTERNAL_WAIT_SECONDS"
echo

echo "Starting CARLA scene collection..."
echo "CONFIG_PATH       : $CONFIG_PATH"
echo "OUTPUT_ROOT       : $OUTPUT_ROOT"
echo "SCENE_COUNT       : $SCENE_COUNT"
echo "SECONDS_PER_SCENE : $SECONDS_PER_SCENE"
echo "FPS               : $FPS"
echo "IMAGE             : ${IMAGE_WIDTH}x${IMAGE_HEIGHT}"
echo "TOWN/WEATHER      : $TOWN / $WEATHER"
echo "CONTROL_MODE      : $CONTROL_MODE"
echo "SPEED_CONTROL     : $SPEED_CONTROL"
echo "IGNORE L/S/V      : $IGNORE_LIGHTS_PERCENTAGE / $IGNORE_SIGNS_PERCENTAGE / $IGNORE_VEHICLES_PERCENTAGE"
echo "NPC VEH/PED       : $NPC_VEHICLE_COUNT ($NPC_VEHICLE_FILTER) / $PEDESTRIAN_COUNT"
echo "SYNC/FIXED_DT     : $SYNCHRONOUS_MODE / $FIXED_DELTA_SECONDS"
echo "CMD_LOOKAHEAD     : $ROUTE_COMMAND_LOOKAHEAD_MODE meters=$ROUTE_COMMAND_LOOKAHEAD_METERS frames=$ROUTE_COMMAND_LOOKAHEAD_FRAMES"
echo

for scene_index in $(seq 0 $((SCENE_COUNT - 1))); do
  scene_name="$(printf "scene_%03d" "$scene_index")"
  scene_root="$OUTPUT_ROOT/$scene_name"
  seed=$((SPAWN_SEED_BASE + scene_index))
  echo "Collecting $scene_name seed=$seed ..."

  if [[ -e "$scene_root" ]]; then
    if [[ "$OVERWRITE_SCENE_DIRS" == "1" ]]; then
      rm -rf "$scene_root"
    else
      if [[ -s "$scene_root/metadata.jsonl" ]]; then
        echo "$scene_name already exists; reusing metadata and skipping collection."
        cat "$scene_root/metadata.jsonl" >> "$COMBINED_METADATA"
        SKIPPED_SCENE_COUNT=$((SKIPPED_SCENE_COUNT + 1))
        continue
      fi
      echo "$scene_name exists but metadata is missing or empty; replacing incomplete output."
      rm -rf "$scene_root"
    fi
  fi

  scene_ok=0
  for attempt in $(seq 1 "$SCENE_RETRY_COUNT"); do
    echo "Attempt $attempt/$SCENE_RETRY_COUNT for $scene_name"
    if PYTHONIOENCODING=utf-8 "$WINE_BIN" --bottle "$BOTTLE" --cx-app 'C:\Python37\python.exe' \
      scripts/collect_carla_data.py \
      --config "$CONFIG_PATH" \
      --output-root "$scene_root" \
      --seconds "$SECONDS_PER_SCENE" \
      --fps "$FPS" \
      --image-width "$IMAGE_WIDTH" \
      --image-height "$IMAGE_HEIGHT" \
      --target-speed-mps "$TARGET_SPEED_MPS" \
      --speed-control "$SPEED_CONTROL" \
      --ignore-lights-percentage "$IGNORE_LIGHTS_PERCENTAGE" \
      --ignore-signs-percentage "$IGNORE_SIGNS_PERCENTAGE" \
      --ignore-vehicles-percentage "$IGNORE_VEHICLES_PERCENTAGE" \
      --npc-vehicle-count "$NPC_VEHICLE_COUNT" \
      --npc-vehicle-filter "$NPC_VEHICLE_FILTER" \
      --npc-vehicle-target-speed-mps "$NPC_VEHICLE_TARGET_SPEED_MPS" \
      --pedestrian-count "$PEDESTRIAN_COUNT" \
      --pedestrian-cross-factor "$PEDESTRIAN_CROSS_FACTOR" \
      --pedestrian-running-percentage "$PEDESTRIAN_RUNNING_PERCENTAGE" \
      --synchronous-mode "$SYNCHRONOUS_MODE" \
      --fixed-delta-seconds "$FIXED_DELTA_SECONDS" \
      --route-length "$ROUTE_LENGTH" \
      --driving-stack "$CONTROL_MODE" \
      --route-command-lookahead-mode "$ROUTE_COMMAND_LOOKAHEAD_MODE" \
      --route-command-lookahead-meters "$ROUTE_COMMAND_LOOKAHEAD_METERS" \
      --route-command-lookahead-frames "$ROUTE_COMMAND_LOOKAHEAD_FRAMES" \
      --route-command-yaw-threshold-rad "$ROUTE_COMMAND_YAW_THRESHOLD_RAD" \
      --town "$TOWN" \
      --weather "$WEATHER" \
      --spawn-seed "$seed"; then
      scene_ok=1
      break
    fi
    if [[ -s "$scene_root/metadata.jsonl" ]]; then
      echo "$scene_name command returned non-zero, but metadata exists; accepting scene."
      scene_ok=1
      break
    fi
    rm -rf "$scene_root"
    echo "$scene_name failed; waiting ${SCENE_RETRY_SLEEP_SECONDS}s before retry..."
    sleep "$SCENE_RETRY_SLEEP_SECONDS"
  done

  if [[ "$scene_ok" != "1" ]]; then
    echo "Failed to collect $scene_name after $SCENE_RETRY_COUNT attempts" >&2
    exit 1
  fi

  if [[ ! -f "$scene_root/metadata.jsonl" ]]; then
    echo "metadata missing after $scene_name: $scene_root/metadata.jsonl" >&2
    exit 1
  fi
  cat "$scene_root/metadata.jsonl" >> "$COMBINED_METADATA"
  COLLECTED_SCENE_COUNT=$((COLLECTED_SCENE_COUNT + 1))

  echo "Rendering GIF for $scene_name ..."
  "$PYTHON_BIN" scripts/render_scene_gif.py \
    --scene-dir "$scene_root" \
    --gif-fps "$GIF_FPS" \
    --stride "$GIF_STRIDE" \
    --cam-width "$GIF_CAM_WIDTH" || echo "Warning: GIF render failed for $scene_name (non-fatal)"

  echo "Rendering BEV/control report for $scene_name ..."
  MPLCONFIGDIR=.matplotlib_cache "$PYTHON_BIN" scripts/render_scene_report.py \
    --scene-dir "$scene_root" || echo "Warning: scene report render failed for $scene_name (non-fatal)"
done

FRAME_COUNT="$(wc -l < "$COMBINED_METADATA" | tr -d ' ')"

cat > "$SUMMARY_PATH" <<EOF
{
  "config_path": "$CONFIG_PATH",
  "output_root": "$OUTPUT_ROOT",
  "metadata_path": "$COMBINED_METADATA",
  "scene_count": $SCENE_COUNT,
  "collected_scene_count": $COLLECTED_SCENE_COUNT,
  "skipped_scene_count": $SKIPPED_SCENE_COUNT,
  "seconds_per_scene": $SECONDS_PER_SCENE,
  "fps": $FPS,
  "image_width": $IMAGE_WIDTH,
  "image_height": $IMAGE_HEIGHT,
  "target_speed_mps": $TARGET_SPEED_MPS,
  "speed_control": "$SPEED_CONTROL",
  "ignore_lights_percentage": $IGNORE_LIGHTS_PERCENTAGE,
  "ignore_signs_percentage": $IGNORE_SIGNS_PERCENTAGE,
  "ignore_vehicles_percentage": $IGNORE_VEHICLES_PERCENTAGE,
  "npc_vehicle_count": $NPC_VEHICLE_COUNT,
  "npc_vehicle_filter": "$NPC_VEHICLE_FILTER",
  "npc_vehicle_target_speed_mps": $NPC_VEHICLE_TARGET_SPEED_MPS,
  "pedestrian_count": $PEDESTRIAN_COUNT,
  "pedestrian_cross_factor": $PEDESTRIAN_CROSS_FACTOR,
  "pedestrian_running_percentage": $PEDESTRIAN_RUNNING_PERCENTAGE,
  "synchronous_mode": "$SYNCHRONOUS_MODE",
  "fixed_delta_seconds": $FIXED_DELTA_SECONDS,
  "route_command_lookahead_mode": "$ROUTE_COMMAND_LOOKAHEAD_MODE",
  "route_command_lookahead_meters": $ROUTE_COMMAND_LOOKAHEAD_METERS,
  "route_command_lookahead_frames": $ROUTE_COMMAND_LOOKAHEAD_FRAMES,
  "route_command_yaw_threshold_rad": $ROUTE_COMMAND_YAW_THRESHOLD_RAD,
  "route_length": $ROUTE_LENGTH,
  "town": "$TOWN",
  "weather": "$WEATHER",
  "frame_count": $FRAME_COUNT
}
EOF

echo "CARLA_SCENE_COLLECTION_OK"
echo "metadata=$COMBINED_METADATA"
echo "summary=$SUMMARY_PATH"
echo "frames=$FRAME_COUNT"
