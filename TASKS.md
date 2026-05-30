# TASKS

이 파일은 로컬 LLM(Qwen3 Coder 30B)이 순서대로 구현하기 위한 실행 지시서다. `README.md`와 `project_plan.md`는 방향 문서이고, 실제 작업 순서는 이 파일을 따른다.

## Global Rules

- 저장소 구조를 재설계하지 말 것.
- 새 파일을 만들기 전에 관련 TODO가 있는 기존 스텁 파일을 먼저 확인할 것.
- 한 번에 하나의 milestone만 진행할 것.
- 인터넷이 필요하면 작업을 멈추지 말고 `BLOCKED: needs internet`로 표시한 뒤 다음 오프라인 작업으로 넘어갈 것.
- CARLA loop가 동작하기 전에는 모델 학습 코드를 키우지 말 것.
- 모든 기능은 MacBook tiny smoke run을 먼저 통과한 뒤 RTX 5090 중간 규모 run으로 확장할 것.
- AIP/H100은 MacBook과 RTX 5090에서 데이터 수집-학습-평가 루프가 검증된 뒤에만 사용할 것.
- 10B급 모델 full fine-tuning은 금지. LoRA/QLoRA만 허용.
- 작업을 끝내면 Acceptance 항목을 실제로 확인하고 Status를 바꿀 것.

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Done
- `[!]` Blocked

## M0: Repository Orientation

Status: `[x]`

Files:

- `README.md`
- `project_plan.md`
- `wiki/Home.md`
- `wiki/Handbook.md`
- `docs/setup.md`
- `docs/research.md`
- `docs/data.md`
- `docs/experiments.md`

Goal:

- 프로젝트 방향, 모델 전략, 하드웨어 제약, 폴더 구조를 이해한다.

Steps:

1. `README.md`를 읽는다.
2. `project_plan.md`를 읽는다.
3. `wiki/Home.md`를 읽는다.
4. `wiki/Handbook.md`에서 구현 흐름을 확인한다.
5. `docs/setup.md`에서 Anaconda, 하드웨어 역할, 120GB 다운로드 제한을 확인한다.
6. `docs/research.md`에서 모델 선정과 논문 우선순위를 확인한다.
7. `docs/data.md`와 `docs/experiments.md`에서 데이터/실험 기준을 확인한다.

Acceptance:

- 다음 구현 대상이 `M1: CARLA Connection`임을 설명할 수 있다.
- AIP/H100을 초기에 쓰면 안 되는 이유를 설명할 수 있다.
- MacBook, RTX 5090, AIP/H100의 역할 차이가 규모 차이이며 파이프라인 자체는 같다는 점을 설명할 수 있다.
- 120GB 제한 안에서 무엇을 먼저 받아야 하는지 설명할 수 있다.
- 다운로드 우선순위 P0-P5를 설명할 수 있다.

## M0.5: Offline Assets Ready

Status: `[x]`

Files:

- `data/offline/`
- `docs/setup.md`
- `docs/data.md`

Goal:

- 인터넷이 느리거나 없는 환경에서 바로 구현을 시작할 수 있도록 P0-P4 오프라인 자산을 확인한다.

Completed Assets:

- `.conda/`
- `data/offline/conda_installers/Miniconda3-py310_25.9.1-3-MacOSX-arm64.sh`
- `data/offline/repos/navsim`
- `data/offline/repos/Bench2Drive`
- `data/offline/repos/nuscenes-devkit`
- `data/offline/wheels/macos-py310-pinned`
- `data/offline/hf_models/Qwen2.5-VL-3B-Instruct`
- `data/offline/hf_models/Qwen2.5-VL-7B-Instruct`
- `data/offline/hf_models/llava-onevision-qwen2-7b-ov-hf`
- `data/offline/hf_models/navsim_baselines`
- `data/offline/datasets/nuscenes/v1.0-mini.tgz`
- `data/offline/datasets/nuscenes/can_bus.zip`
- `data/offline/datasets/nuscenes/nuScenes-map-expansion-v1.3.zip`
- `data/offline/datasets/bench2drive/Bench2Drive-mini`
- `data/offline/simulators/carla/AdditionalMaps_0.9.15.tar.gz`
- `docs/research/papers/*.pdf`

