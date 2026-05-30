# Setup

이 문서는 환경 설정, 하드웨어 역할, 오프라인 다운로드, 120GB 용량 예산을 한 곳에 정리한다. 이 프로젝트는 Anaconda/Miniconda를 기준으로 하며, MacBook 로컬 표준은 Python 3.10이다.

## Conda Policy

- Use conda for Python version and environment isolation.
- Use pip wheelhouse for PyTorch, Transformers, PEFT, Accelerate, BitsAndBytes, and nuScenes devkit.
- Do not use the base conda environment.
- Keep one environment per machine role.

Environment names:

```text
vla-drive-mac
vla-drive-5090
vla-drive-aip-h100
```

Current MacBook local environment:

```text
.conda/                                      # project-local Miniconda, Python 3.10.19
data/offline/conda_installers/Miniconda3-py310_25.9.1-3-MacOSX-arm64.sh
data/offline/wheels/macos-py310-pinned/      # pinned cp310/macOS arm64 wheelhouse
```

Scale ladder:

```text
MacBook tiny run -> RTX 5090 medium run -> AIP/H100 large run
```

The pipeline is the same across machines: CARLA data collection, training, open-loop evaluation, and closed-loop evaluation. Only route count, dataset size, model size, image resolution, training length, and batch size should change.

Cleanup note:

- Removed legacy Python 3.9/latest Miniconda installers and the old `macos-current` wheelhouse.
- Keep only the Python 3.10 installer and `macos-py310-pinned` wheelhouse for MacBook offline setup.

## Hardware Profiles

| Environment | Role | Main Use | Avoid |
| --- | --- | --- | --- |
| MacBook | small end-to-end pilot | CARLA smoke data collection, tiny/small training, small evaluation, docs, code editing, unit tests | long training, large route sweeps |
| Desktop RTX 5090 | medium-scale execution | CARLA collection at larger scale, LoRA/QLoRA, repeated training/evaluation | 10B full fine-tuning |
| Company AIP/H100 x2 | final scale-up | large LoRA, multi-dataset training, ablation | early exploration |

## MacBook Setup

```bash
brew install git git-lfs ffmpeg
./data/offline/conda_installers/Miniconda3-py310_25.9.1-3-MacOSX-arm64.sh -b -p .conda
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -r requirements.offline.txt
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -e .
```

MacBook rules:

- Keep `data/offline` under 120GB.
- Prefer Bundle A below.
- CARLA is part of the MacBook pilot path too: run short routes, low traffic, low resolution, and short evaluation jobs first.
- Do not extract large CARLA/dataset archives on the Mac unless enough space is confirmed.
- Set `MPLCONFIGDIR=.matplotlib_cache` when running scripts that import matplotlib if the user home cache is not writable.

## RTX 5090 Setup

Recommended stack:

- Ubuntu 22.04 or 24.04
- NVIDIA driver compatible with RTX 5090
- CUDA 12.x
- Python 3.10 or 3.11
- PyTorch build that supports the installed CUDA/Blackwell stack
- CARLA 0.9.15 or compatible build

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

Validation:

```bash
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
python -c "import transformers; print(transformers.__version__)"
python -m pytest tests/unit
```

Memory rules:

- reuse the MacBook smoke run code path
- start with batch size 1
- use bf16
- use LoRA first
- enable gradient checkpointing
- use 4-bit quantization if needed
- reduce image size before changing architecture
- do not start with 10B full fine-tuning

## AIP/H100 Entry Criteria

Use the company AIP/H100 only after the MacBook pilot and local RTX 5090 medium-scale pipeline are stable.

Entry criteria:

- CARLA data collection works on MacBook smoke routes and RTX 5090 medium routes.
- open-loop training/evaluation works first on MacBook scale, then on RTX 5090 scale.
- closed-loop evaluation works on at least 5 routes before migration.
- exact experiment plan is written in `docs/experiments.md`.
- code snapshot is archived before entering the company environment.
- the team accepts that code cannot be brought back to Mac/5090 after migration.

Intended use:

- large LoRA experiments
- multi-dataset training
- ablations
- Alpamayo/OpenDriveVLA/AutoVLA-scale experiments

Do not use AIP/H100 for:

- initial CARLA debugging
- unstable data schema work
- trial-and-error dependency setup
- simple OOM avoidance before trying quantization/checkpointing

## Offline Storage Layout

Large files are not committed. Store them under:

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

## Download Priority Under 120GB

### P0: Tiny but Critical

Estimated total: below 1GB.

