# 환경 설정 (Setup)

이 문서는 환경 설정, 하드웨어 역할, 오프라인 다운로드, 120GB 용량 예산을 한 곳에 정리한다. 이 프로젝트는 Anaconda/Miniconda를 기준으로 하며, MacBook 로컬 표준은 Python 3.10이다.

## Conda 정책

- Python version과 environment isolation은 conda로 관리한다.
- PyTorch, Transformers, PEFT, Accelerate 등 Python dependency는 현재 `.conda` environment에 설치되어 있다.
- base conda environment는 사용하지 않는다.
- 장비 역할별로 environment를 분리한다.

Environment 이름:

```text
vla-drive-mac
vla-drive-5090
vla-drive-aip-h100
```

현재 MacBook 로컬 environment:

```text
.conda/                                      # project-local Miniconda, Python 3.10.19
data/offline/hf_models/Qwen2.5-VL-3B-Instruct/
data/offline/simulators/carla/
```

Scale ladder:

```text
MacBook 가능한 최대 검증 -> MacBook 리소스 한계 기록 -> RTX 5090 확장
RTX 5090 가능한 최대 검증 -> RTX 5090 리소스 한계 기록 -> AIP/H100 확장
```

모든 장비에서 pipeline은 같다: CARLA data collection, training, open-loop evaluation, closed-loop evaluation. 장비가 바뀌어도 code path를 바꾸지 않고 route 수, dataset 크기, model 크기, image resolution, training 길이, batch size만 조정한다. 다음 장비로 넘어가는 이유는 항상 리소스 한계 또는 명확한 대규모 실험 필요성으로 남긴다.

정리 기록:

- 설치가 완료된 `.conda`는 유지한다.
- 설치용 conda installer/wheelhouse, 외부 dataset/repo, 추가 대형 model은 launcher 미연결 자산 정리 과정에서 삭제했다.

## 하드웨어 역할

| 환경 | 역할 | 주요 용도 | 피할 것 |
| --- | --- | --- | --- |
| MacBook | 기본 개발/검증 장비 | CARLA data collection, CPU/MPS-safe training, open/closed-loop evaluation, 문서화, code editing, unit test | 리소스 한계 기록 없이 5090으로 넘기기, 10B full fine-tuning |
| Desktop RTX 5090 | MacBook 한계 이후 확장 장비 | 더 큰 CARLA collection, LoRA/QLoRA, 반복 training/evaluation, 큰 image/model/batch 검증 | MacBook에서 가능한 축소/최적화 실험 건너뛰기, 10B full fine-tuning |
| Company AIP/H100 x2 | RTX 5090 한계 이후 최종 확장 | large LoRA/QLoRA, multi-dataset training, ablation, teacher/reference run | 초기 탐색, 단순 편의성 때문에 사용 |

## MacBook Setup

```bash
brew install git git-lfs ffmpeg
.conda/bin/python -m pip check
.conda/bin/python -m pip install -e .
```

MacBook 규칙:

- `data/offline`은 120GB 아래로 유지한다.
- 현재 launcher 필수 구성만 유지한다.
- CARLA도 MacBook pilot path에 포함된다. 공식 지원 경로는 Linux/Windows server 또는 remote host지만, 이 Mac에서는 CrossOver 64-bit bottle + D3DMetal로 Windows CARLA 0.9.15 server 실행, `127.0.0.1:2000` port open, RGB camera frame까지 검증했다. 재현 절차는 `docs/carla_mac_setup.md`를 따른다.
- Mac에서 먼저 가능한 route 수, image resolution, sample 수, tiny/small training, open/closed-loop 평가를 모두 시도한다.
- Mac 리소스 한계가 나오면 batch size, image size, route length, traffic density, model size, LoRA rank, frozen backbone, CPU/MPS-safe mode를 줄여 다시 시도한다.
- 그래도 불가능한 경우에만 5090 전환 사유를 연구일지 또는 `docs/experiments.md`에 남긴다.
- 충분한 용량을 확인하기 전에는 Mac에서 큰 CARLA/dataset archive를 풀지 않는다.
- user home cache에 쓸 수 없을 때는 matplotlib을 import하는 script 실행 시 `MPLCONFIGDIR=.matplotlib_cache`를 설정한다.

MacBook readiness check:

```bash
.conda/bin/python scripts/check_mac_readiness.py
```

현재 이 Mac 기준으로 주의할 점:

- disk: 2026-06-07 정리 후 `data/offline`은 약 25GiB다. CARLA log/checkpoint를 고려해 최소 40GiB free space를 유지한다.
- Python: project-local `.conda`는 Python 3.10.19이며 현재 표준과 일치한다.
- system tools: 현재 `git-lfs`, `ffmpeg`, `cmake`가 PATH에 없다. offline coding 자체는 가능하지만 dataset/repo LFS 처리, video export, native build fallback에는 필요하다.
- torch/MPS: 현재 process에서는 `torch.backends.mps.is_available()`가 false다. 이 상태에서는 MacBook training/evaluation을 CPU smoke mode로 먼저 통과시키고, local Terminal에서 MPS가 true로 확인될 때만 MPS path를 켠다.
- CARLA: Mac local server는 `docs/carla_mac_setup.md`의 CrossOver/D3DMetal path로 RGB camera까지 검증했다. `carla` Python package는 macOS native process에서 import하지 않고 CrossOver bottle 내부 Windows Python 3.7과 CARLA egg를 사용한다.
- bitsandbytes: Mac에서는 CUDA quantization 경로로 쓰지 않는다. MacBook은 frozen backbone, CPU/MPS-safe mode, 작은 batch로만 검증한다.

MacBook 문제별 해결책:

| 문제 | 증상 | 해결 |
| --- | --- | --- |
| `git-lfs` 없음 | 외부 repo나 dataset pointer만 받고 실제 파일이 없음 | `brew install git-lfs && git lfs install`을 online에서 실행한다. offline 환경이면 LFS object까지 포함된 archive를 미리 받는다. |
| `ffmpeg` 없음 | episode video export 또는 debug clip 생성 실패 | `brew install ffmpeg`를 online에서 실행한다. 필수 구현은 image sequence/JSONL만으로 먼저 진행한다. |
| `cmake` 없음 | wheel 없는 native package build 실패 | `brew install cmake`를 online에서 실행한다. 기본 작업은 pinned wheelhouse만 사용하므로 당장 blocking은 아니다. |
| MPS unavailable | torch는 설치됐지만 MPS가 false | CPU smoke mode를 기본값으로 사용한다. training config는 `device: auto` 대신 `cpu` fallback을 허용한다. |
| CARLA server/runtime 문제 | simulator 실행 불가 또는 `import carla` 실패 | Mac local server는 `docs/carla_mac_setup.md`로 재설치한다. Mac native Python 대신 CrossOver bottle 내부 Windows Python 3.7을 사용한다. |
| disk pressure | free space 40GiB 미만 또는 offline cache 120GB 초과 | launcher에 연결되지 않은 선택 asset을 조사하고 승인 후 제거한다. |
| matplotlib cache permission | plot/eval script에서 cache 경고 또는 실패 | `MPLCONFIGDIR=.matplotlib_cache`를 붙여 실행한다. |
| offline wheel 누락 | offline pip install 실패 | online 환경에서 `requirements.offline.txt` 기준으로 `macos-py310-pinned` wheelhouse를 다시 만든다. |

추가 설치/다운로드 판단:

| 우선순위 | 항목 | 현재 상태 | 조치 |
| ---: | --- | --- | --- |
| P0 | project-local `.conda` | 준비됨, `pip check` 통과 | 유지 |
| P0 | Qwen2.5-VL-3B | 준비됨 | 추가 다운로드 불필요 |
| P1 | `git-lfs` | 미설치 | online일 때 Homebrew로 설치 |
| P1 | `ffmpeg` | 미설치 | video export가 필요해지기 전에 설치 |
| P2 | CARLA base runtime | Mac local server와 RGB camera 검증됨 | `docs/carla_mac_setup.md`와 `scripts/run_carla_mac_crossover.sh` 사용 |
| P2 | CARLA Python client import path | macOS native `carla` import는 사용하지 않음 | CrossOver bottle 내부 Windows Python 3.7과 CARLA egg를 사용한다. |
| P3 | 외부 dataset/repo | 제거됨 | launcher 경로를 정의한 뒤 필요할 때 다시 준비 |
| P4 | Qwen 7B/LLaVA/NAVSIM baselines | 제거됨 | 현재 launcher에는 불필요 |

