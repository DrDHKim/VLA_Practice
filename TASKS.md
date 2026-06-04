# TASKS

이 파일은 로컬 LLM(Qwen3 Coder 30B)이 순서대로 구현하기 위한 실행 지시서다. 프로젝트 방향은 `README.md`와 `project_plan.md`, 환경/오프라인 자산은 `docs/setup.md`, 데이터 기준은 `docs/data.md`를 따른다.

## 전역 규칙

- 저장소 구조를 재설계하지 말 것.
- 새 파일을 만들기 전에 관련 TODO가 있는 기존 stub 파일을 먼저 확인할 것.
- 한 번에 하나의 milestone만 진행할 것.
- internet이 필요하면 `BLOCKED: needs internet`로 표시하고 다음 offline-safe task로 넘어갈 것.
- CARLA loop가 동작하기 전에는 모델 학습 코드를 키우지 말 것.
- 모든 기능은 먼저 MacBook에서 가능한 범위까지 구현/검증한다. 단순히 milestone이 끝났다는 이유만으로 RTX 5090으로 넘어가지 않는다.
- RTX 5090 전환은 MacBook에서 같은 code path를 유지한 채 batch/image/model/route/traffic 규모를 줄여도 리소스 한계가 명확할 때만 허용한다. 전환 사유는 `docs/experiments.md` 또는 연구일지에 남긴다.
- AIP/H100 전환도 RTX 5090에서 같은 방식으로 가능한 최적화와 축소 실험을 모두 시도한 뒤, 리소스 한계나 대규모 ablation 필요성이 명확할 때만 허용한다.
- 10B급 model full fine-tuning은 금지. LoRA/QLoRA만 허용.
- 작업을 끝내면 완료 기준을 실제로 확인하고 상태를 바꿀 것.
- MacBook 작업 시작 전 `.conda/bin/python scripts/check_mac_readiness.py`를 실행하고, `[FAIL]`이 있으면 먼저 해결할 것.
- CARLA server는 Mac 공식 지원을 전제하지 말 것. 이 Mac에서는 CrossOver 64-bit bottle + D3DMetal + Windows CARLA 0.9.15로 RGB camera frame과 `127.0.0.1:2000` port open까지 검증했다. 불안정하더라도 먼저 Mac에서 가능한 축소/우회 설정을 시도하고, 그 한계를 기록한 뒤 Linux/Windows host 또는 remote-run 방식으로 전환한다.

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
- 현재 MacBook readiness에서 CARLA server runtime은 준비됐지만, macOS native `carla` PythonAPI와 MPS availability는 주의 대상이다. 자세한 해결책은 `docs/setup.md`와 `docs/carla_mac_setup.md`를 따른다.

현재 구현 대상: `M10D: Autopilot Sync Dataset Collection and Validation`

## M1: CARLA Connection

상태: `[x]`

파일:

- `src/vla_drive/simulation/carla_client.py`
- `src/vla_drive/simulation/route_planner.py`
- `src/vla_drive/utils/io.py`
- `scripts/collect_carla_data.py`
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`

목표:

- MacBook에서 tiny smoke부터 시작해 가능한 범위까지 CARLA 서버에 연결하고, 차량과 센서를 spawn하고, Traffic Manager autopilot으로 주행하며 데이터를 저장할 준비를 한다. CARLA server는 `scripts/run_carla_mac_crossover.sh`로 켠 local CrossOver/D3DMetal server를 우선 사용하되, Mac 리소스 한계가 기록된 경우 같은 config로 remote Linux/Windows host도 허용한다.
- 같은 코드는 이후 리소스 한계가 확인된 시점에 RTX 5090과 AIP/H100에서 규모만 키워 재사용한다.

단계:

1. `CarlaClient.connect()`를 구현한다.
2. synchronous mode와 fixed delta seconds 설정을 구현한다.
3. `RoutePlanner`에서 짧은 route와 local waypoint/high-level command를 만든다.
4. actor cleanup 로직을 구현한다.
5. RGB front camera sensor callback을 구현한다.
6. Traffic Manager autopilot control log를 JSONL target에 저장한다.
7. `scripts/collect_carla_data.py`에서 짧은 scene 1개를 실행하고 JSONL/images를 저장한다.

완료 기준:

- MacBook에서 local 또는 remote CARLA 서버가 켜져 있을 때 Python script가 world name을 출력한다.
- ego vehicle과 RGB camera가 spawn된다.
- 30초 이상 crash 없이 tick이 진행된다.
- 최소 10개 frame의 observation metadata를 저장한다.
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`만 바꿔 route와 저장 위치를 조정할 수 있다.

