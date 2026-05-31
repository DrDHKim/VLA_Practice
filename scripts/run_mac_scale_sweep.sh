#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# MacBook scale envelope parameters
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

PYTHON_BIN="${PYTHON_BIN:-.conda/bin/python}"
METADATA_PATH="${METADATA_PATH:-/Volumes/DATASET/vla_drive_carla/m1_smoke/metadata.jsonl}"
OUT_DIR="${OUT_DIR:-outputs/reports/mac_scale}"
SUMMARY_PATH="${SUMMARY_PATH:-outputs/reports/mac_scale_envelope.json}"
DEVICE="${DEVICE:-cpu}"

EPOCHS="${EPOCHS:-2}"
BATCH_SIZE="${BATCH_SIZE:-2}"
IMAGE_SIZES=(${IMAGE_SIZES:-64})
MAX_SAMPLES_LIST=(${MAX_SAMPLES_LIST:-10 20})

# 기본 sweep은 CARLA server 없이 가능한 학습/평가만 수행한다.
# CARLA collection/closed-loop까지 포함하려면 CARLA를 먼저 켠 뒤 아래 flag를 1로 실행한다.
RUN_CARLA_COLLECTION="${RUN_CARLA_COLLECTION:-0}"
RUN_CARLA_CLOSED_LOOP="${RUN_CARLA_CLOSED_LOOP:-0}"
CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
CARLA_PORT="${CARLA_PORT:-2000}"
CARLA_TOWN="${CARLA_TOWN:-Town01}"
CARLA_WEATHER="${CARLA_WEATHER:-ClearNoon}"
COLLECTION_SECONDS_LIST=(${COLLECTION_SECONDS_LIST:-5})
COLLECTION_RESOLUTIONS=(${COLLECTION_RESOLUTIONS:-160x90})
CLOSED_LOOP_ROUTE_COUNTS=(${CLOSED_LOOP_ROUTE_COUNTS:-1 5})
CLOSED_LOOP_ROUTE_SECONDS="${CLOSED_LOOP_ROUTE_SECONDS:-3}"

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p "$OUT_DIR"

if [[ ! -f "$METADATA_PATH" ]]; then
  echo "metadata가 없습니다: $METADATA_PATH"
  echo "먼저 CARLA collection을 실행하거나 METADATA_PATH를 기존 JSONL로 지정하세요."
  exit 1
fi

RUNS_JSONL="$OUT_DIR/runs.jsonl"
COLLECTION_JSONL="$OUT_DIR/collection_runs.jsonl"
CLOSED_LOOP_JSONL="$OUT_DIR/closed_loop_runs.jsonl"
ENV_JSON="$OUT_DIR/environment.json"
: > "$RUNS_JSONL"
: > "$COLLECTION_JSONL"
: > "$CLOSED_LOOP_JSONL"

"$PYTHON_BIN" - "$METADATA_PATH" "$ENV_JSON" <<'PY'
import json
import platform
import shutil
import sys
from pathlib import Path

metadata_path = Path(sys.argv[1])
env_path = Path(sys.argv[2])
sample_count = sum(1 for line in metadata_path.open("r", encoding="utf-8") if line.strip())
disk = shutil.disk_usage(Path.cwd())
record = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "metadata_path": str(metadata_path),
    "metadata_sample_count": sample_count,
    "disk_free_gib": round(disk.free / (1024 ** 3), 2),
    "disk_total_gib": round(disk.total / (1024 ** 3), 2),
}
env_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
print("ENV", json.dumps(record, sort_keys=True))
PY

