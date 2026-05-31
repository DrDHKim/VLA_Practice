# P01 OpenDriveVLA Notes

논문: "OpenDriveVLA: Towards End-to-end Autonomous Driving with Large Vision Language Action Model"  
arXiv: 2503.23463v2 (2025)  
소속: TU Munich

## Inputs

- **Multi-view 이미지**: 여러 카메라 뷰에서 2D feature 추출 → BEV feature 생성
- **3D 구조화 visual token 3종**:
  - `vscene`: Global Scene Sampler, 2D feature에서 전체 scene context
  - `vagent`: Agent QueryTransformer, BEV에서 dynamic agent 감지/추적 (N_a개)
  - `vmap`: Map QueryTransformer, BEV에서 lane/drivable area 등 static 구조
- **Ego state**: ego vehicle 상태 (속도, 위치 등)를 텍스트로 변환해 LLM 입력
- **High-level command**: 자연어 명령 (예: "turn right at the church")

## Outputs

- **Waypoint sequence**: ego frame 기준 2D 좌표 `(x, y)` × T timestep
- Waypoint를 **discrete text token으로 변환** 후 LLM이 autoregressive 생성
- 생성된 token → Decoder → 실제 좌표로 복원
- 부가 출력: Driving QA (perception, motion prediction, scene reasoning 등)

## Training Data

nuScenes 기반 다중 데이터셋:

| 데이터 | 용도 |
|---|---|
| TOD3Cap | agent-level 2D caption (위치 포함) |
| nuCaption | scene-level multi-view description |
| nuScenesQA | 장면 QA |
| nuX | instruction-based QA |
| GPT-Driver | 계획/판단 QA |

## Training Stages

4단계 순차 학습:

1. **Stage 1 — Hierarchical Vision-Language Alignment**: VLM 전부 frozen. Projector만 학습. scene/agent/map token을 LLM 공간에 정렬
2. **Stage 2 — Driving Instruction Tuning**: Projector + LLM 학습. 다양한 driving QA로 지식 주입. CoT 없이 implicit 추론 내재화
3. **Stage 2.5 — Agent-Env-Ego Interaction Modeling**: 주변 agent의 trajectory를 auxiliary task로 예측. spatial prior 강화
4. **Stage 3 — Trajectory Planning Tuning**: 전체 end-to-end 학습. ego trajectory 예측

## Action Representation

- waypoint를 **text token으로 직렬화**해 LLM vocabulary에 통합
- autoregressive 생성: `t=1` → `t=2` → ... → `t=T`
- 수식: `argmax Π p(wt | w_<t, Venv, Sego, Xcmd)`
- 이 방식의 장점: LLM의 reasoning 능력과 action 생성이 통합됨

## Evaluation (nuScenes open-loop)

두 metric set 모두 SOTA 수준 달성:
- **ST-P3 metric**: L2 (1/2/3s), Collision rate
- **UniAD metric**: L2 (1/2/3s), Collision rate

## What to Copy

- **Waypoint tokenization 아이디어**: 연속 waypoint를 discrete token으로 만들어 LLM vocabulary에 추가하는 방식. Phase C action tokenizer 구현의 직접 참고
- **Multi-stage training 전략**: frozen projector → instruction tuning → trajectory tuning 순서. Phase B의 frozen_vlm → lora_vlm 흐름과 일치
- **auxiliary interaction task**: 주변 agent trajectory 예측을 보조 loss로 추가하는 아이디어. M7 이후 검토
- **ego state를 텍스트로 변환**해 prompt에 포함하는 방식: 이미 `collect_carla_data.py`에서 route_command + ego_speed로 반영됨

## What Not to Copy

- **3D perception stack (BEV + LiDAR)**: 우리 현재 데이터는 front RGB + ego state만. 당장 불필요
- **다단계 visual token (scene/agent/map)**: 복잡도가 높음. DummyBackbone → 3B frozen 단계에서는 single visual embedding으로 시작
- **nuScenes 전용 QA dataset**: CARLA 기반 작업이 먼저