## M2: Common Data Schema

상태: `[x]`

파일:

- `src/vla_drive/data/schemas.py`
- `src/vla_drive/data/datasets.py`
- `src/vla_drive/data/collate.py`
- `src/vla_drive/data/transforms.py`
- `src/vla_drive/utils/io.py`
- `docs/data.md`

목표:

- CARLA와 nuScenes를 같은 `DrivingSample` 형식으로 읽을 수 있게 만든다.

단계:

1. `Observation`, `ActionTarget`, `DrivingSample` 필드가 실제 저장 JSONL과 일치하는지 확인한다.
2. JSONL read/write helper와 image path helper를 `utils/io.py`에 추가한다.
3. `JsonlDrivingDataset`에 상대 경로/절대 경로 처리를 추가한다.
4. image loading transform을 구현한다.
5. `driving_collate_fn`에서 batch tensor와 prompt를 만든다.
6. 작은 fixture JSONL로 unit test를 추가한다.

완료 기준:

- 10개 샘플 JSONL을 dataset으로 읽을 수 있다.
- DataLoader가 batch를 만든다.
- image tensor shape와 waypoint tensor shape가 출력된다.

## M3: Baseline VLA Policy

상태: `[x]`

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
2. `WaypointHead`가 `[B, T, 3]`을 출력하는지 확인한다.
3. `VLADrivingPolicy`가 backbone output과 waypoint head를 연결하게 한다.
4. waypoint L1 loss와 FDE loss를 합친 loss 함수를 만든다.
5. Qwen2.5-VL 또는 LLaVA wrapper는 dummy baseline이 통과한 뒤 붙인다.

완료 기준:

- dummy batch에서 forward/loss/backward가 성공한다.
- unit test가 통과한다.

## M4: Training Loop

상태: `[x]`

파일:

- `src/vla_drive/training/train.py`
- `src/vla_drive/training/lora.py`
- `src/vla_drive/utils/seed.py`
- `src/vla_drive/utils/logging.py`
- `scripts/train_lora.sh`
- `src/vla_drive/configs/base.yaml`

목표:

- 작은 CARLA dataset으로 overfit 가능한 training loop를 만든다.

단계:

1. argparse 또는 Hydra 중 하나를 선택한다. 단순 구현은 argparse를 우선한다.
2. dataset, model, optimizer, scheduler, checkpoint 저장을 구현한다.
3. seed 고정과 training log 저장 helper를 연결한다.
4. gradient accumulation과 bf16 옵션을 추가한다.
5. `scripts/train_lora.sh`가 MacBook tiny run 기본값으로 실행되게 한다.
6. LoRA는 baseline overfit 성공 후 추가한다.

완료 기준:

- 10개 샘플에 overfit되어 loss가 감소한다.
- checkpoint가 `checkpoints/`에 저장된다.
- training log가 `outputs/logs/`에 저장된다.

## M5: Open-Loop Evaluation

상태: `[x]`

파일:

- `src/vla_drive/evaluation/open_loop_metrics.py`
- `src/vla_drive/evaluation/evaluator.py`
- `scripts/eval_open_loop.sh`
- `scripts/prepare_nuscenes.py`
- `src/vla_drive/configs/nuscenes_open_loop.yaml`

목표:

- CARLA/nuScenes sample에서 trajectory metric을 계산한다.

단계:

1. ADE/FDE metric을 확장한다.
2. route deviation과 collision proxy metric을 추가한다.
3. evaluation report JSON을 저장한다.
4. `nuscenes_open_loop.yaml`로 checkpoint, dataset, report path를 제어한다.
5. nuScenes mini 변환은 CARLA eval path가 검증된 뒤 진행한다.