run_collection() {
  local label="$1"
  local seconds="$2"
  local resolution="$3"
  local width="${resolution%x*}"
  local height="${resolution#*x}"
  local output_root="$OUT_DIR/collections/$label"
  local config_path="$OUT_DIR/${label}_collection.yaml"
  local started_at ended_at status message metadata_path frames

  echo "==> collection $label"
  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  status="ok"
  message=""
  metadata_path="$output_root/metadata.jsonl"
  frames=0

  cat > "$config_path" <<EOF
simulation:
  host: $CARLA_HOST
  port: $CARLA_PORT
  town: $CARLA_TOWN
  weather: $CARLA_WEATHER
  timeout_seconds: 30.0
  synchronous_mode: false
  fixed_delta_seconds: 0.05

collection:
  seconds: $seconds
  fps: 10.0
  warmup_seconds: 1.0
  image_width: $width
  image_height: $height
  fov: 90.0
  vehicle_filter: vehicle.tesla.model3
  target_speed_mps: 5.0
  route_length: 80
  waypoint_spacing_m: 2.0
  future_waypoint_count: 8

data:
  root: $output_root
EOF

  if ! nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; then
    status="port_closed"
    message="CARLA RPC port is not open"
  elif ! PYTHONIOENCODING=utf-8 /Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine \
    --bottle "${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}" \
    --cx-app 'C:\Python37\python.exe' \
    scripts/collect_carla_data.py \
    --config "$config_path" \
    --output-root "$output_root"; then
    status="failed"
    message="collection command failed"
  fi

  if [[ -f "$metadata_path" ]]; then
    frames="$(wc -l < "$metadata_path" | tr -d ' ')"
  fi
  ended_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  "$PYTHON_BIN" - "$COLLECTION_JSONL" "$label" "$seconds" "$width" "$height" "$output_root" "$metadata_path" "$frames" \
    "$started_at" "$ended_at" "$status" "$message" <<'PY'
import json
import sys
from pathlib import Path

(
    runs_path,
    label,
    seconds,
    width,
    height,
    output_root,
    metadata_path,
    frames,
    started_at,
    ended_at,
    status,
    message,
) = sys.argv[1:13]

record = {
    "label": label,
    "seconds": float(seconds),
    "image_width": int(width),
    "image_height": int(height),
    "output_root": output_root,
    "metadata_path": metadata_path if Path(metadata_path).exists() else None,
    "frames": int(frames),
    "started_at": started_at,
    "ended_at": ended_at,
    "status": status,
    "message": message,
}
with Path(runs_path).open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True) + "\n")
print("COLLECTION", json.dumps(record, sort_keys=True))
PY
}

run_training_eval() {
  local label="$1"
  local stage="$2"
  local reasoning_mode="$3"
  local image_size="$4"
  local max_samples="$5"
  local checkpoint_dir="$OUT_DIR/checkpoints/$label"
  local log_dir="$OUT_DIR/logs/$label"
  local report_path="$OUT_DIR/${label}_open_loop.json"
  local started_at ended_at status message

  echo "==> $label"
  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  status="ok"
  message=""

  if ! STAGE="$stage" \
    REASONING_MODE="$reasoning_mode" \
    EPOCHS="$EPOCHS" \
    BATCH_SIZE="$BATCH_SIZE" \
    IMAGE_SIZE="$image_size" \
    MAX_SAMPLES="$max_samples" \
    CHECKPOINT_DIR="$checkpoint_dir" \
    LOG_DIR="$log_dir" \
    DEVICE="$DEVICE" \
    NUM_ACTION_TOKENS=64 \
      scripts/train_lora.sh; then
    status="train_failed"
    message="training command failed"
  elif ! "$PYTHON_BIN" -m vla_drive.evaluation.evaluator \
    --checkpoint-path "$checkpoint_dir/latest.pt" \
    --metadata-path "$METADATA_PATH" \
    --report-path "$report_path" \
    --max-samples "$max_samples" \
    --batch-size "$BATCH_SIZE" \
    --image-size "$image_size" \
    --device "$DEVICE"; then
    status="eval_failed"
    message="open-loop evaluation command failed"
  fi

  ended_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  "$PYTHON_BIN" - "$RUNS_JSONL" "$label" "$stage" "$reasoning_mode" "$image_size" "$max_samples" \
    "$checkpoint_dir" "$log_dir" "$report_path" "$started_at" "$ended_at" "$status" "$message" <<'PY'
import json
import sys
from pathlib import Path

(
    runs_path,
    label,
    stage,
    reasoning_mode,
    image_size,
    max_samples,
    checkpoint_dir,
    log_dir,
    report_path,
    started_at,
    ended_at,
    status,
    message,
) = sys.argv[1:14]

record = {
    "label": label,
    "stage": stage,
    "reasoning_mode": reasoning_mode,
    "image_size": int(image_size),
    "max_samples": int(max_samples),
    "checkpoint_dir": checkpoint_dir,
    "log_dir": log_dir,
    "report_path": report_path,
    "started_at": started_at,
    "ended_at": ended_at,
    "status": status,
    "message": message,
}
path = Path(report_path)
if path.exists():
    report = json.loads(path.read_text(encoding="utf-8"))
    record["metrics"] = {
        key: report[key]
        for key in ["ade", "fde", "route_deviation", "collision_proxy_rate", "sample_count"]
        if key in report
    }
with Path(runs_path).open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True) + "\n")
print("RUN", json.dumps(record, sort_keys=True))
PY
}

for image_size in "${IMAGE_SIZES[@]}"; do
  for max_samples in "${MAX_SAMPLES_LIST[@]}"; do
    run_training_eval "dummy_i${image_size}_n${max_samples}" "dummy_overfit" "fast" "$image_size" "$max_samples"
    run_training_eval "reason_fast_i${image_size}_n${max_samples}" "reasoning_aux" "fast" "$image_size" "$max_samples"
    run_training_eval "reason_slow_i${image_size}_n${max_samples}" "reasoning_aux" "slow" "$image_size" "$max_samples"
    run_training_eval "action_token_i${image_size}_n${max_samples}" "action_token" "fast" "$image_size" "$max_samples"
  done
