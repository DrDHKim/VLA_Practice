#!/usr/bin/env bash
set -euo pipefail

CROSSOVER_APP="${CARLA_CROSSOVER_APP:-/Applications/CrossOver.app}"
BOTTLE="${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}"
HOST="${CARLA_HOST:-127.0.0.1}"
PORT="${CARLA_PORT:-2000}"
TIMEOUT="${CARLA_TIMEOUT:-5.0}"

WINE_BIN="$CROSSOVER_APP/Contents/SharedSupport/CrossOver/bin/wine"
PYTHON_EXE="C:\\Python37\\python.exe"
CARLA_EGG="C:\\CARLA\\PythonAPI\\carla\\dist\\carla-0.9.15-py3.7-win-amd64.egg"

if [[ ! -x "$WINE_BIN" ]]; then
  echo "CrossOver wine not found: $WINE_BIN" >&2
  exit 1
fi

exec "$WINE_BIN" --bottle "$BOTTLE" --cx-app "$PYTHON_EXE" -c \
  "import sys; sys.path.insert(0, r'$CARLA_EGG'); import carla; client = carla.Client('$HOST', int('$PORT')); client.set_timeout(float('$TIMEOUT')); world = client.get_world(); print('CARLA_WORLD', world.get_map().name)"