| Order | Item | Estimated Size | Reason |
| ---: | --- | ---: | --- |
| 0.1 | Repository docs and code | already local | Local LLM working baseline |
| 0.2 | Paper PDFs in `docs/research/papers/` | 0.1GB | Research basis, already done |
| 0.3 | Miniconda/Anaconda installers for Mac | 0.1-1GB | Offline conda setup |
| 0.4 | Documentation snapshots | 0.5GB | Offline setup/debug docs |

### P1: Offline Coding and Environment Bootstrap

Estimated cumulative total: 10-20GB.

| Order | Item | Estimated Size | Reason |
| ---: | --- | ---: | --- |
| 1.1 | GitHub repo clones: NAVSIM, Bench2Drive, nuscenes-devkit | 1-3GB | External implementation reference |
| 1.2 | macOS Python 3.10 wheelhouse | about 0.5GB | Mac offline tests and local implementation |
| 1.3 | Linux CUDA wheelhouse | 8-15GB | RTX 5090 offline install, not stored on the Mac unless needed |

### P2: First Model and First Simulator

Estimated cumulative total: 35-60GB.

| Order | Item | Estimated Size | Reason |
| ---: | --- | ---: | --- |
| 2.1 | Qwen2.5-VL-3B-Instruct | 7-10GB | First VLA backbone |
| 2.2 | CARLA runtime for the target machine | varies | First closed-loop simulator for MacBook smoke, RTX 5090 medium, and AIP/H100 large runs |
| 2.3 | CARLA PythonAPI wheel/client package | included or small | Python script execution against the CARLA server |

CARLA note:

- MacBook, RTX 5090, and AIP/H100 all use CARLA in the same pipeline.
- Do not store a Linux-only CARLA runtime on the Mac unless it is specifically needed for transfer to the desktop.
- The current Mac offline cache contains CARLA AdditionalMaps, not a verified Mac CARLA runtime.

### P3: Small Datasets

Estimated cumulative total: 45-70GB.

| Order | Item | Estimated Size | Reason |
| ---: | --- | ---: | --- |
| 3.1 | nuScenes mini | about 4GB | schema/open-loop validation |
| 3.2 | Bench2Drive Mini | about 4GB | benchmark format inspection |
| 3.3 | nuScenes maps/CAN bus small expansions | 1-5GB estimate | conversion/debug convenience |

### P4: Better Baselines Within 120GB

Estimated cumulative total: 75-115GB depending on choices.

| Order | Item | Estimated Size | Reason |
| ---: | --- | ---: | --- |
| 4.1 | Qwen2.5-VL-7B-Instruct | 15-20GB | second VLA baseline |
| 4.2 | Choose one: LLaVA-OneVision Qwen2 7B or NAVSIM baselines | 2-20GB | alternative baseline/reference |
| 4.3 | CARLA AdditionalMaps | 10-20GB estimate | route/weather/map variety |

Rule: add P4 items one at a time and run `./scripts/check_offline_budget.sh`.

### P5: Do Not Download to Mac

| Item | Estimated Size | Reason |
| --- | ---: | --- |
| Bench2Drive Base | about 400GB | exceeds Mac 120GB policy |
| Bench2Drive Full | about 4TB | unsuitable for initial phase |
| NVIDIA Physical AI Open Dataset | about 100TB | outside initial project scope |
| nuScenes full trainval | large | defer to desktop/external storage |
| Alpamayo large stack | large | defer until teacher/reference phase |

## Recommended Bundles

Bundle A, minimal and safe for Mac, estimated 45-65GB:

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

Bundle B, recommended 120GB cap, estimated 85-115GB:

```text
Bundle A
Qwen2.5-VL-7B
LLaVA-OneVision Qwen2 7B
NAVSIM baselines
CARLA AdditionalMaps, only if actual file size keeps total under 120GB
```

## Offline Commands

MacBook offline install:

```bash
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -r requirements.offline.txt
.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -e .
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest
```

MacBook wheel download, only when rebuilding the wheelhouse online:

```bash
.conda/bin/python -m pip download -d data/offline/wheels/macos-py310-pinned -r requirements.offline.txt
```

Linux wheel download, run on the Linux desktop or AIP/H100 target, not on the Mac:

```bash
python3 -m pip download -d data/offline/wheels/linux-x86_64-cu12 -r requirements.offline.txt
```

Linux offline install:

```bash
python3 -m pip install --no-index --find-links data/offline/wheels/linux-x86_64-cu12 -r requirements.offline.txt
```

Hugging Face examples:

```bash
hf download Qwen/Qwen2.5-VL-3B-Instruct --local-dir data/offline/hf_models/Qwen2.5-VL-3B-Instruct
hf download Qwen/Qwen2.5-VL-7B-Instruct --local-dir data/offline/hf_models/Qwen2.5-VL-7B-Instruct
```

Budget check:

```bash
./scripts/check_offline_budget.sh
```
