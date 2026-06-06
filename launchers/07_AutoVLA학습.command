#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AutoVLA(LoRA 생성) 학습 — 진짜 VLA 방식
#   VLM이 추론 텍스트 + action 토큰을 "생성"하도록 LoRA로 SFT한다.
#   1) instruction 데이터셋 생성(build_autovla_dataset.py)
#   2) LoRA 생성 학습(train_autovla_lora.py)
# 03_학습.command(frozen_vlm=특징추출+회귀 head)과는 다른 파이프라인이다.
# 학습은 .conda MPS 파이썬으로 돈다(CrossOver 아님). 이미지가 필요하므로
# /Volumes/DATASET 마운트가 있어야 한다.
# ============================================================

# 입력 데이터/출력.
METADATA_PATH="${METADATA_PATH:-tmp/m10d_final/metadata_scene_balanced_100.jsonl}"
INSTRUCTION_PATH="${INSTRUCTION_PATH:-tmp/autovla/train.jsonl}"
CODEBOOK_PATH="${CODEBOOK_PATH:-tmp/autovla/train.codebook.json}"
OUTPUT_DIR="${OUTPUT_DIR:-checkpoints/m10d_autovla_lora}"
MODEL_PATH="${MODEL_PATH:-data/offline/hf_models/Qwen2.5-VL-3B-Instruct}"
REBUILD_DATASET="${REBUILD_DATASET:-0}"   # 1이면 instruction 데이터 재생성

# 데이터 포맷.
NUM_TOKENS="${NUM_TOKENS:-256}"            # action 코드북 크기(K)
FRAMES_PER_CAMERA="${FRAMES_PER_CAMERA:-1}"  # 1=3카메라 현재프레임(M4 절충)

# 학습 하이퍼파라미터 — M4(M4/32GB/MPS) 실측 기반 튜닝.
#   측정(fp32, batch1, 3장, trainable 626M):
#     이미지 원본(seq1006)=103s/step, 384(seq697)=98s/step, 224(seq301)=24s/step.
#   → 이미지 해상도가 속도 지배 인자(224면 4배 빠름). 배치는 compute-bound라 키워도
#     throughput 안 늘고 메모리만 늘어서 1 고정. fp32 필수(fp16=NaN). 메모리는 약 44GB로
#     32GB를 넘겨 스왑하지만 동작한다. 본격 대규모는 GPU 권장, M4는 MAX_SAMPLES로 규모 조절.
#   소요 시간 ≈ (사용 샘플수) × EPOCHS × (224면 24s).
#   ⚠️ MAX_SAMPLES=0(전체 10000) × 224면 1에폭 ≈ 약 67시간. M4에선 비현실적 → GPU 권장.
DEVICE="${DEVICE:-auto}"
IMAGE_SIZE="${IMAGE_SIZE:-224}"            # 0=원본(느림). 224=4배 빠름(권장). 품질 원하면 384.
MAX_SAMPLES="${MAX_SAMPLES:-0}"           # 0 = 전체 학습데이터 사용
EPOCHS="${EPOCHS:-2}"
BATCH_SIZE="${BATCH_SIZE:-1}"             # MPS compute-bound: 키워도 throughput 불변
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-4}" # 메모리 추가 없이 effective batch 4
LR="${LR:-1e-4}"
LORA_RANK="${LORA_RANK:-8}"
LORA_ALPHA="${LORA_ALPHA:-16}"
LOG_EVERY="${LOG_EVERY:-1}"
# action 토큰 손실 가중(정지/전진 다수 토큰 다운웨이트 → 회전 학습 강제). 1=on.
BALANCE_ACTION_LOSS="${BALANCE_ACTION_LOSS:-1}"
ACTION_WEIGHT_POWER="${ACTION_WEIGHT_POWER:-0.5}"
ACTION_WEIGHT_CAP="${ACTION_WEIGHT_CAP:-5.0}"
# 체크포인트: SAVE_EVERY마다 latest(덮어쓰기, 완전 resume용 optimizer 포함),
# KEEP_EVERY마다 별도 보존(step_NNNNNN, KEEP_LAST개로 회전).
# 주의: 저장 1회가 adapter(embed/lm_head ~2.4GB)+optimizer(~5GB)라 I/O 큼. 너무 잦으면 키울 것.
SAVE_EVERY="${SAVE_EVERY:-10}"
KEEP_EVERY="${KEEP_EVERY:-500}"
KEEP_LAST="${KEEP_LAST:-3}"
# 완전 resume: 멈춘 체크포인트 dir 지정 시 adapter+optimizer+step부터 이어서 학습.
RESUME_FROM="${RESUME_FROM:-}"

# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
PYTHON_BIN="${PYTHON_BIN:-.conda/bin/python}"

