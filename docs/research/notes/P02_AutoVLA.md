# P02 AutoVLA Notes

논문: "AutoVLA: A Vision-Language-Action Model for End-to-End Autonomous Driving with Adaptive Reasoning and Reinforcement Fine-Tuning"  
arXiv: 2506.13757v3 (NeurIPS 2025)  
소속: UCLA

## Inputs

- **Multi-view 카메라**: front, front-left, front-right 3개 RGB 카메라
- **Multi-frame**: 카메라당 4 프레임 (`t-3, t-2, t-1, t`) @ 2Hz → temporal 동적 정보
- **Navigation instruction**: 자연어 방향 명령 (Turn Left, Go Straight 등)
- **Ego state**: 현재 velocity, acceleration, history action 시퀀스

## Backbone

- **Qwen2.5-VL-3B**: open-source VLM, vision encoder + decoder transformer
- 효율성과 성능의 균형으로 선택. onboard device 배포 적합
- SFT 전 단계에서 Qwen2.5-VL-72B가 teacher로 reasoning 데이터 생성 (knowledge distillation)

## Outputs

- **Action token sequence**: `<action_0>` ~ `<action_2047>` 중 10개 token을 autoregressive 생성
- 각 token = 0.5초 단위 이동 → 10 token = 5초 planning horizon
- Token → 실제 trajectory 복원: action codebook lookup
- 부가 출력: CoT reasoning text (slow thinking mode에서만)

## Action Tokenization

- **K-disk clustering**: 연속 trajectory `(∆x, ∆y, ∆θ)` per 0.5s를 K=2048 cluster로 이산화
- 코드북 `A = {a₁, a₂, ..., a₂₀₄₈}` 구성
- `<action_0>` ~ `<action_2047>`을 LLM vocabulary에 추가
- inference: token sequence decode → 5초 trajectory 복원

## Dual Thinking Mode

| Mode | 조건 | 출력 형식 |
|---|---|---|
| Fast thinking | 단순 시나리오 | `<think>` 없이 바로 `<answer><action_x>...` |
| Slow thinking | 복잡 시나리오 | `<think>` 구조적 CoT → `<answer><action_x>...` |

CoT 구조 (slow): 1) Scene description → 2) Critical object → 3) Intent reasoning → 4) Final action

## Training Data

| 데이터셋 | 규모 | 용도 |
|---|---|---|
| nuPlan (Open-Scene) | 120h, 8 cameras | trajectory + CoT 45.6k |
| Waymo E2E | 4,021 segments | trajectory + CoT 7.2k, long-tail |
| nuScenes | 1,000 scenes, 6 cameras | trajectory |
| CARLA-Garage | 500k+ frames | simulation trajectory |
| DriveLM | nuScenes+CARLA VQA | CoT reasoning 보강 |

## Training Stages

### Stage 1 — SFT (Supervised Fine-tuning)

**Loss 함수**:

```
L_LLM = -1/N Σ log p(xᵢ | x<ᵢ, C, I, S)          # 전체 토큰 CE
L_action = -1/T Σ log p(xᵢ | x<ᵢ, C, I, S)         # action 토큰만 CE

L_SFT = w · (L_LLM + λ_a · L_action)
w = λ_cot=40  if CoT in GT,  else 1
```

- λ_a = 1 (action loss 가중치)
- λ_cot = 40 (CoT 샘플에 높은 가중치)
- 8× NVIDIA L40S, FSDP, lr=1e-5, 5 epochs, effective batch=32

### Stage 2 — RFT (Reinforcement Fine-tuning)

- **알고리즘**: GRPO (Group Relative Policy Optimization)
- G개 candidate trajectory 샘플 → group-relative advantage로 정책 업데이트
- **Reward**: `r = r_Driving - λ_r · r_CoT`
  - `r_Driving`: nuPlan → PDMS, Waymo → ADE
  - `r_CoT`: 불필요한 reasoning 길이 패널티
- LoRA adapter만 학습 (parameter-efficient)
- lr=3e-5, β=0.04 (KL regularization), 6,000 steps

## Evaluation

| Benchmark | Metric | AutoVLA Post-RFT |
|---|---|---|
| NAVSIM/nuPlan | PDMS ↑ | 89.11 (vs TrajHF 93.95) |
| nuScenes | L2, Collision | SOTA 수준 |
| Waymo E2E | RFS | 보고됨 |
| Bench2Drive (CARLA) | Success rate, Driving score | closed-loop |

## What to Copy

- **Action tokenization**: K-disk clustering으로 K=256~512 시작 (K=2048은 나중), codebook을 LLM vocab에 추가하는 방식 → Phase C 직접 구현 참고
- **SFT loss 설계**: L_LLM + λ_a·L_action 조합, CoT 샘플에 λ_cot 가중치 → Phase C loss 설계
- **Fast/slow thinking dual mode**: 단순 시나리오는 action만, 복잡하면 CoT → Phase D reasoning 구현 시 참고
- **Knowledge distillation**: 72B teacher → 3B student CoT 생성 파이프라인 → CARLA annotation이 풍부해지면 도입

## What Not to Copy

- **GRPO/RFT**: closed-loop metric이 안정된 뒤에만 도입. MacBook smoke phase에서는 금지
- **72B teacher 모델**: 현재 Mac 환경에서 실행 불가. reasoning annotation은 GPT API나 local 7B로 대체
- **8-camera multi-view**: 현재 front RGB 단일 카메라로 시작. multi-view는 MacBook에서 가능한 단일/소규모 카메라 실험 한계가 확인된 뒤 RTX 5090에서 확장
- **nuPlan 120h 전체**: 현재 CARLA 데이터 우선. nuPlan은 Phase C 이후 검토