완료 기준:

- eval script가 checkpoint를 읽고 report를 만든다.
- report에 ADE, FDE, sample count가 포함된다.

## M6: Closed-Loop CARLA Evaluation

상태: `[x]`

파일:

- `src/vla_drive/evaluation/closed_loop_metrics.py`
- `src/vla_drive/evaluation/evaluator.py`
- `scripts/eval_carla.sh`

목표:

- CARLA route에서 Traffic Manager autopilot baseline의 collision, route completion, infraction penalty, driving score를 측정한다.

단계:

1. route rollout runner를 만든다.
2. collision/lane/off-road/red-light 이벤트를 기록한다.
3. route completion을 계산한다.
4. route별 report와 aggregate report를 저장한다.

완료 기준:

- 5개 route를 자동 평가한다.
- 각 route의 score와 failure reason이 저장된다.

## M7: Research Extensions

상태: `[x]`

파일:

- `src/vla_drive/models/action_tokenizer.py`
- `docs/research.md`
- `docs/experiments.md`

목표:

- OpenDriveVLA/AutoVLA 논문 구조를 baseline 위에 점진적으로 추가한다.

단계:

1. `[x]` waypoint regression baseline을 고정한다.
2. `[x]` trajectory action tokenizer를 구현한다.
3. `[x]` reasoning auxiliary target을 추가한다.
4. `[x]` fast/slow reasoning mode를 실험한다.
5. RL fine-tuning은 closed-loop metric이 안정된 뒤만 검토한다.

완료 기준:

- `[x]` regression baseline과 tokenized-action baseline을 같은 metric으로 비교한다.
- `[x]` 실험 결과가 `outputs/reports/`에 저장된다.
- `[x]` fast/slow reasoning mode의 최소 smoke 비교를 추가한다.

## M8: MacBook Scale Envelope

상태: `[x]`

파일:

