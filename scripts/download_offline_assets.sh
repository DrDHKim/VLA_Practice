#!/usr/bin/env bash
set -euo pipefail

mkdir -p data/offline/wheels
mkdir -p data/offline/hf_models
mkdir -p data/offline/simulators/carla
mkdir -p data/offline/datasets/nuscenes
mkdir -p data/offline/datasets/bench2drive
mkdir -p data/offline/repos

echo "This script is intentionally conservative."
echo "Large dataset downloads are listed in docs/setup.md and should be run manually."

echo "Downloading Python wheels for the current platform..."
echo "For the MacBook smoke environment, prefer data/offline/wheels/macos-py310-pinned from docs/setup.md."
wheel_dir="data/offline/wheels/current"
platform_name="$(uname -s)"
machine_name="$(uname -m)"
python_tag="$(python3 - <<'PY'
import sys
print(f"py{sys.version_info.major}{sys.version_info.minor}")
PY
)"
if [ "$platform_name" = "Darwin" ] && [ "$machine_name" = "arm64" ] && [ "$python_tag" = "py310" ]; then
  wheel_dir="data/offline/wheels/macos-py310-pinned"
fi
python3 -m pip download -d "$wheel_dir" -r requirements.offline.txt

if command -v hf >/dev/null 2>&1; then
  echo "Downloading minimal Hugging Face model bundle..."
  hf download Qwen/Qwen2.5-VL-3B-Instruct --local-dir data/offline/hf_models/Qwen2.5-VL-3B-Instruct
  if [ "${DOWNLOAD_EXTRA_MODELS:-0}" = "1" ]; then
    echo "Downloading extra models. This may exceed the 120GB Mac budget."
    hf download Qwen/Qwen2.5-VL-7B-Instruct --local-dir data/offline/hf_models/Qwen2.5-VL-7B-Instruct
    hf download llava-hf/llava-onevision-qwen2-7b-ov-hf --local-dir data/offline/hf_models/llava-onevision-qwen2-7b-ov-hf
    hf download autonomousvision/navsim_baselines --local-dir data/offline/hf_models/navsim_baselines
  else
    echo "Skipping Qwen2.5-VL-7B, LLaVA-OneVision, and NAVSIM baselines."
    echo "Set DOWNLOAD_EXTRA_MODELS=1 to download them."
  fi
else
  echo "hf command not found. Install huggingface_hub first: python3 -m pip install huggingface_hub"
fi

echo "Mirroring useful repositories..."
if [ ! -d data/offline/repos/navsim ]; then
  git clone https://github.com/autonomousvision/navsim.git data/offline/repos/navsim
fi
if [ ! -d data/offline/repos/Bench2Drive ]; then
  git clone https://github.com/Thinklab-SJTU/Bench2Drive.git data/offline/repos/Bench2Drive
fi
if [ ! -d data/offline/repos/nuscenes-devkit ]; then
  git clone https://github.com/nutonomy/nuscenes-devkit.git data/offline/repos/nuscenes-devkit
fi

echo "Done. Read docs/setup.md for the MacBook -> RTX 5090 -> AIP/H100 scale ladder and CARLA, nuScenes, Bench2Drive, NAVSIM downloads."
./scripts/check_offline_budget.sh || true