### Mac에서 CARLA 직접 실행

공식 문서 기준으로 CARLA server는 Linux/Windows가 지원 대상이다. 다만 이 Mac에서는 CrossOver 64-bit bottle + D3DMetal로 Windows CARLA 0.9.15 server 실행, RPC port open, RGB camera frame까지 확인했다. 설치 절차는 `docs/carla_mac_setup.md`, 실행은 `scripts/run_carla_mac_crossover.sh`를 따른다.

Option A, 안정 경로:

```text
MacBook Python client -> remote CARLA server on Linux/Windows/RTX 5090
```

장점: official CARLA path와 가장 가깝고, ROS/Bench2Drive/NAVSIM 확장도 쉽다.

Option B, Mac 단독 experimental path:

```text
CrossOver 64-bit bottle + D3DMetal -> WindowsNoEditor/CarlaUE4.exe -> bottle 내부 PythonAPI
```

필요 항목:

- CrossOver 26.x
- Windows CARLA release archive, 예: `WindowsNoEditor`
- 64-bit bottle: `carla-rgb64`
- D3DMetal enabled
- Windows Python 3.7 x64 for CARLA 0.9.15 Windows PythonAPI egg
- 실행 flag: `-quality-level=Epic`, `-windowed`, `-carla-rpc-port=2000`

주의:

- community PDF 기준 M4/24GB에서는 CARLA 0.9.15가 동작한 사례가 있고, M1 Pro/16GB에서는 0.9.15+ rendering 실패 사례가 있다.
- 같은 discussion에서 ROS는 Wine 내부에서 잘 안 맞는다고 보고되어 있다. ROS가 필요하면 remote Linux server가 더 낫다.
- Python client를 macOS native process에서 바로 쓰지 않는다. CrossOver bottle 내부 Python을 사용한다.
- 이 경로는 reproducibility가 낮으므로 RTX 5090/AIP에서는 Linux/Windows official path를 계속 우선한다.

참고:

- CARLA official build docs: https://carla.readthedocs.io/en/0.9.15/build_carla/
- CARLA macOS maintainer comment: https://github.com/carla-simulator/carla/discussions/8563
- Apple Silicon Kegworks/Wine workaround: https://github.com/carla-simulator/carla/discussions/9037
- Community PDF: https://github.com/user-attachments/files/21182231/CARLA.Server.on.Apple.Silicon.Mac.pdf

## RTX 5090 Setup

권장 stack:

- Ubuntu 22.04 또는 24.04
- RTX 5090과 호환되는 NVIDIA driver
- CUDA 12.x
- Python 3.10 또는 3.11
- 설치된 CUDA/Blackwell stack을 지원하는 PyTorch build
- CARLA 0.9.15 또는 호환 build

```bash
conda create -n vla-drive-5090 python=3.10 pip -y
conda activate vla-drive-5090
python -m pip install -r requirements.offline.txt
```

Offline install:

```bash
conda activate vla-drive-5090
python -m pip install --no-index --find-links data/offline/wheels/linux-x86_64-cu12 -r requirements.offline.txt
```

CARLA Python API:

```bash
conda activate vla-drive-5090
python -m pip install /path/to/CARLA_0.9.15/PythonAPI/carla/dist/*.whl
```

검증:

```bash
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
python -c "import transformers; print(transformers.__version__)"
python -m pytest tests/unit
```

첫 5090 smoke command set:

```bash
conda activate vla-drive-5090
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
MPLCONFIGDIR=.matplotlib_cache python -m pytest -m 'not slow'

python scripts/collect_carla_data.py \
  --config src/vla_drive/configs/carla_rgb_waypoint.yaml \
  --output-root /data/vla_drive/carla/e07_5090_smoke

STAGE=reasoning_aux \
METADATA_PATH=/data/vla_drive/carla/e07_5090_smoke/metadata.jsonl \
EPOCHS=5 MAX_SAMPLES=200 BATCH_SIZE=4 IMAGE_SIZE=128 DEVICE=cuda \
CHECKPOINT_DIR=checkpoints/e07_5090_reasoning_aux \
LOG_DIR=outputs/logs/e07_5090_reasoning_aux \
scripts/train_lora.sh

CARLA_HOST=127.0.0.1 CARLA_PORT=2000 ROUTE_COUNT=5 ROUTE_SECONDS=20 \
REPORT_PATH=outputs/reports/e07_5090_closed_loop.json \
scripts/eval_carla.sh
```

