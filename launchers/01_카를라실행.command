#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# CARLA 실행 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

CARLA_PORT=2000
CARLA_QUALITY=Low
CARLA_MAP=/Game/Carla/Maps/Town01
KILL_EXISTING=1
FORCE_LOW_SETTINGS=1
FORCE_DX11=0
WINDOWED=1
RESX=800
RESY=600
NO_SOUND=1
RENDER_OFFSCREEN=0
CARLA_FPS=30
EXTRA_ARGS=()

# RGB 렌더링은 CrossOver 64-bit + D3DMetal bottle을 기본으로 사용한다.
# CARLA/Python37 원본은 data/offline/simulators/carla/crossover_source를 사용한다.
CARLA_CROSSOVER_BOTTLE=carla-rgb64
# export CARLA_CROSSOVER_APP="/Applications/CrossOver.app"
# export CARLA_SOURCE_WINE_PREFIX="/absolute/path/to/crossover_source"

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CARLA_SOURCE_WINE_PREFIX_EFFECTIVE="${CARLA_SOURCE_WINE_PREFIX:-$REPO_ROOT/data/offline/simulators/carla/crossover_source}"

cd "$REPO_ROOT"

if [[ "$KILL_EXISTING" == "1" ]]; then
  echo "Stopping existing CARLA processes..."

  BOTTLE_DIR="$HOME/Library/Application Support/CrossOver/Bottles/$CARLA_CROSSOVER_BOTTLE"
  WINE_BIN="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine"

  # 1. wineserver -k 로 해당 bottle 전체 종료 (가장 확실)
  if [[ -x "$WINE_BIN" && -d "$BOTTLE_DIR" ]]; then
    WINEPREFIX="$BOTTLE_DIR" "$WINE_BIN" --bottle "$CARLA_CROSSOVER_BOTTLE" --cx-app wineserver -- -k 2>/dev/null || true
    sleep 1
  fi

  # 2. 프로세스 이름 기반 fallback
  pkill -f "CarlaUE4" 2>/dev/null || true
  pkill -f "carla-rgb64" 2>/dev/null || true
  pkill -f "CARLA_0.9" 2>/dev/null || true

  # 3. 포트를 점유 중인 프로세스 종료
  if command -v lsof >/dev/null 2>&1; then
    PORT_PIDS="$(lsof -tiTCP:"$CARLA_PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$PORT_PIDS" ]]; then
      echo "Stopping processes on port $CARLA_PORT: $PORT_PIDS"
      kill $PORT_PIDS 2>/dev/null || true
    fi
  fi

  sleep 3
fi

if [[ "$FORCE_LOW_SETTINGS" == "1" ]]; then
  UE_CONFIG_DIR="$HOME/Library/Application Support/CrossOver/Bottles/$CARLA_CROSSOVER_BOTTLE/drive_c/users/crossover/AppData/Local/CarlaUE4/Saved/Config/WindowsNoEditor"
  mkdir -p "$UE_CONFIG_DIR"

  cat > "$UE_CONFIG_DIR/GameUserSettings.ini" <<EOF
[/Script/Engine.GameUserSettings]
bUseVSync=False
bUseDynamicResolution=False
ResolutionSizeX=$RESX
ResolutionSizeY=$RESY
LastUserConfirmedResolutionSizeX=$RESX
LastUserConfirmedResolutionSizeY=$RESY
WindowPosX=-1
WindowPosY=-1
LastConfirmedFullscreenMode=2
PreferredFullscreenMode=2
AudioQualityLevel=0
LastConfirmedAudioQualityLevel=0
FrameRateLimit=15.000000
DesiredScreenWidth=$RESX
bUseDesiredScreenHeight=True
DesiredScreenHeight=$RESY
LastUserConfirmedDesiredScreenWidth=$RESX
LastUserConfirmedDesiredScreenHeight=$RESY
bUseHDRDisplayOutput=False
HDRDisplayOutputNits=1000

[ScalabilityGroups]
sg.ResolutionQuality=50.000000
sg.ViewDistanceQuality=0
sg.AntiAliasingQuality=0
sg.ShadowQuality=0
sg.PostProcessQuality=0
sg.TextureQuality=0
sg.EffectsQuality=0
sg.FoliageQuality=0
sg.ShadingQuality=0
EOF

  if [[ "$FORCE_DX11" == "1" ]]; then
    cat >> "$UE_CONFIG_DIR/Engine.ini" <<EOF

[/Script/WindowsTargetPlatform.WindowsTargetSettings]
DefaultGraphicsRHI=DefaultGraphicsRHI_DX11
EOF
  elif [[ -f "$UE_CONFIG_DIR/Engine.ini" ]]; then
    sed -i '' '/DefaultGraphicsRHI=DefaultGraphicsRHI_DX11/d' "$UE_CONFIG_DIR/Engine.ini"
  fi
fi

if [[ "$FORCE_DX11" == "1" ]]; then
  EXTRA_ARGS+=("-dx11" "-d3d11")
fi
if [[ "$RENDER_OFFSCREEN" == "1" ]]; then
  EXTRA_ARGS+=("-RenderOffScreen")
fi
if [[ "$WINDOWED" == "1" ]]; then
  EXTRA_ARGS+=("-windowed" "-ResX=$RESX" "-ResY=$RESY")
fi
if [[ "$NO_SOUND" == "1" ]]; then
  EXTRA_ARGS+=("-nosound")
fi
EXTRA_ARGS+=("-NoVSync" "-fps=$CARLA_FPS")

echo "Starting CARLA..."
echo "REPO_ROOT : $REPO_ROOT"
echo "PORT      : $CARLA_PORT"
echo "QUALITY   : $CARLA_QUALITY"
echo "FPS CAP   : $CARLA_FPS"
echo "BACKEND   : CrossOver D3DMetal"
echo "BOTTLE    : $CARLA_CROSSOVER_BOTTLE"
echo "ARGS      : ${EXTRA_ARGS[*]:-}"
echo
echo "이 경로는 CrossOver 64-bit bottle + D3DMetal을 사용합니다."
echo "127.0.0.1:$CARLA_PORT 포트가 열리면 CARLA server는 실행된 상태입니다."
echo

if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
  CARLA_PORT="$CARLA_PORT" CARLA_QUALITY="$CARLA_QUALITY" \
  CARLA_MAP="$CARLA_MAP" \
  CARLA_CROSSOVER_BOTTLE="$CARLA_CROSSOVER_BOTTLE" \
  CARLA_SOURCE_WINE_PREFIX="$CARLA_SOURCE_WINE_PREFIX_EFFECTIVE" \
    "$REPO_ROOT/scripts/run_carla_mac_crossover.sh" "${EXTRA_ARGS[@]}"
else
  CARLA_PORT="$CARLA_PORT" CARLA_QUALITY="$CARLA_QUALITY" \
  CARLA_MAP="$CARLA_MAP" \
  CARLA_CROSSOVER_BOTTLE="$CARLA_CROSSOVER_BOTTLE" \
  CARLA_SOURCE_WINE_PREFIX="$CARLA_SOURCE_WINE_PREFIX_EFFECTIVE" \
    "$REPO_ROOT/scripts/run_carla_mac_crossover.sh"
fi
