# 환경 설정 (Setup)

이 문서는 환경 설정, 하드웨어 역할, 오프라인 다운로드, 120GB 용량 예산을 한 곳에 정리한다. 이 프로젝트는 Anaconda/Miniconda를 기준으로 하며, MacBook 로컬 표준은 Python 3.10이다.

## Conda 정책

- Python version과 environment isolation은 conda로 관리한다.
- PyTorch, Transformers, PEFT, Accelerate, BitsAndBytes, nuScenes devkit은 pip wheelhouse로 설치한다.
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
data/offline/conda_installers/Miniconda3-py310_25.9.1-3-MacOSX-arm64.sh
data/offline/wheels/macos-py310-pinned/      # pinned cp310/macOS arm64 wheelhouse
```

Scale ladder:

```text
MacBook tiny run -> RTX 5090 medium run -> AIP/H100 large run
```

모든 장비에서 pipeline은 같다: CARLA data collection, training, open-loop evaluation, closed-loop evaluation. 바뀌는 것은 route 수, dataset 크기, model 크기, image resolution, training 길이, batch size뿐이다.

정리 기록:

- legacy Python 3.9/latest Miniconda installer와 old `macos-current` wheelhouse는 삭제했다.
- MacBook offline setup에는 Python 3.10 installer와 `macos-py310-pinned` wheelhouse만 유지한다.

## 하드웨어 역할

| 환경 | 역할 | 주요 용도 | 피할 것 |
| --- | --- | --- | --- |
| MacBook | small end-to-end pilot | CARLA smoke data collection, tiny/small training, small evaluation, 문서화, code editing, unit test | 장시간 training, 대규모 route sweep |
| Desktop RTX 5090 | medium-scale execution | 더 큰 CARLA collection, LoRA/QLoRA, 반복 training/evaluation | 10B full fine-tuning |
| Company AIP/H100 x2 | final scale-up | large LoRA, multi-dataset training, ablation | 초기 탐색 |

## MacBook Setup

```bash
brew install git git-lfs ffmpeg
./data/offline/conda_installers/Miniconda3-py310_25.9.1-3-MacOSX-arm64.sh -b -p .conda
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -r requirements.offline.txt
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -e .
```

MacBook 규칙:

- `data/offline`은 120GB 아래로 유지한다.
- 아래 Bundle A를 우선한다.
- CARLA도 MacBook pilot path에 포함된다. 먼저 짧은 route, 낮은 traffic, 낮은 resolution, 짧은 evaluation job으로 실행한다.
- 충분한 용량을 확인하기 전에는 Mac에서 큰 CARLA/dataset archive를 풀지 않는다.
- user home cache에 쓸 수 없을 때는 matplotlib을 import하는 script 실행 시 `MPLCONFIGDIR=.matplotlib_cache`를 설정한다.

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

Memory 규칙:

- MacBook smoke run code path를 그대로 재사용한다.
- batch size 1부터 시작한다.
- bf16을 사용한다.
- LoRA를 먼저 사용한다.
- gradient checkpointing을 켠다.
- 필요하면 4-bit quantization을 사용한다.
- architecture를 바꾸기 전에 image size를 줄인다.
- 10B full fine-tuning으로 시작하지 않는다.

## AIP/H100 진입 기준

Company AIP/H100은 MacBook pilot과 RTX 5090 medium-scale pipeline이 안정된 뒤에만 사용한다.

진입 기준:

- CARLA data collection이 MacBook smoke route와 RTX 5090 medium route에서 모두 동작한다.
- open-loop training/evaluation이 MacBook scale에서 먼저 동작하고, 이후 RTX 5090 scale에서도 동작한다.
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
- quantization/checkpointing을 시도하기 전 단순 OOM 회피

## Offline 저장 구조

대용량 파일은 commit하지 않는다. 아래 위치에 저장한다.

```text
data/offline/
├── conda_installers/
├── conda_envs/
├── wheels/
├── hf_models/
├── simulators/carla/
├── datasets/
│   ├── nuscenes/
│   ├── bench2drive/
│   └── navsim/
└── repos/
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
| 2.2 | target machine용 CARLA runtime | 상황별 다름 | MacBook smoke, RTX 5090 medium, AIP/H100 large run의 첫 closed-loop simulator |
| 2.3 | CARLA PythonAPI wheel/client package | 포함 또는 소용량 | Python script가 CARLA server와 통신하기 위해 필요 |

CARLA note:

- MacBook, RTX 5090, AIP/H100은 모두 같은 pipeline에서 CARLA를 사용한다.
- Linux 전용 CARLA runtime은 desktop으로 옮길 목적이 명확할 때만 Mac에 저장한다.
- 현재 Mac offline cache에는 CARLA AdditionalMaps만 있고, 검증된 Mac CARLA runtime은 없다.

### P3: 작은 dataset

예상 누적 용량: 45-70GB.

| 순서 | 항목 | 예상 용량 | 이유 |
| ---: | --- | ---: | --- |
| 3.1 | nuScenes mini | 약 4GB | schema/open-loop validation |
| 3.2 | Bench2Drive Mini | 약 4GB | benchmark format inspection |
| 3.3 | nuScenes maps/CAN bus small expansion | 1-5GB estimate | conversion/debug 편의 |

### P4: 120GB 안에서 가능한 추가 baseline

예상 누적 용량: 선택에 따라 75-115GB.

| 순서 | 항목 | 예상 용량 | 이유 |
| ---: | --- | ---: | --- |
| 4.1 | Qwen2.5-VL-7B-Instruct | 15-20GB | 두 번째 VLA baseline |
| 4.2 | LLaVA-OneVision Qwen2 7B 또는 NAVSIM baselines 중 선택 | 2-20GB | alternative baseline/reference |
| 4.3 | CARLA AdditionalMaps | 10-20GB estimate | route/weather/map 다양성 |

규칙: P4 항목은 하나씩 추가하고 매번 `./scripts/check_offline_budget.sh`를 실행한다.

### P5: Mac에 받지 말 것

| 항목 | 예상 용량 | 이유 |
| --- | ---: | --- |
| Bench2Drive Base | 약 400GB | Mac 120GB 정책 초과 |
| Bench2Drive Full | 약 4TB | 초기 단계에 부적합 |
| NVIDIA Physical AI Open Dataset | 약 100TB | 초기 project scope 밖 |
| nuScenes full trainval | 큼 | desktop/external storage로 defer |
| Alpamayo large stack | 큼 | teacher/reference phase까지 defer |

## 추천 Bundle

Bundle A, Mac에 안전한 최소 구성, 예상 45-65GB:

```text
papers
docs snapshots
repo clones
Mac Python 3.10 Miniconda installer
Mac Python 3.10 wheelhouse
Qwen2.5-VL-3B
CARLA runtime/client path for MacBook smoke run
nuScenes mini
Bench2Drive Mini
```

Bundle B, 120GB cap 기준 추천 구성, 예상 85-115GB:

```text
Bundle A
Qwen2.5-VL-7B
LLaVA-OneVision Qwen2 7B
NAVSIM baselines
CARLA AdditionalMaps, only if actual file size keeps total under 120GB
```

## Offline 명령

MacBook offline install:

```bash
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -r requirements.offline.txt
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -e .
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

용량 확인:

```bash
./scripts/check_offline_budget.sh
```