LoRA smoke는 위 reasoning_aux path가 통과한 뒤 실행한다.

```bash
STAGE=lora_vlm \
METADATA_PATH=/data/vla_drive/carla/e07_5090_smoke/metadata.jsonl \
EPOCHS=1 MAX_SAMPLES=64 BATCH_SIZE=1 IMAGE_SIZE=224 DEVICE=cuda \
CHECKPOINT_DIR=checkpoints/e07_5090_lora \
LOG_DIR=outputs/logs/e07_5090_lora \
scripts/train_lora.sh
```

Memory 규칙:

- MacBook에서 리소스 한계가 확인된 code path를 그대로 재사용한다.
- batch size 1부터 시작한다.
- bf16을 사용한다.
- LoRA를 먼저 사용한다.
- gradient checkpointing을 켠다.
- 필요하면 4-bit quantization을 사용한다.
- architecture를 바꾸기 전에 image size를 줄인다.
- RTX 5090에서도 리소스 한계가 나오면 batch/model/data 규모 축소와 offload/quantization을 먼저 시도하고, 그 뒤에만 H100 전환을 검토한다.
- 10B full fine-tuning으로 시작하지 않는다.

## AIP/H100 진입 기준

Company AIP/H100은 MacBook과 RTX 5090에서 가능한 실험을 모두 시도하고, RTX 5090 리소스 한계가 기록된 뒤에만 사용한다.

진입 기준:

- CARLA data collection이 MacBook에서 가능한 최대 범위와 RTX 5090 확장 범위에서 모두 동작한다.
- open-loop training/evaluation이 MacBook에서 가능한 범위까지 먼저 동작하고, 이후 RTX 5090 scale에서도 동작한다.
- RTX 5090에서 gradient checkpointing, quantization, CPU offload, batch/image/model 축소를 시도했다.
- RTX 5090의 한계 또는 H100이 필요한 실험 목적이 report로 남아 있다.
- migration 전에 closed-loop evaluation이 최소 5개 route에서 동작한다.
- 정확한 experiment plan이 `docs/experiments.md`에 기록되어 있다.
- 회사 환경에 들어가기 전 code snapshot을 archive한다.
- 회사 환경으로 들어간 뒤 code를 Mac/5090으로 다시 가져올 수 없다는 운영 리스크를 수용한다.

AIP/H100 용도:

- large LoRA experiment
- multi-dataset training
- ablation
- Alpamayo/OpenDriveVLA/AutoVLA-scale experiment

AIP/H100에 쓰지 말 것:

- 초기 CARLA debugging
- 불안정한 data schema 작업
- 시행착오성 dependency setup
- MacBook/RTX 5090에서 가능한 축소 실험을 하기 전 단순 OOM 회피

## Offline 저장 구조

대용량 파일은 commit하지 않는다. 현재 유지 구조는 아래와 같다.

```text
data/offline/
├── hf_models/Qwen2.5-VL-3B-Instruct/
└── simulators/carla/
```

## 120GB 기준 다운로드 우선순위

### P0: 작지만 필수

예상 누적 용량: 1GB 미만.

| 순서 | 항목 | 예상 용량 | 이유 |
| ---: | --- | ---: | --- |
| 0.1 | repository docs and code | 이미 local | Local LLM 작업 기준 |
| 0.2 | `docs/research/papers/`의 paper PDF | 0.1GB | research basis, 완료됨 |
| 0.3 | Mac용 Miniconda/Anaconda installer | 0.1-1GB | offline conda setup |
| 0.4 | documentation snapshot | 0.5GB | offline setup/debug 문서 |

### P1: Offline coding과 environment bootstrap

예상 누적 용량: 10-20GB.

| 순서 | 항목 | 예상 용량 | 이유 |
| ---: | --- | ---: | --- |
| 1.1 | GitHub repo clone: NAVSIM, Bench2Drive, nuscenes-devkit | 1-3GB | 외부 구현 참고 |
| 1.2 | macOS Python 3.10 wheelhouse | 약 0.5GB | Mac offline test와 local implementation |
| 1.3 | Linux CUDA wheelhouse | 8-15GB | RTX 5090 offline install. Mac에는 필요할 때만 저장 |

