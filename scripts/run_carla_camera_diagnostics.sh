#!/usr/bin/env bash
set -euo pipefail

APP="${CARLA_WINE_APP:-$HOME/Applications/Sikarugir/CARLA_0.9.15.app}"
WINE_BIN="$APP/Contents/SharedSupport/wine/bin/wine"
WINEPATH_BIN="$APP/Contents/SharedSupport/wine/bin/winepath"
PYTHON_WIN_PATH="${CARLA_WINE_PYTHON_PATH:-C:\\Python37\\python.exe}"

HOST="${CARLA_HOST:-127.0.0.1}"
PORT="${CARLA_PORT:-2000}"
TIMEOUT="${CARLA_TIMEOUT:-60}"
OUT_DIR="${CARLA_DIAG_OUT_DIR:-/private/tmp/carla_camera_diag}"

if [[ ! -x "$WINE_BIN" ]]; then
  echo "BLOCKED: Wine binary not found: $WINE_BIN" >&2
  exit 2
fi

export WINEPREFIX="$APP/Contents/SharedSupport/prefix"
export CARLA_ROOT_WIN="C:\\CARLA"
export PYTHONIOENCODING="utf-8"
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/SharedSupport/wine/lib:$APP/Contents/Frameworks:$APP/Contents/Frameworks/GStreamer.framework/Libraries:${DYLD_FALLBACK_LIBRARY_PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT_WIN="$("$WINEPATH_BIN" -w "$REPO_ROOT/scripts/diagnose_carla_camera_sensors.py")"
mkdir -p "$OUT_DIR"
OUT_DIR_ABS="$(cd "$OUT_DIR" && pwd)"
OUT_DIR_WIN="$("$WINEPATH_BIN" -w "$OUT_DIR_ABS")"

"$WINE_BIN" "$PYTHON_WIN_PATH" "$SCRIPT_WIN" \
  --host "$HOST" \
  --port "$PORT" \
  --timeout "$TIMEOUT" \
  --out-dir "$OUT_DIR_WIN"

echo "Diagnostics written under: $OUT_DIR_ABS"