Verified:

- `.conda/bin/python --version`: `Python 3.10.19`.
- `.conda/bin/python -m pip check`: no broken requirements.
- `.conda/bin/python -m pip install --no-index --find-links data/offline/wheels/macos-py310-pinned -e .`: passed.
- `.conda/bin/python -m pytest`: 2 passed.
- `./scripts/check_offline_budget.sh` result after cleanup: `56.51GB / 120GB`, within budget.
- Core imports passed: torch, torchvision, torchaudio, transformers, accelerate, peft, datasets, cv2, numpy, scipy, matplotlib, nuscenes, pytest.
- Bench2Drive Mini 10 tar files match official sha256 values.
- Qwen2.5-VL-7B and LLaVA-OneVision model folders have no `.incomplete` files.
- NAVSIM baseline checkpoint folder has no `.incomplete` files.
- CARLA AdditionalMaps tar listing is readable.
- nuScenes CAN bus md5: `34b8aa2e676a4aadf0865084bf3425ee`.
- nuScenes map expansion md5: `b3a717def24130beb4becdbbd8c8cd56`.

Do Not Re-download:

- Do not download Bench2Drive Base or Full on the Mac. They exceed the 120GB policy.
- Do not download full nuScenes trainval on the Mac unless the 120GB policy is explicitly changed.
- Do not download Linux CUDA wheelhouse on the Mac unless the target machine needs a portable offline package.
- Use only `data/offline/wheels/macos-py310-pinned` for normal MacBook offline work.

Next Step:

- Proceed to `M1: CARLA Connection`.

## M1: CARLA Connection

Status: `[ ]`

Files:

- `src/vla_drive/simulation/carla_client.py`
- `src/vla_drive/simulation/carla_agent.py`
- `src/vla_drive/simulation/route_planner.py`
- `src/vla_drive/simulation/pid_controller.py`
- `scripts/collect_carla_data.py`
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`

Goal:

- MacBook tiny smoke run부터 CARLA 서버에 연결하고, 차량과 센서를 spawn하고, rule-based route를 따라 주행하며 데이터를 저장할 준비를 한다. 같은 코드는 이후 RTX 5090과 AIP/H100에서 규모만 키워 재사용한다.

Steps:

1. `CarlaClient.connect()`를 구현한다.
2. synchronous mode와 fixed delta seconds 설정을 구현한다.
3. actor cleanup 로직을 구현한다.
4. RGB front camera sensor callback을 구현한다.
5. `PIDWaypointController.control()`을 구현한다.
6. `scripts/collect_carla_data.py`에서 짧은 route 1개를 실행한다.

Acceptance:

- MacBook에서 CARLA 서버가 켜져 있을 때 Python 스크립트가 world name을 출력한다.
- ego vehicle과 RGB camera가 spawn된다.
- 30초 이상 crash 없이 tick이 진행된다.
- 최소 10개 frame의 observation metadata를 저장한다.

## M2: Common Data Schema

Status: `[ ]`

Files:

- `src/vla_drive/data/schemas.py`
- `src/vla_drive/data/datasets.py`
- `src/vla_drive/data/collate.py`
- `src/vla_drive/data/transforms.py`
- `docs/data.md`

Goal:

- CARLA와 nuScenes를 같은 `DrivingSample` 형식으로 읽을 수 있게 만든다.

Steps:

1. `Observation`, `ActionTarget`, `DrivingSample` 필드가 실제 저장 JSONL과 일치하는지 확인한다.
2. `JsonlDrivingDataset`에 상대 경로/절대 경로 처리를 추가한다.
3. image loading transform을 구현한다.
4. `driving_collate_fn`에서 batch tensor와 prompt를 만든다.
5. 작은 fixture JSONL로 unit test를 추가한다.

Acceptance:

- 10개 샘플 JSONL을 dataset으로 읽을 수 있다.
- DataLoader가 batch를 만든다.
- image tensor shape와 waypoint tensor shape가 출력된다.

## M3: Baseline VLA Policy

Status: `[ ]`

Files:

- `src/vla_drive/models/backbone_vlm.py`
- `src/vla_drive/models/waypoint_head.py`
- `src/vla_drive/models/vla_policy.py`
- `src/vla_drive/training/losses.py`
- `tests/unit/test_waypoint_head.py`
- `tests/unit/test_metrics.py`

Goal:

- frozen VLM 또는 dummy backbone으로 future waypoints를 예측하는 최소 policy를 만든다.

Steps:

1. 먼저 dummy backbone으로 `VLADrivingPolicy` forward path를 통과시킨다.
2. `WaypointHead`가 `[B, T, 2]`를 출력하는지 확인한다.
3. waypoint L1 loss와 FDE loss를 합친 loss 함수를 만든다.
4. Qwen2.5-VL 또는 LLaVA wrapper는 dummy baseline이 통과한 뒤 붙인다.

Acceptance:

- dummy batch에서 forward/loss/backward가 성공한다.
- unit test가 통과한다.

## M4: Training Loop

Status: `[ ]`

Files:

- `src/vla_drive/training/train.py`
- `src/vla_drive/training/lora.py`
- `scripts/train_lora.sh`
- `src/vla_drive/configs/base.yaml`

Goal:

- 작은 CARLA dataset으로 overfit 가능한 training loop를 만든다.

Steps:

1. argparse 또는 Hydra 중 하나를 선택한다. 단순 구현은 argparse를 우선한다.
2. dataset, model, optimizer, scheduler, checkpoint 저장을 구현한다.
3. gradient accumulation과 bf16 옵션을 추가한다.
4. LoRA는 baseline overfit 성공 후 추가한다.

Acceptance:

- 10개 샘플에 overfit되어 loss가 감소한다.
- checkpoint가 `checkpoints/`에 저장된다.
- training log가 `outputs/logs/`에 저장된다.

## M5: Open-Loop Evaluation

Status: `[ ]`

Files:

- `src/vla_drive/evaluation/open_loop_metrics.py`
- `src/vla_drive/evaluation/evaluator.py`
- `scripts/eval_open_loop.sh`
- `scripts/prepare_nuscenes.py`

Goal:

- CARLA/nuScenes sample에서 trajectory metric을 계산한다.

Steps:

1. ADE/FDE metric을 확장한다.
2. route deviation과 collision proxy metric을 추가한다.
3. evaluation report JSON을 저장한다.
4. nuScenes mini 변환은 CARLA eval이 끝난 뒤 진행한다.

Acceptance:

- eval script가 checkpoint를 읽고 report를 만든다.
- report에 ADE, FDE, sample count가 포함된다.

## M6: Closed-Loop CARLA Evaluation

Status: `[ ]`

Files:

- `src/vla_drive/evaluation/closed_loop_metrics.py`
- `src/vla_drive/evaluation/evaluator.py`
- `scripts/eval_carla.sh`
- `src/vla_drive/simulation/carla_agent.py`

Goal:

- CARLA route에서 collision, route completion, infraction penalty, driving score를 측정한다.

Steps:

1. route rollout runner를 만든다.
2. collision/lane/off-road/red-light 이벤트를 기록한다.
3. route completion을 계산한다.
4. route별 report와 aggregate report를 저장한다.

Acceptance:

- 5개 route를 자동 평가한다.
- 각 route의 score와 failure reason이 저장된다.

## M7: Research Extensions

Status: `[ ]`

Files:

- `src/vla_drive/models/action_tokenizer.py`
- `docs/research.md`
- `docs/experiments.md`

Goal:

- OpenDriveVLA/AutoVLA 논문 구조를 baseline 위에 점진적으로 추가한다.

Steps:

1. waypoint regression baseline을 고정한다.
2. trajectory action tokenizer를 구현한다.
3. reasoning auxiliary target을 추가한다.
4. fast/slow reasoning mode를 실험한다.
5. RL fine-tuning은 closed-loop metric이 안정된 뒤만 검토한다.

Acceptance:

- regression baseline과 tokenized-action baseline을 같은 metric으로 비교한다.
- 실험 결과가 `outputs/reports/`에 저장된다.