### P2: 첫 model과 첫 simulator

예상 누적 용량: 35-60GB.

| 순서 | 항목 | 예상 용량 | 이유 |
| ---: | --- | ---: | --- |
| 2.1 | Qwen2.5-VL-3B-Instruct | 7-10GB | 첫 VLA backbone |
| 2.2 | target server용 CARLA runtime | Mac local 약 25-35GB | MacBook local run과 리소스 한계 이후 RTX 5090/AIP 확장의 첫 closed-loop simulator |
| 2.3 | CARLA PythonAPI wheel/client package | 포함 또는 소용량 | Python script가 CARLA server와 통신하기 위해 필요 |

CARLA note:

- MacBook, RTX 5090, AIP/H100은 모두 같은 pipeline에서 CARLA를 사용한다.
- MacBook은 CARLA client/control/data schema run을 맡고, local CrossOver/D3DMetal server에서 가능한 범위까지 수행한다. 한계가 확인되면 Linux/Windows remote server에 연결한다.
- Linux 전용 CARLA runtime은 desktop/server로 옮길 목적이 명확할 때만 Mac에 저장한다.
- 현재 Mac offline cache에는 Windows CARLA 0.9.15 runtime이 있고, local Wine server는 port open까지 검증했다.

### P3: 작은 dataset (현재 제거됨)

예상 누적 용량: 45-70GB.

| 순서 | 항목 | 예상 용량 | 이유 |
| ---: | --- | ---: | --- |
| 3.1 | nuScenes mini | 약 4GB | schema/open-loop validation |
| 3.2 | Bench2Drive Mini | 약 4GB | benchmark format inspection |
| 3.3 | nuScenes maps/CAN bus small expansion | 1-5GB estimate | conversion/debug 편의 |

### P4: Mac에서 사용하는 추가 baseline (현재 제거됨)

| 순서 | 항목 | 예상 용량 | 상태 |
| ---: | --- | ---: | --- |
| 4.1 | Qwen2.5-VL-7B-Instruct | 15GB | 제거됨 |
| 4.2 | LLaVA-OneVision Qwen2 7B | 15GB | 제거됨 |
| 4.3 | NAVSIM baselines | 3.8GB | 제거됨 |

note: 추가 대형 model은 현재 제거 상태다. 다시 도입할 때도 10B full fine-tuning은 금지한다.

### P5: Mac에 받지 말 것

| 항목 | 예상 용량 | 이유 |
| --- | ---: | --- |
| Bench2Drive Base | 약 400GB | Mac 120GB 정책 초과 |
| Bench2Drive Full | 약 4TB | 초기 단계에 부적합 |
| NVIDIA Physical AI Open Dataset | 약 100TB | 초기 project scope 밖 |
| nuScenes full trainval | 큼 | desktop/external storage로 defer |
| Alpamayo large stack | 큼 | teacher/reference phase까지 defer |

## 추천 Bundle

현재 Mac launcher 필수 구성:

```text
papers
.conda
Qwen2.5-VL-3B
CARLA runtime + CrossOver Python prefix
```

## Offline 명령

현재 environment 검증:

```bash
.conda/bin/python -m pip check
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest
```

MacBook wheelhouse를 online에서 다시 만들 때만 실행:

```bash
.conda/bin/python -m pip download -d data/offline/wheels/macos-py310-pinned -r requirements.offline.txt
```

Linux wheel download는 Linux desktop 또는 AIP/H100 target에서 실행한다. Mac에서 실행하지 않는다.

```bash
python3 -m pip download -d data/offline/wheels/linux-x86_64-cu12 -r requirements.offline.txt
```

Linux offline install:

```bash
python3 -m pip install --no-index --find-links data/offline/wheels/linux-x86_64-cu12 -r requirements.offline.txt
```

Hugging Face 예시:

```bash
hf download Qwen/Qwen2.5-VL-3B-Instruct --local-dir data/offline/hf_models/Qwen2.5-VL-3B-Instruct
hf download Qwen/Qwen2.5-VL-7B-Instruct --local-dir data/offline/hf_models/Qwen2.5-VL-7B-Instruct
```

용량 확인은 `du -sh data/offline/* checkpoints/*`로 수행한다.