- `scripts/run_mac_scale_sweep.sh`
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`
- `docs/experiments.md`
- `docs/research_journal.md`

목표:

- 5090으로 넘어가기 전에 MacBook에서 가능한 CARLA 수집/학습/평가 범위를 계량한다.
- 단순히 “느리다”가 아니라 route 수, route 시간, image size, sample 수, batch size, model stage별 성공/실패 증거를 남긴다.

단계:

1. `[x]` MacBook readiness와 free disk를 기록한다.
2. `[x]` CARLA collection scale sweep을 만든다: route count, route seconds, image size, weather.
3. `[x]` training scale sweep을 만든다: `dummy_overfit`, `reasoning_aux`, `action_token`, 가능하면 `frozen_vlm`.
4. `[x]` open-loop evaluation을 모든 checkpoint에 같은 metric으로 실행한다.
5. `[x]` closed-loop evaluation은 1 route -> 5 route -> 가능한 route 수 순서로 늘린다.
6. `[x]` 실패하면 batch/image/route/model을 줄여 재시도하고 전환 기록 양식에 남긴다.

완료 기준:

- `outputs/reports/mac_scale_envelope.json`에 성공한 최대 설정과 실패한 최소 설정이 저장된다.
- 5090 전환이 필요하면 `docs/experiments.md`의 장비 전환 기록 양식이 채워진다.
- 전환이 아직 필요 없으면 다음 MacBook 실험 범위가 명확히 적힌다.

## M9: Dataset Expansion on Mac

상태: `[x]`

파일:

- `scripts/prepare_nuscenes.py`
- `src/vla_drive/data/datasets.py`
- `src/vla_drive/data/schemas.py`
- `src/vla_drive/configs/nuscenes_open_loop.yaml`
- `docs/data.md`

목표:

- MacBook에서 가능한 범위로 CARLA 외 dataset path를 common schema에 연결한다.
- full dataset으로 바로 가지 않고, nuScenes mini 또는 Bench2Drive mini의 작은 subset을 JSONL/image path 기반으로 변환한다.

단계:

1. `[x]` nuScenes mini 또는 Bench2Drive mini 중 offline asset이 준비된 쪽을 먼저 선택한다.
2. `[x]` 10-100 sample subset을 `DrivingSample` JSONL로 변환한다.
3. `[x]` route command 또는 scene prompt mapping을 문서화한다.
4. `[x]` open-loop evaluator가 변환된 JSONL에서 동작하게 한다.
5. `[x]` CARLA-trained checkpoint와 dataset-specific tiny checkpoint를 같은 metric으로 비교한다.

완료 기준:

- 변환된 mini JSONL을 DataLoader가 읽는다.
- open-loop report가 `outputs/reports/`에 저장된다.
- MacBook에서 full 변환이 불가능하면 용량/시간 한계를 기록한다.

## M10: 5090 Handoff Package

상태: `[x]`

파일:

- `scripts/export_handoff_bundle.sh`
- `docs/setup.md`
- `docs/experiments.md`
- `docs/research_journal.md`

목표:

- MacBook에서 가능한 실험을 모두 수행한 뒤에만 5090으로 넘길 수 있는 재현 bundle을 만든다.
- 코드, config, command, report, 전환 사유가 한 묶음으로 남아야 한다.

단계:

1. `[x]` MacBook scale envelope report를 확인한다.
2. `[x]` 5090에서 실행할 정확한 command set을 정한다.
3. `[x]` 필요한 offline wheel/model/dataset path를 점검한다.
4. `[x]` git status와 untracked artifact를 정리한다.
5. `[x]` handoff manifest를 만든다: commit/hash, config, checkpoint, reports, expected commands.
6. `[x]` 5090에서 첫 smoke command를 `docs/setup.md`에 기록한다.

완료 기준:

- `outputs/handoff/5090_manifest.json`이 생성된다.
- MacBook에서 5090 전환 사유가 문서화되어 있다.
- 5090에서 처음 실행할 data collection, training, open-loop, closed-loop command가 명시되어 있다.

## M10A: MacBook CARLA Dataset and VLA Training Extension

상태: `[x]`

파일:

- `src/vla_drive/configs/carla_mac_dataset.yaml`
- `src/vla_drive/evaluation/evaluator.py`
- `docs/research_journal.md`
- `outputs/reports/m10_mac_carla_60s_vla_training_summary.json`

목표:

- 5090으로 넘어가기 전에 MacBook에서 CARLA dataset을 추가 수집하고, 가능한 VLA 학습 경로를 실제로 실행한다.

단계:

1. `[x]` Mac readiness를 다시 확인한다.
2. `[x]` CrossOver CARLA에서 60초 이상 RGB/waypoint dataset을 수집한다.
3. `[x]` 수집 JSONL을 DataLoader로 확인한다.
4. `[x]` `reasoning_aux`와 `action_token`을 Mac MPS에서 학습하고 open-loop 평가한다.
5. `[x]` Qwen2.5-VL frozen VLM smoke 학습과 open-loop 평가를 수행한다.
6. `[x]` Qwen2.5-VL LoRA VLM 최소 smoke 학습과 open-loop 평가를 수행하고 Mac 한계를 기록한다.

완료 기준:

- MacBook 수집 dataset metadata가 600 sample 이상이다.
- VLA 계열 checkpoint와 open-loop report가 생성된다.
- frozen/LoRA VLM의 Mac 실행 가능 여부와 한계가 연구일지에 기록된다.

## M10B: User-Editable Mac Command Launchers

상태: `[x]`

파일:

- `launchers/03_학습.command`
- `launchers/06_데이터수집.command`
- `scripts/collect_carla_scenes.sh`
- `scripts/collect_carla_data.py`
- `scripts/train_lora.sh`
- `src/vla_drive/training/train.py`
- `launchers/README.md`
- `docs/research_journal.md`

목표:

- Mac에서 사용자가 command 파일 상단 변수만 수정해 CARLA dataset 수집과 VLA 학습을 반복 실행할 수 있게 한다.

단계:

1. `[x]` 데이터 수집 command에 scene 수, scene별 시간, FPS, 해상도, route/weather/output root 변수를 노출한다.
2. `[x]` scene별 output을 만들고 전체 `metadata.jsonl`을 합치는 수집 wrapper를 추가한다.
3. `[x]` CARLA port 대기와 scene 재시도 옵션을 추가한다.
4. `[x]` 학습 command에 full VLM 연결 stage(`frozen_vlm`, `lora_vlm`), epoch, early stopping, batch size, learning rate, gradient accumulation, resume 옵션을 노출한다.
5. `[x]` training loop에 실제 early stopping과 `best.pt` 저장을 추가한다.
6. `[x]` launcher README와 연구일지에 사용 방법과 검증 결과를 기록한다.

완료 기준:

- command/script 문법 검사가 통과한다.
- early stopping smoke 학습이 동작한다.
- CARLA가 응답하지 않는 경우 수집 script가 재시도하거나 명확히 실패한다.

## M10C: Autopilot-Only Data Collection Cleanup

상태: `[x]`

파일:

- `scripts/collect_carla_data.py`
- `scripts/collect_carla_scenes.sh`
- `scripts/eval_carla_closed_loop.py`
- `scripts/eval_carla.sh`
- `launchers/05_평가.command`
- `launchers/06_데이터수집.command`
- `src/vla_drive/configs/carla_mac_dataset.yaml`
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`
- `tests/unit/test_simulation_m1.py`

