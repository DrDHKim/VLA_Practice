# Mac CARLA 설치 문서

이 문서는 Apple Silicon Mac에서 Windows CARLA 0.9.15를 RGB camera까지 동작시키는 clean install 절차다. CARLA의 공식 지원 경로는 Linux/Windows server이며, 이 Mac 경로는 MacBook에서 가능한 CARLA 수집/평가를 먼저 수행하기 위한 experimental local server로 사용한다.

검증 상태:

- 날짜: 2026-05-31
- 장비: Apple Silicon Mac
- Runtime: Windows CARLA 0.9.15 `WindowsNoEditor/CarlaUE4.exe`
- 실행 backend: CrossOver 26.1.0, 64-bit bottle, D3DMetal
- 검증: `127.0.0.1:2000` RPC port open, RGB camera raw frame 정상, 100 frame smoke drive 영상 생성

## 핵심 결론

Sikarugir/Wine10 단독 실행은 CARLA RPC server와 depth/semantic sensor까지는 동작했지만, `sensor.camera.rgb` raw buffer가 alpha channel만 채워지고 B/G/R channel은 0으로 나왔다. PNG 저장 문제가 아니라 renderer backend 문제다.

이 Mac에서 RGB camera까지 통과한 경로는 CrossOver 64-bit bottle + D3DMetal이다. `C:\CARLA`와 `C:\Python37` 원본은 `data/offline/simulators/carla/crossover_source` 아래에 둔다.

## 설치 결과 위치

```text
/Applications/CrossOver.app
~/Library/Application Support/CrossOver/Bottles/carla-rgb64
data/offline/simulators/carla/crossover_source
```

CrossOver bottle에는 대용량 CARLA runtime을 복사하지 않고 symlink만 둔다.

```text
~/Library/Application Support/CrossOver/Bottles/carla-rgb64/drive_c/CARLA
  -> data/offline/simulators/carla/crossover_source/drive_c/CARLA

~/Library/Application Support/CrossOver/Bottles/carla-rgb64/drive_c/Python37
  -> data/offline/simulators/carla/crossover_source/drive_c/Python37
```

## Clean Install

Rosetta와 CrossOver를 설치한다.

```bash
softwareupdate --install-rosetta --agree-to-license
brew install --cask crossover
```

CARLA Windows runtime과 Windows Python 3.7 x64가 들어 있는 source prefix를 준비한다. 현재 저장소 launcher는 아래 위치를 기본 source prefix로 사용한다.

```bash
SOURCE_PREFIX="$(pwd)/data/offline/simulators/carla/crossover_source"
mkdir -p "$SOURCE_PREFIX/drive_c"
```

CARLA Windows package를 준비한다.

```bash
mkdir -p data/offline/simulators/carla
curl -L https://tiny.carla.org/carla-0-9-15-windows \
  -o data/offline/simulators/carla/CARLA_0.9.15.zip
unzip -q data/offline/simulators/carla/CARLA_0.9.15.zip \
  -d data/offline/simulators/carla/CARLA_0.9.15_Windows
ln -sfn "$(pwd)/data/offline/simulators/carla/CARLA_0.9.15_Windows/WindowsNoEditor" \
  "$SOURCE_PREFIX/drive_c/CARLA"
```

Windows Python 3.7 x64를 source prefix의 `C:\Python37`에 설치한다. 이유는 CARLA 0.9.15 Windows package가 `carla-0.9.15-py3.7-win-amd64.egg`를 제공하기 때문이다.

```bash
# Python installer가 이미 준비되어 있으면 그 파일을 사용한다.
# 없으면 online 환경에서 Python 3.7.x Windows x86-64 executable installer를 내려받아 설치한다.
```

CrossOver 64-bit bottle을 만들고 D3DMetal을 켠다.

```bash
/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/cxbottle \
  --bottle carla-rgb64 \
  --create \
  --template win10_64 \
  --description "CARLA RGB 64-bit"

BOTTLE="$HOME/Library/Application Support/CrossOver/Bottles/carla-rgb64"
mkdir -p "$BOTTLE/drive_c"
ln -sfn "$SOURCE_PREFIX/drive_c/CARLA" "$BOTTLE/drive_c/CARLA"
ln -sfn "$SOURCE_PREFIX/drive_c/Python37" "$BOTTLE/drive_c/Python37"
```

`$BOTTLE/cxbottle.conf`의 `[EnvironmentVariables]`에 아래 값을 둔다. `scripts/run_carla_mac_crossover.sh`는 이 값을 매 실행 시 보정한다.

