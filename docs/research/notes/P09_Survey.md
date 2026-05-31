# P09 VLA4AD Survey Notes

논문: "A Survey on Vision-Language-Action Models for Autonomous Driving"  
arXiv: 2506.24044v1 (2025)  
소속: McGill, Tsinghua, Wisconsin-Madison 등

## VLA4AD 발전 4단계

```
Stage 1: VLM as Explainer
         → 언어로 scene 설명, 실제 제어는 PID가 담당

Stage 2: Modular VLA
         → 언어 → 중간 표현(waypoint/meta-action) → action head → trajectory
         ← 우리 현재 위치 (M1~M6 완료)

Stage 3: End-to-end VLA
         → 단일 unified network, sensor → trajectory (single forward pass)
         ← 우리 다음 목표 (Phase B~C)

Stage 4: Reasoning-augmented VLA
         → CoT + 장기 memory + tool use + GRPO
         ← Phase D 이후 (closed-loop 안정 후)
```

## 각 단계 특징

### Stage 1: Explainer
- 대표: DriveGPT-4, CLIP+LLM → 텍스트 scene description
- 제어는 완전히 분리된 PID/MPC
- 한계: 언어와 action 사이 semantic gap, 지연 발생

### Stage 2: Modular VLA
- 대표: OpenDriveVLA, CoVLA-Agent, RAG-Driver
- 언어 → 중간 표현(human-readable waypoints, meta-action) → action head
- 멀티-스테이지 파이프라인: 에러 누적, 지연 위험
- 우리 현재 구현: RGB + ego state → DummyBackbone → WaypointHead → PID

### Stage 3: End-to-end VLA
- 대표: EMMA, AutoVLA, LMDrive, CarLLaVA, DiffVLA
- 단일 네트워크, sensor → trajectory (single differentiable path)
- CARLA에서 DriveLM, LMDrive 등 closed-loop 검증
- 한계: 장기 reasoning, fine-grained 설명 어려움

### Stage 4: Reasoning-augmented VLA
- 대표: ORION (QTFormer memory), AutoVLA (CoT+GRPO), Impromptu VLA
- CoT verbalization + long-horizon memory + GRPO 강화학습
- 과제: city-scale memory, 30Hz 이내 LLM reasoning, language-conditioned policy 검증

## 아키텍처 표준 구성

```
Multimodal Input
    ↓
[Vision Encoder]      DINOv2 / CLIP ViT / ConvNeXt-V2
    ↓
[Language Processor]  LLaMA-2 / GPT-style / LoRA-adapted
    ↓
[Action Decoder]      Autoregressive tokenizer / Diffusion head / MLP
    ↓
Output: LLC / Trajectory / Multi-task
```

**LoRA**: 표준 적용법. rank-low adapter로 VLM efficient fine-tuning

## 입력 분류

| 카테고리 | 종류 | 우리 현재 |
|---|---|---|
| Visual | single/multi-view cameras, LiDAR, BEV | front RGB 1대 |
| Ego state | velocity, acceleration, history actions | speed + route_command |
| Language | navigation command, VQA, CoT | route_command string |

## 출력 분류

| 카테고리 | 예시 | 우리 현재 |
|---|---|---|
| Low-Level Control (LLC) | steer, throttle, brake | M6에서 PID로 변환 |
| Trajectory | waypoints in ego/BEV frame | [B, T, 2] |
| Multi-task | perception + prediction + planning | Phase D 이후 |

## 벤치마크 정리

| 벤치마크 | 데이터 | 핵심 metric |
|---|---|---|
| nuScenes | 1k episodes, 6 cams, Boston/Singapore | L2 1/2/3s, Collision |
| NAVSIM/nuPlan | 120h real-world | PDMS (safety+comfort+progress) |
| Waymo E2E | 4k segments, long-tail | RFS (human-judged quality) |
| Bench2Drive | 44 CARLA scenarios, 220 routes | Success rate, Driving score |
| BDD100K/BDD-X | 100k diverse US videos + rationales | 설명 품질 포함 |

## 우리 프로젝트 위치 매핑

| Milestone | Survey 단계 |
|---|---|
| M1~M6 (완료) | Stage 2 Modular VLA의 최소 구현 |
| Phase B (VLM backbone) | Stage 2→3 전환 시작: Qwen2.5-VL-3B로 진짜 VLM 사용 |
| Phase C (action tokenizer) | Stage 3 End-to-end VLA: autoregressive action token 생성 |
| Phase D (reasoning, GRPO) | Stage 4 Reasoning-augmented VLA |

## What to Copy

- **4단계 ladder를 명확히 유지**: 단계를 건너뛰지 않는다. Modular가 검증된 뒤 End-to-end로
- **LoRA** = 표준 fine-tuning 방식. 논문들이 모두 사용
- **Waypoint → PID** = Stage 2의 표준 출력 패턴, 현재 구현과 일치
- **CARLA Bench2Drive** metric: closed-loop 평가 시 success rate와 driving score 기준

## What Not to Copy

- **BEV projection, LiDAR, multi-sensor fusion**: 당장 불필요. front RGB 단일부터
- **city-scale memory bank (ORION 방식)**: Phase D 이후 검토
- **30Hz real-time constraint**: 연구 단계에서는 offline 평가 우선