목표:

- PID 기반 제어기를 완전히 제거하고, CARLA Traffic Manager autopilot 기반 수집/평가만 남긴다.
- 카메라 시야와 throttle/brake oscillation 문제를 완화한다.

단계:

1. `[x]` PID controller 파일, PID agent 파일, PID tuning launcher를 삭제한다.
2. `[x]` closed-loop 평가를 Traffic Manager autopilot 기반으로 바꾼다.
3. `[x]` 수집 기본값을 autopilot-only로 고정하고 직접 제어 fallback을 제거한다.
4. `[x]` 고정 path autopilot을 기본에서 끄고 실제 autopilot trajectory를 post-process한다.
5. `[x]` 카메라 위치를 더 높고 앞으로 이동한다.
6. `[x]` brake가 큰 frame을 기본적으로 제외한다.

완료 기준:

- PID 관련 code/test/launcher 참조가 제거된다.
- autopilot-only 8초 smoke 수집에서 RGB image와 metadata가 생성된다.
- sync smoke에서 비동기 stop-go 문제가 완화되고, 남은 Traffic Manager throttle/brake 변동은 scene report에 드러난다.

## M10D: Autopilot Sync Dataset Collection and Validation

상태: `[~]`

파일:

- `launchers/06_데이터수집.command`
- `scripts/collect_carla_scenes.sh`
- `scripts/render_scene_gif.py`
- `scripts/render_scene_report.py`
- `src/vla_drive/simulation/route_command.py`
- `src/vla_drive/simulation/route_planner.py`
- `src/vla_drive/configs/carla_mac_dataset.yaml`
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`
- `tests/unit/test_route_command.py`
- `scripts/train_lora.sh`
- `scripts/eval_open_loop.sh`
- `scripts/eval_carla.sh`
- `docs/experiments.md`
- `docs/research_journal.md`

목표:

- M10C에서 정리한 Traffic Manager autopilot + synchronous sampling 경로로 MacBook CARLA dataset을 새로 수집한다.
- 신호등 정지, 앞차 정지, random walker crossing에 따른 감속/정지 샘플을 포함한다.
- 신호등/보행자 상태는 모델 입력에 직접 넣지 않고, RGB image와 autopilot target에서 학습하게 둔다.
- 수집 품질을 GIF, BEV/control report, metadata 통계로 먼저 검수한 뒤 training/evaluation으로 넘어간다.
- MacBook에서 더 진행할 수 있는 범위와 RTX 5090으로 넘겨야 하는 범위를 분리한다.

단계:

1. `[x]` `06_데이터수집.command` 상단 변수로 scene 수, 초, FPS, 해상도, overwrite 정책을 확인한다.
2. `[x]` route command 생성 로직을 수집/평가에서 공유 가능한 helper로 분리한다.
3. `[x]` route command lookahead를 `meters` 또는 `frames` 입력으로 조정할 수 있게 한다. 기본값은 30m다.
4. `[x]` Traffic Manager가 신호등/앞차를 따르도록 ignore lights/signs/vehicles 기본값을 0으로 바꾼다.
5. `[x]` NPC vehicle과 random walker crossing 수를 launcher/config에서 조정할 수 있게 한다.
6. `[x]` 수집 결과의 `metadata.jsonl`, scene별 `scene.gif`, `bev_route.png`, `controls_timeseries.png`가 생성되는지 확인한다.
7. `[x]` metadata row 수, sample id 중복, frame index gap, image path 존재 여부를 점검한다.
8. `[ ]` 속도/브레이크가 과도하게 흔들리는 scene은 제외하거나 재수집한다.
9. `[x]` 수집 metadata로 DataLoader/pytest smoke를 통과시킨다.
10. `[x]` `reasoning_aux`와 `action_token` tiny training smoke를 실행한다.
11. `[x]` 각 checkpoint를 같은 metadata로 open-loop 평가한다.
12. `[x]` CARLA Traffic Manager closed-loop baseline report를 생성한다.
13. `[x]` 결과와 다음 장비 전환 판단을 `docs/research_journal.md`와 `docs/experiments.md`에 기록한다.

완료 기준:

- combined `metadata.jsonl`이 있고, scene별 GIF/report를 통해 수집 품질을 검수했다.
- 학습 수집과 평가에서 같은 route command lookahead 기준을 설정할 수 있다. 기본 설정은 30m다.
- 신호등/앞차/NPC 보행자 시나리오를 화면 기반으로 수집할 수 있다.
- DataLoader smoke와 최소 1개 training stage가 통과한다.
- open-loop report와 Traffic Manager baseline closed-loop report가 `outputs/reports/`에 저장된다.
- MacBook에서 추가 수집/학습을 계속할지, RTX 5090으로 확장할지 근거가 문서화된다.

## M11: RTX 5090 Expansion

상태: `[ ]`

파일:

- `docs/experiments.md`
- `docs/research_journal.md`
- `scripts/train_lora.sh`
- `scripts/eval_open_loop.sh`
- `scripts/eval_carla.sh`

목표:

- MacBook에서 검증된 같은 code path를 RTX 5090에서 확장한다.
- 5090에서도 바로 H100으로 가지 않고, quantization/checkpointing/offload와 scale-down을 먼저 시도한다.

단계:

1. 5090 환경에서 unit test와 MacBook-equivalent smoke run을 통과시킨다.
2. CARLA collection scale을 늘린다: route/weather/traffic/time.
3. LoRA/QLoRA training을 반복한다.
4. open-loop와 closed-loop report를 같은 schema로 저장한다.
5. OOM 또는 시간 한계가 나오면 batch/image/model/LoRA rank/quantization/offload를 조정한다.
6. H100 전환이 필요하면 전환 기록 양식을 채운다.

완료 기준:

- 5090 report가 `outputs/reports/`에 저장된다.
- MacBook report와 같은 metric key로 비교 가능하다.
- H100 전환 여부가 근거와 함께 결정된다.

## M12: H100 Final Scale and Ablation

상태: `[ ]`

파일:

- `docs/experiments.md`
- `docs/research_journal.md`
- `outputs/reports/`

목표:

- 5090에서도 리소스 한계가 확인된 실험만 H100에서 수행한다.
- 회사 환경 lock-in을 감수할 가치가 있는 large LoRA/QLoRA, multi-dataset, ablation만 실행한다.

단계:

1. H100 진입 기준과 운영 리스크를 재확인한다.
2. code snapshot과 experiment manifest를 archive한다.
3. large training/ablation matrix를 실행한다.
4. open-loop, closed-loop, failure taxonomy report를 생성한다.
5. MacBook/5090 결과와 같은 metric schema로 비교한다.

완료 기준:

- H100 run의 목적, config, 결과, 비용/시간이 문서화된다.
- MacBook -> 5090 -> H100 전체 ladder의 metric 비교표가 있다.
- 다음 논문/보고서용 artifact가 분리되어 있다.