if [[ ! -f "$METADATA_PATH" ]]; then
  echo "metadata가 없습니다: $METADATA_PATH"
  exit 1
fi

# instruction 데이터셋 생성 (없거나 REBUILD=1).
if [[ "$REBUILD_DATASET" == "1" || ! -f "$INSTRUCTION_PATH" ]]; then
  echo "Building AutoVLA instruction dataset..."
  echo "  METADATA   : $METADATA_PATH"
  echo "  OUTPUT     : $INSTRUCTION_PATH"
  echo "  NUM_TOKENS : $NUM_TOKENS   FRAMES/CAM: $FRAMES_PER_CAMERA"
  "$PYTHON_BIN" scripts/build_autovla_dataset.py \
    --metadata-path "$METADATA_PATH" \
    --output-path "$INSTRUCTION_PATH" \
    --codebook-path "$CODEBOOK_PATH" \
    --num-tokens "$NUM_TOKENS" \
    --frames-per-camera "$FRAMES_PER_CAMERA"
else
  echo "Reusing instruction dataset: $INSTRUCTION_PATH (REBUILD_DATASET=1로 재생성)"
fi

# 자동 resume: RESUME_FROM이 비어 있어도 OUTPUT_DIR에 체크포인트가 있으면 이어서 학습한다.
# (실수로 그냥 07을 다시 돌려 step1부터 덮어쓰는 사고 방지). 처음부터 새로 하려면 FRESH=1.
if [[ -z "$RESUME_FROM" && "${FRESH:-0}" != "1" && -f "$OUTPUT_DIR/training_state.json" ]]; then
  RESUME_FROM="$OUTPUT_DIR"
  echo "기존 체크포인트 발견 → 자동 resume: $RESUME_FROM (처음부터 하려면 FRESH=1)"
fi
if [[ "${FRESH:-0}" == "1" ]]; then
  RESUME_FROM=""
  echo "FRESH=1 → 처음부터 학습(기존 체크포인트 무시/덮어쓰기)"
fi

# 이미지 마운트 확인(첫 샘플 경로).
FIRST_IMG="$("$PYTHON_BIN" -c "import json;print(json.loads(open('$INSTRUCTION_PATH').readline())['image_paths'][0])" 2>/dev/null || true)"
if [[ -n "$FIRST_IMG" && ! -f "$FIRST_IMG" ]]; then
  echo "경고: 학습 이미지가 없습니다(마운트 확인): $FIRST_IMG"
  echo "/Volumes/DATASET 마운트 후 다시 실행하세요."
  exit 1
fi

SAMPLES_LABEL="$MAX_SAMPLES"
SAMPLE_ARGS=()
if [[ -n "$MAX_SAMPLES" && "$MAX_SAMPLES" != "0" ]]; then
  SAMPLE_ARGS=(--max-samples "$MAX_SAMPLES")
else
  SAMPLES_LABEL="ALL"
fi

echo
echo "Starting AutoVLA LoRA generation SFT..."
echo "  OUTPUT_DIR : $OUTPUT_DIR"
echo "  DEVICE     : $DEVICE"
echo "  MAX_SAMPLES: $SAMPLES_LABEL   EPOCHS: $EPOCHS   BATCH: $BATCH_SIZE x GA $GRAD_ACCUM_STEPS"
echo "  LR         : $LR   LORA r/a: $LORA_RANK/$LORA_ALPHA"
echo "  RESUME_FROM: ${RESUME_FROM:-<none, fresh start>}"
echo

"$PYTHON_BIN" scripts/train_autovla_lora.py \
  --instruction-path "$INSTRUCTION_PATH" \
  --codebook-path "$CODEBOOK_PATH" \
  --num-tokens "$NUM_TOKENS" \
  --model-path "$MODEL_PATH" \
  --output-dir "$OUTPUT_DIR" \
  --device "$DEVICE" \
  --epochs "$EPOCHS" \
  --batch-size "$BATCH_SIZE" \
  --grad-accum-steps "$GRAD_ACCUM_STEPS" \
  --lr "$LR" \
  --lora-rank "$LORA_RANK" \
  --lora-alpha "$LORA_ALPHA" \
  --image-size "$IMAGE_SIZE" \
  --balance-action-loss "$BALANCE_ACTION_LOSS" \
  --action-weight-power "$ACTION_WEIGHT_POWER" \
  --action-weight-cap "$ACTION_WEIGHT_CAP" \
  --save-every "$SAVE_EVERY" \
  --keep-every "$KEEP_EVERY" \
  --keep-last "$KEEP_LAST" \
  --resume-from "$RESUME_FROM" \
  ${SAMPLE_ARGS[@]+"${SAMPLE_ARGS[@]}"} \
  --log-every "$LOG_EVERY"