done

collection_status="skipped"
if [[ "$RUN_CARLA_COLLECTION" == "1" ]]; then
  collection_status="ok"
  for seconds in "${COLLECTION_SECONDS_LIST[@]}"; do
    for resolution in "${COLLECTION_RESOLUTIONS[@]}"; do
      run_collection "collect_${seconds}s_${resolution}" "$seconds" "$resolution"
    done
  done
fi

closed_loop_status="skipped"
closed_loop_report=""
if [[ "$RUN_CARLA_CLOSED_LOOP" == "1" ]]; then
  if nc -z "$CARLA_HOST" "$CARLA_PORT" >/dev/null 2>&1; then
    closed_loop_status="ok"
    for route_count in "${CLOSED_LOOP_ROUTE_COUNTS[@]}"; do
      report_path="$OUT_DIR/closed_loop_${route_count}routes_${CLOSED_LOOP_ROUTE_SECONDS}s.json"
      status="ok"
      started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      if ! ROUTE_COUNT="$route_count" ROUTE_SECONDS="$CLOSED_LOOP_ROUTE_SECONDS" REPORT_PATH="$report_path" scripts/eval_carla.sh; then
        status="failed"
        closed_loop_status="failed"
      fi
      ended_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      "$PYTHON_BIN" - "$CLOSED_LOOP_JSONL" "$route_count" "$CLOSED_LOOP_ROUTE_SECONDS" "$report_path" "$started_at" "$ended_at" "$status" <<'PY'
import json
import sys
from pathlib import Path

runs_path, route_count, route_seconds, report_path, started_at, ended_at, status = sys.argv[1:8]
record = {
    "route_count": int(route_count),
    "route_seconds": float(route_seconds),
    "report_path": report_path if Path(report_path).exists() else None,
    "started_at": started_at,
    "ended_at": ended_at,
    "status": status,
}
path = Path(report_path)
if path.exists():
    report = json.loads(path.read_text(encoding="utf-8"))
    record["aggregate"] = report.get("aggregate", {})
with Path(runs_path).open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True) + "\n")
print("CLOSED_LOOP", json.dumps(record, sort_keys=True))
PY
    done
  else
    closed_loop_status="port_closed"
  fi
fi

"$PYTHON_BIN" - "$ENV_JSON" "$RUNS_JSONL" "$COLLECTION_JSONL" "$CLOSED_LOOP_JSONL" "$SUMMARY_PATH" "$collection_status" "$closed_loop_status" <<'PY'
import json
import sys
from pathlib import Path

env_path, runs_path, collection_path, closed_loop_path, summary_path, collection_status, closed_loop_status = sys.argv[1:8]
environment = json.loads(Path(env_path).read_text(encoding="utf-8"))
runs = [
    json.loads(line)
    for line in Path(runs_path).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
collection_runs = [
    json.loads(line)
    for line in Path(collection_path).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
closed_loop_runs = [
    json.loads(line)
    for line in Path(closed_loop_path).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
successful = [run for run in runs if run["status"] == "ok"]
failed = [run for run in runs if run["status"] != "ok"]
best_by_ade = None
if successful:
    best_by_ade = min(successful, key=lambda run: run.get("metrics", {}).get("ade", float("inf")))["label"]

summary = {
    "environment": environment,
    "run_count": len(runs),
    "successful_count": len(successful),
    "failed_count": len(failed),
    "best_by_ade": best_by_ade,
    "runs": runs,
    "collection": {
        "status": collection_status,
        "runs": collection_runs,
        "successful_count": sum(1 for run in collection_runs if run["status"] == "ok"),
        "failed_count": sum(1 for run in collection_runs if run["status"] != "ok"),
    },
    "closed_loop": {
        "status": closed_loop_status,
        "runs": closed_loop_runs,
        "successful_count": sum(1 for run in closed_loop_runs if run["status"] == "ok"),
        "failed_count": sum(1 for run in closed_loop_runs if run["status"] != "ok"),
    },
}
Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
Path(summary_path).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
print("MAC_SCALE_ENVELOPE_OK")
print(json.dumps({
    "summary_path": summary_path,
    "run_count": summary["run_count"],
    "successful_count": summary["successful_count"],
    "failed_count": summary["failed_count"],
    "best_by_ade": best_by_ade,
    "collection_status": collection_status,
    "closed_loop_status": closed_loop_status,
}, sort_keys=True))
PY