```text
"WINED3DMETAL" = "1"
"WINEDXVK" = "0"
"CX_GRAPHICS_BACKEND" = "d3dmetal"
"WINEMSYNC" = "1"
"D3DM_SUPPORT_DXR" = "0"
"ROSETTA_ADVERTISE_AVX" = "1"
```

## 실행

저장소 루트에서 실행한다.

```bash
./launchers/01_카를라실행.command
```

또는 script를 직접 실행한다.

```bash
CARLA_PORT=2000 CARLA_QUALITY=Epic scripts/run_carla_mac_crossover.sh \
  -windowed -ResX=800 -ResY=600 -nosound -NoVSync -fps=15
```

CARLA가 켜진 뒤 별도 shell에서 연결을 확인한다.

```bash
./launchers/02_카를라연결확인.command
```

RGB camera가 실제 색을 내는지 확인하려면 CrossOver bottle의 Python으로 진단 script를 실행한다.

```bash
/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine \
  --bottle carla-rgb64 \
  --cx-app 'C:\Python37\python.exe' \
  scripts/diagnose_carla_camera_sensors.py \
  --host 127.0.0.1 \
  --port 2000 \
  --timeout 60 \
  --out-dir /private/tmp/carla_camera_diag
```

성공 기준은 `sensor.camera.rgb`의 raw stats에서 `nonzero`가 alpha-only 값인 `width * height` 수준이 아니라, B/G/R까지 채워진 값으로 나오는 것이다. 검증 당시 `640x360` RGB default frame은 `nonzero=921399`였다.

## 정리 기준

남겨야 하는 것:

- `/Applications/CrossOver.app`
- `~/Library/Application Support/CrossOver/Bottles/carla-rgb64`
- `data/offline/simulators/carla/crossover_source/drive_c/CARLA`
- `data/offline/simulators/carla/crossover_source/drive_c/Python37`
- `data/offline/simulators/carla/` 안의 CARLA archive/runtime

삭제해도 되는 실험 찌꺼기:

- `/private/tmp/carla_*`
- `/private/tmp/vkd3d_versions`
- failed CrossOver 32-bit bottle `~/Library/Application Support/CrossOver/Bottles/carla-rgb`
- Sikarugir app과 cask. 최종 RGB 경로에서는 필요하지 않다.
- Sikarugir prefix 안의 `dxvk-*-disabled`, `windows/temp/_dxvk`, `windows/temp/_vkd3d`
- `outputs/carla_smoke/`의 임시 smoke 영상과 frame. 재현 영상이 필요할 때만 새로 생성한다.

## Troubleshooting

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| RGB image가 검게 저장되고 raw stats가 `nonzero=width*height` 근처 | alpha channel만 255이고 B/G/R이 0인 renderer backend 문제 | Sikarugir/Wine10 단독 경로를 쓰지 말고 CrossOver 64-bit bottle + D3DMetal을 사용한다. |
| `wine: could not load kernel32.dll, status c000007b` | 32-bit bottle에서 64-bit CARLA를 실행함 | `win10_64` bottle `carla-rgb64`를 새로 만든다. |
| DXVK가 `geometryShader` 미지원 또는 adapter 없음으로 실패 | Apple Silicon/MoltenVK 조합에서 DXVK feature requirement를 만족하지 못함 | DXVK를 끄고 D3DMetal을 사용한다. |
| VKD3D가 cooperative matrix 또는 transform feedback 부족으로 실패 | Apple Silicon Vulkan feature mismatch | VKD3D 경로를 쓰지 않는다. |
| macOS native Python에서 `import carla` 실패 | Windows CARLA package는 macOS wheel을 포함하지 않음 | CrossOver bottle 내부 `C:\Python37\python.exe`와 Windows CARLA egg를 사용한다. |
| 한글 경로에 PNG 저장 실패 또는 누락 | Wine path 변환/파일 저장 이슈 | capture output은 `/private/tmp/...`처럼 ASCII path를 우선 사용한다. |

## 운영 기준

- Mac에서는 tiny smoke route에서 시작하고, 가능한 범위까지 route 수, collection 시간, image resolution을 확장한다.
- Mac에서 렌더링 안정성, 시간, 메모리, 저장공간 한계가 확인되면 그 기록을 남긴 뒤 RTX 5090 또는 AIP/H100으로 확장한다.
- 이 문서의 Mac local server가 불안정하면 `src/vla_drive/configs/carla_rgb_waypoint.yaml`의 host만 Linux/Windows CARLA server로 바꾼다.
- CARLA archive와 extracted runtime은 `data/offline/`에 두되 git에는 commit하지 않는다.
