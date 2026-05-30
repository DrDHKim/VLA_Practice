# TASKS

이 파일은 로컬 LLM(Qwen3 Coder 30B)이 순서대로 구현하기 위한 실행 지시서다. 프로젝트 방향은 `README.md`와 `project_plan.md`, 환경/오프라인 자산은 `docs/setup.md`, 데이터 기준은 `docs/data.md`를 따른다.

## 전역 규칙

- 저장소 구조를 재설계하지 말 것.
- 새 파일을 만들기 전에 관련 TODO가 있는 기존 stub 파일을 먼저 확인할 것.
- 한 번에 하나의 milestone만 진행할 것.
- internet이 필요하면 `BLOCKED: needs internet`로 표시하고 다음 offline-safe task로 넘어갈 것.
- CARLA loop가 동작하기 전에는 모델 학습 코드를 키우지 말 것.
- 모든 기능은 MacBook tiny smoke run을 먼저 통과한 뒤 RTX 5090 medium run으로 확장할 것.
- AIP/H100은 MacBook과 RTX 5090에서 data collection, training, evaluation loop가 검증된 뒤에만 사용할 것.
- 10B급 model full fine-tuning은 금지. LoRA/QLoRA만 허용.
- 작업을 끝내면 완료 기준을 실제로 확인하고 상태를 바꿀 것.

## 상태 표시

- `[ ]` 시작 전
- `[~]` 진행 중
- `[x]` 완료
- `[!]` 차단됨

## 준비 완료 상태

상태: `[x]`

- 문서와 stub 구조가 준비됨.
- MacBook Python 3.10 local environment가 준비됨.
- P0-P4 offline asset은 `data/offline/`에 준비됨.
- 일반 MacBook offline 작업은 `data/offline/wheels/macos-py310-pinned`를 사용함.
- 세부 목록과 용량 정책은 `docs/setup.md`를 기준으로 확인할 것.

다음 구현 대상: `M1: CARLA Connection`

## M1: CARLA Connection

상태: `[ ]`

파일:

- `src/vla_drive/simulation/carla_client.py`
- `src/vla_drive/simulation/carla_agent.py`
- `src/vla_drive/simulation/route_planner.py`
- `src/vla_drive/simulation/pid_controller.py`
- `scripts/collect_carla_data.py`
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`

목표:

- MacBook tiny smoke run부터 CARLA 서버에 연결하고, 차량과 센서를 spawn하고, rule-based route를 따라 주행하며 데이터를 저장할 준비를 한다.
- 같은 코드는 이후 RTX 5090과 AIP/H100에서 규모만 키워 재사용한다.

단계:

1. `CarlaClient.connect()`를 구현한다.
2. synchronous mode와 fixed delta seconds 설정을 구현한다.
3. actor cleanup 로직을 구현한다.
4. RGB front camera sensor callback을 구현한다.
5. `PIDWaypointController.control()`을 구현한다.
6. `scripts/collect_carla_data.py`에서 짧은 route 1개를 실행한다.

완료 기준:

- MacBook에서 CARLA 서버가 켜져 있을 때 Python script가 world name을 출력한다.
- ego vehicle과 RGB camera가 spawn된다.
- 30초 이상 crash 없이 tick이 진행된다.
- 최소 10개 frame의 observation metadata를 저장한다.

## M2: Common Data Schema

상태: `[ ]`

파일:

- `src/vla_drive/data/schemas.py`
- `src/vla_drive/data/datasets.py`
- `src/vla_drive/data/collate.py`
- `src/vla_drive/data/transforms.py`
- `docs/data.md`

목표:

- CARLA와 nuScenes를 같은 `DrivingSample` 형식으로 읽을 수 있게 만든다.

단계:

1. `Observation`, `ActionTarget`, `DrivingSample` 필드가 실제 저장 JSONL과 일치하는지 확인한다.
2. `JsonlDrivingDataset`에 상대 경로/절대 경로 처리를 추가한다.
3. image loading transform을 구현한다.
4. `driving_collate_fn`에서 batch tensor와 prompt를 만든다.
5. 작은 fixture JSONL로 unit test를 추가한다.

완료 기준:

- 10개 샘플 JSONL을 dataset으로 읽을 수 있다.
- DataLoader가 batch를 만든다.
- image tensor shape와 waypoint tensor shape가 출력된다.

## M3: Baseline VLA Policy

상태: `[ ]`

파일:

- `src/vla_drive/models/backbone_vlm.py`
- `src/vla_drive/models/waypoint_head.py`
- `src/vla_drive/models/vla_policy.py`
- `src/vla_drive/training/losses.py`
- `tests/unit/test_waypoint_head.py`
- `tests/unit/test_metrics.py`

목표:

- frozen VLM 또는 dummy backbone으로 future waypoints를 예측하는 최소 policy를 만든다.

단계:

1. 먼저 dummy backbone으로 `VLADrivingPolicy` forward path를 통과시킨다.
2. `WaypointHead`가 `[B, T, 2]`를 출력하는지 확인한다.
3. waypoint L1 loss와 FDE loss를 합친 loss 함수를 만든다.
4. Qwen2.5-VL 또는 LLaVA wrapper는 dummy baseline이 통과한 뒤 붙인다.

완료 기준:

- dummy batch에서 forward/loss/backward가 성공한다.
- unit test가 통과한다.

## M4: Training Loop

상태: `[ ]`

파일:

- `src/vla_drive/training/train.py`
- `src/vla_drive/training/lora.py`
- `scripts/train_lora.sh`
- `src/vla_drive/configs/base.yaml`

목표:

- 작은 CARLA dataset으로 overfit 가능한 training loop를 만든다.

단계:

1. argparse 또는 Hydra 중 하나를 선택한다. 단순 구현은 argparse를 우선한다.
2. dataset, model, optimizer, scheduler, checkpoint 저장을 구현한다.
3. gradient accumulation과 bf16 옵션을 추가한다.
4. LoRA는 baseline overfit 성공 후 추가한다.

완료 기준:

- 10개 샘플에 overfit되어 loss가 감소한다.
- checkpoint가 `checkpoints/`에 저장된다.
- training log가 `outputs/logs/`에 저장된다.

## M5: Open-Loop Evaluation

상태: `[ ]`

파일:

- `src/vla_drive/evaluation/open_loop_metrics.py`
- `src/vla_drive/evaluation/evaluator.py`
- `scripts/eval_open_loop.sh`
- `scripts/prepare_nuscenes.py`

목표:

- CARLA/nuScenes sample에서 trajectory metric을 계산한다.

단계:

1. ADE/FDE metric을 확장한다.
2. route deviation과 collision proxy metric을 추가한다.
3. evaluation report JSON을 저장한다.
4. nuScenes mini 변환은 CARLA eval이 끝난 뒤 진행한다.

완료 기준:

- eval script가 checkpoint를 읽고 report를 만든다.
- report에 ADE, FDE, sample count가 포함된다.

## M6: Closed-Loop CARLA Evaluation

상태: `[ ]`

파일:

- `src/vla_drive/evaluation/closed_loop_metrics.py`
- `src/vla_drive/evaluation/evaluator.py`
- `scripts/eval_carla.sh`
- `src/vla_drive/simulation/carla_agent.py`

목표:

- CARLA route에서 collision, route completion, infraction penalty, driving score를 측정한다.

단계:

1. route rollout runner를 만든다.
2. collision/lane/off-road/red-light 이벤트를 기록한다.
3. route completion을 계산한다.
4. route별 report와 aggregate report를 저장한다.

완료 기준:

- 5개 route를 자동 평가한다.
- 각 route의 score와 failure reason이 저장된다.

## M7: Research Extensions

상태: `[ ]`

파일:

- `src/vla_drive/models/action_tokenizer.py`
- `docs/research.md`
- `docs/experiments.md`

목표:

- OpenDriveVLA/AutoVLA 논문 구조를 baseline 위에 점진적으로 추가한다.

단계:

1. waypoint regression baseline을 고정한다.
2. trajectory action tokenizer를 구현한다.
3. reasoning auxiliary target을 추가한다.
4. fast/slow reasoning mode를 실험한다.
5. RL fine-tuning은 closed-loop metric이 안정된 뒤만 검토한다.

완료 기준:

- regression baseline과 tokenized-action baseline을 같은 metric으로 비교한다.
- 실험 결과가 `outputs/reports/`에 저장된다.
