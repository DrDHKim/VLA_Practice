# Research

조사 기준일: 2026-05-29. PDF는 `docs/research/papers/`에 저장한다. 논문별 오프라인 요약은 `docs/research/notes/`에 둔다.

## Model Selection

처음 구현은 `Qwen2.5-VL/LLaVA style VLM + waypoint regression head + CARLA PID controller`로 시작한다. OpenDriveVLA와 AutoVLA는 구조를 참고하되, 공개 구현이 안정화되기 전까지 그대로 복제하지 않는다.

선택 이유:

- RTX 5090 32GB에서 LoRA/QLoRA 실험이 가능해야 한다.
- MacBook에서 CARLA 데이터 수집-작은 학습-작은 평가 smoke run이 가능해야 한다.
- closed-loop driving에서는 action token을 바로 control로 내는 것보다 future waypoint를 예측하고 controller로 변환하는 편이 디버깅 가능하다.
- reasoning text는 안전 검증 수단이지, 초기 제어 루프의 필수 조건이 아니다.
- AIP/H100은 irreversible environment로 취급해야 하므로, MacBook/RTX 5090에서 데이터/평가/학습 코드가 안정되기 전에는 쓰지 않는다.

Baseline:

```text
front/multiview image
ego state
route command text
      |
      v
VLM backbone
      |
      v
pooled hidden state
      |
      v
waypoint head -> future waypoints in ego frame
      |
      v
PID/MPC controller -> steer/throttle/brake
```

Default first run:

- image size: 384 or 448 px long side
- horizon: 4 seconds
- waypoint interval: 0.5 seconds
- waypoint count: 8
- loss: L1 waypoint loss + final displacement loss
- optimizer: AdamW
- precision: fp32/MPS-safe mode on MacBook smoke run, bf16 on RTX 5090
- fine-tuning: freeze backbone first on MacBook; LoRA rank 8 or 16 on RTX 5090
- batch size: start with 1 on MacBook, 1-4 on RTX 5090, accumulate gradients

Reject for now:

- full fine-tuning 10B models
- direct steer/throttle/brake-only imitation as the first model
- unverified chain-of-thought as a safety signal
- moving to AIP/H100 before CARLA data collection, training, and evaluation work on MacBook and RTX 5090

## Must Read Papers

| ID | Paper | Year | Why it matters | URL |
| --- | --- | --- | --- | --- |
| P01 | OpenDriveVLA: Towards End-to-end Autonomous Driving with Large Vision Language Action Model | 2025 | 1차 구조 참고. 2D/3D visual tokens, ego state, driver command를 VLA로 연결 | https://arxiv.org/abs/2503.23463 |
| P02 | AutoVLA: A Vision-Language-Action Model for End-to-End Autonomous Driving with Adaptive Reasoning and Reinforcement Fine-Tuning | 2025 | fast/slow reasoning, trajectory tokenization, GRPO fine-tuning 참고 | https://arxiv.org/abs/2506.13757 |
| P03 | Alpamayo-R1: Bridging Reasoning and Action Prediction for Generalizable Autonomous Driving in the Long Tail | 2025 | NVIDIA open reasoning VLA. 대형 teacher/baseline 후보 | https://arxiv.org/abs/2511.00088 |
| P04 | Reasoning-VLA: A Fast and General Vision-Language-Action Reasoning Model for Autonomous Driving | 2025 | learnable action query와 multi-dataset CoT format 참고 | https://arxiv.org/abs/2511.19912 |
| P05 | DriveVLM: The Convergence of Autonomous Driving and Large Vision-Language Models | 2024 | VLM reasoning + 기존 AD stack hybrid 설계 참고 | https://arxiv.org/abs/2402.12289 |
| P06 | DriveGPT4: Interpretable End-to-end Autonomous Driving via Large Language Model | 2023/2024 | driving video instruction tuning, interpretable control 예시 | https://arxiv.org/abs/2310.01412 |
| P07 | OmniDrive: A Holistic Vision-Language Dataset for Autonomous Driving with Counterfactual Reasoning | 2025 | AD QA/reasoning 데이터 설계 참고 | https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_OmniDrive_A_Holistic_Vision-Language_Dataset_for_Autonomous_Driving_with_Counterfactual_CVPR_2025_paper.pdf |
| P08 | DriveGPT4-V2: Harnessing Large Language Model Capabilities for Enhanced Closed-Loop Autonomous Driving | 2025 | closed-loop VLM driving 개선 방향 참고 | https://openaccess.thecvf.com/content/CVPR2025/papers/Xu_DriveGPT4-V2_Harnessing_Large_Language_Model_Capabilities_for_Enhanced_Closed-Loop_Autonomous_CVPR_2025_paper.pdf |
| P09 | A Survey on Vision-Language-Action Models for Autonomous Driving | 2025 | 전체 taxonomy와 누락된 관련 연구 확인 | https://arxiv.org/abs/2506.24044 |
| P10 | UniDriveVLA: Unifying Understanding, Perception, and Action Planning for Autonomous Driving | 2026 | 최신 unified VLA 방향. Bench2Drive closed-loop 참고 | https://arxiv.org/abs/2604.02190 |

## Practical / Systems Papers

| ID | Paper | Why it matters | URL |
| --- | --- | --- | --- |
| S01 | OOM-Free Alpamayo via CPU-GPU Memory Swapping for Vision-Language-Action Models | RTX 5090/16-32GB급 GPU에서 Alpamayo inference/offload 참고 | https://arxiv.org/abs/2605.11678 |
| S02 | Lost in Fog: Sensor Perturbations Expose Reasoning Fragility in Driving VLAs | VLA robustness 평가 시나리오 참고 | https://arxiv.org/abs/2605.21446 |
| S03 | Is VLA Reasoning Faithful? Probing Safety of Chain-of-Causation | reasoning이 실제 action과 일치하는지 평가하는 기준 참고 | https://arxiv.org/abs/2605.17268 |

## Reading Order

1. P09 survey로 용어와 taxonomy 확인
2. P05/P06으로 VLM 기반 AD의 초기 문제 이해
3. P01/P02로 구현 구조 결정
4. P03/P04/P10으로 최신 reasoning/action 설계 파악
5. S01/S02/S03으로 메모리와 안전성 평가 보강

## Notes for Offline Work

- 각 논문은 `docs/research/notes/<paper_id>_<short_name>.md`에 1페이지 요약을 남긴다.
- 요약에는 `Inputs`, `Outputs`, `Training Data`, `Action Representation`, `Evaluation`, `What to copy`, `What not to copy`를 포함한다.
- Qwen3 Coder는 논문 PDF를 직접 다 읽기 어렵다면 notes 파일부터 읽는다.
