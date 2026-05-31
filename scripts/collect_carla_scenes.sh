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
ROUTE_LENGTH="${ROUTE_LENGTH:-120}"
TOWN="${TOWN:-Town01}"
WEATHER="${WEATHER:-ClearNoon}"
SPAWN_SEED_BASE="${SPAWN_SEED_BASE:-2601}"
CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
CARLA_PORT="${CARLA_PORT:-2000}"
WAIT_FOR_CARLA_SECONDS="${WAIT_FOR_CARLA_SECONDS:-420}"
SCENE_RETRY_COUNT="${SCENE_RETRY_COUNT:-2}"
SCENE_RETRY_SLEEP_SECONDS="${SCENE_RETRY_SLEEP_SECONDS:-20}"

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
echo "CARLA 내부 초기화 대기 중 (120초)..."
sleep 120
echo

echo "Starting CARLA scene collection..."
echo "CONFIG_PATH       : $CONFIG_PATH"
echo "OUTPUT_ROOT       : $OUTPUT_ROOT"
echo "SCENE_COUNT       : $SCENE_COUNT"
echo "SECONDS_PER_SCENE : $SECONDS_PER_SCENE"
echo "FPS               : $FPS"
echo "IMAGE             : ${IMAGE_WIDTH}x${IMAGE_HEIGHT}"
echo "TOWN/WEATHER      : $TOWN / $WEATHER"
echo

for scene_index in $(seq 0 $((SCENE_COUNT - 1))); do
  scene_name="$(printf "scene_%03d" "$scene_index")"
  scene_root="$OUTPUT_ROOT/$scene_name"
  seed=$((SPAWN_SEED_BASE + scene_index))
  echo "Collecting $scene_name seed=$seed ..."

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
      --route-length "$ROUTE_LENGTH" \
      --town "$TOWN" \
      --weather "$WEATHER" \
      --spawn-seed "$seed"; then
      scene_ok=1
      break
    fi
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
done

FRAME_COUNT="$(wc -l < "$COMBINED_METADATA" | tr -d ' ')"

cat > "$SUMMARY_PATH" <<EOF
{
  "config_path": "$CONFIG_PATH",
  "output_root": "$OUTPUT_ROOT",
  "metadata_path": "$COMBINED_METADATA",
  "scene_count": $SCENE_COUNT,
  "seconds_per_scene": $SECONDS_PER_SCENE,
  "fps": $FPS,
  "image_width": $IMAGE_WIDTH,
  "image_height": $IMAGE_HEIGHT,
  "target_speed_mps": $TARGET_SPEED_MPS,
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
