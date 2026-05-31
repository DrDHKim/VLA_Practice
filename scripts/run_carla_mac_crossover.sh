#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CROSSOVER_APP="${CARLA_CROSSOVER_APP:-/Applications/CrossOver.app}"
BOTTLE="${CARLA_CROSSOVER_BOTTLE:-carla-rgb64}"
SOURCE_PREFIX="${CARLA_SOURCE_WINE_PREFIX:-$REPO_ROOT/data/offline/simulators/carla/crossover_source}"
PORT="${CARLA_PORT:-2000}"
QUALITY="${CARLA_QUALITY:-Epic}"

WINE_BIN="$CROSSOVER_APP/Contents/SharedSupport/CrossOver/bin/wine"
CXBOTTLE_BIN="$CROSSOVER_APP/Contents/SharedSupport/CrossOver/bin/cxbottle"
BOTTLE_DIR="$HOME/Library/Application Support/CrossOver/Bottles/$BOTTLE"

if [[ ! -x "$WINE_BIN" || ! -x "$CXBOTTLE_BIN" ]]; then
  echo "CrossOver command not found: $CROSSOVER_APP" >&2
  echo "Install CrossOver first: brew install --cask crossover" >&2
  exit 1
fi

if [[ ! -d "$BOTTLE_DIR" ]]; then
  "$CXBOTTLE_BIN" --bottle "$BOTTLE" --create --template win10_64 \
    --description "CARLA RGB 64-bit test"
fi

if [[ ! -e "$SOURCE_PREFIX/drive_c/CARLA" ]]; then
  echo "CARLA install not found under: $SOURCE_PREFIX/drive_c/CARLA" >&2
  exit 1
fi

mkdir -p "$BOTTLE_DIR/drive_c"
if [[ ! -e "$BOTTLE_DIR/drive_c/CARLA" ]]; then
  ln -s "$SOURCE_PREFIX/drive_c/CARLA" "$BOTTLE_DIR/drive_c/CARLA"
fi
if [[ ! -e "$BOTTLE_DIR/drive_c/Python37" && -d "$SOURCE_PREFIX/drive_c/Python37" ]]; then
  ln -s "$SOURCE_PREFIX/drive_c/Python37" "$BOTTLE_DIR/drive_c/Python37"
fi

CONF="$BOTTLE_DIR/cxbottle.conf"
if [[ -f "$CONF" ]]; then
  perl -0pi -e 's/\[EnvironmentVariables\]\n(?:"WINED3DMETAL".*\n|"WINEDXVK".*\n|"CX_GRAPHICS_BACKEND".*\n|"WINEMSYNC".*\n|"D3DM_SUPPORT_DXR".*\n|"ROSETTA_ADVERTISE_AVX".*\n)*/[EnvironmentVariables]\n"WINED3DMETAL" = "1"\n"WINEDXVK" = "0"\n"CX_GRAPHICS_BACKEND" = "d3dmetal"\n"WINEMSYNC" = "1"\n"D3DM_SUPPORT_DXR" = "0"\n"ROSETTA_ADVERTISE_AVX" = "1"\n/' "$CONF"
fi

MAP_ARG="${CARLA_MAP:-}"

exec "$WINE_BIN" --bottle "$BOTTLE" --cx-app 'C:\CARLA\CarlaUE4.exe' \
  ${MAP_ARG:+"$MAP_ARG"} \
  "-quality-level=$QUALITY" \
  "-carla-rpc-port=$PORT" \
  "$@"
