#!/usr/bin/env bash
set -euo pipefail

mkdir -p docs/research/papers

download() {
  local url="$1"
  local out="$2"
  if [ -f "$out" ]; then
    echo "skip $out"
  else
    echo "download $out"
    curl -L --fail --retry 3 "$url" -o "$out"
  fi
}

download "https://arxiv.org/pdf/2503.23463" "docs/research/papers/P01_OpenDriveVLA_2503.23463.pdf"
download "https://arxiv.org/pdf/2506.13757" "docs/research/papers/P02_AutoVLA_2506.13757.pdf"
download "https://arxiv.org/pdf/2511.00088" "docs/research/papers/P03_Alpamayo_R1_2511.00088.pdf"
download "https://arxiv.org/pdf/2511.19912" "docs/research/papers/P04_Reasoning_VLA_2511.19912.pdf"
download "https://arxiv.org/pdf/2402.12289" "docs/research/papers/P05_DriveVLM_2402.12289.pdf"
download "https://arxiv.org/pdf/2310.01412" "docs/research/papers/P06_DriveGPT4_2310.01412.pdf"
download "https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_OmniDrive_A_Holistic_Vision-Language_Dataset_for_Autonomous_Driving_with_Counterfactual_CVPR_2025_paper.pdf" "docs/research/papers/P07_OmniDrive_CVPR2025.pdf"
download "https://openaccess.thecvf.com/content/CVPR2025/papers/Xu_DriveGPT4-V2_Harnessing_Large_Language_Model_Capabilities_for_Enhanced_Closed-Loop_Autonomous_CVPR_2025_paper.pdf" "docs/research/papers/P08_DriveGPT4_V2_CVPR2025.pdf"
download "https://arxiv.org/pdf/2506.24044" "docs/research/papers/P09_VLA_AD_Survey_2506.24044.pdf"
download "https://arxiv.org/pdf/2604.02190" "docs/research/papers/P10_UniDriveVLA_2604.02190.pdf"
download "https://arxiv.org/pdf/2605.11678" "docs/research/papers/S01_OOM_Free_Alpamayo_2605.11678.pdf"
download "https://arxiv.org/pdf/2605.21446" "docs/research/papers/S02_Lost_in_Fog_2605.21446.pdf"
download "https://arxiv.org/pdf/2605.17268" "docs/research/papers/S03_VLA_Reasoning_Faithful_2605.17268.pdf"
