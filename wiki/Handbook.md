# Handbook

사람과 local LLM을 위한 압축 작업 가이드다. 자세한 실행 순서는 `TASKS.md`에 있다.

## Local LLM Workflow

필수 읽기 순서:

1. `README.md`
2. `project_plan.md`
3. `TASKS.md`
4. offline setup이 필요하면 `docs/setup.md`
5. 현재 task에 적힌 파일

규칙:

- repository를 재설계하지 않는다.
- milestone을 건너뛰지 않는다.
- CARLA와 baseline training이 동작하기 전에 paper extension을 구현하지 않는다.
- 작고 test 가능한 code를 우선한다.
- internet이 없으면 local stub으로 계속 진행하고, 필요한 download는 blocked로 표시한다.
- code를 수정한 뒤 가장 작은 관련 test를 실행한다.

Progress report 형식:

```text
Task: M1.1 Implement CarlaClient
변경 파일:
- src/vla_drive/simulation/carla_client.py
검증:
- Connected to CARLA Town01
Blocked:
- None
다음:
- RGB camera callback 구현
```

## Architecture

```text
RGB image + ego state + route command
        |
        v
VLM backbone
        |
        v
pooled hidden state
        |
        v
waypoint head
        |
        v
future waypoints
        |
        v
PID/MPC controller
        |
        v
steer / throttle / brake
```

waypoint를 먼저 쓰는 이유는 direct low-level control보다 debugging이 쉽고, retraining 없이 controller를 교체할 수 있으며, 일반적인 planning metric과 잘 맞기 때문이다.

나중에 추가할 확장:

- multi-view cameras
- trajectory action tokenizer
- reasoning auxiliary output
- fast/slow reasoning mode
- CARLA 안의 RL fine-tuning

## CARLA Pipeline

첫 reliable loop:

```text
connect -> spawn -> sense -> predict waypoints -> control -> log -> cleanup
```

구현 파일:

- `src/vla_drive/simulation/carla_client.py`
- `src/vla_drive/simulation/carla_agent.py`
- `src/vla_drive/simulation/route_planner.py`
- `src/vla_drive/simulation/pid_controller.py`
- `scripts/collect_carla_data.py`
- `scripts/eval_carla.sh`

최소 demo:

- CARLA server running
- vehicle 1대
- front RGB camera 1개
- route 1개
- 30초 driving
- metadata JSONL과 image frame 저장

흔한 실패:

- crash 후 actor cleanup 누락
- async/sync mode mismatch
- sensor queue lag
- 첫 observation 전에 control command 적용
- route completion metric을 distance가 아니라 frame count에 묶음

## Data Pipeline

모든 dataset은 `DrivingSample`로 변환한다.

- `Observation`
- `ActionTarget`
- optional reasoning text

자세한 내용은 `docs/data.md`를 본다.

우선순위:

1. CARLA short routes
2. CARLA weather variants
3. nuScenes mini
4. nuScenes full
5. NAVSIM 또는 Bench2Drive

split은 frame 단위가 아니라 route 또는 scene 단위로 나눈다.

## Training Pipeline

첫 목표는 10-100개 sample에 overfit하는 것이다. 이것이 동작하기 전에는 large training을 시작하지 않는다.

Training 순서:

1. dummy backbone + waypoint head
2. frozen VLM + waypoint head
3. VLM LoRA/QLoRA
4. multi-view input
5. reasoning auxiliary loss
6. action tokenizer

RTX 5090 규칙:

- batch size 1부터 시작한다.
- bf16을 사용한다.
- gradient accumulation을 사용한다.
- full fine-tuning 전에 LoRA를 사용한다.
- architecture를 바꾸기 전에 image size를 낮춘다.
- checkpoint는 git 밖에 둔다.

## Evaluation

Open-loop metrics:

- Average Displacement Error
- Final Displacement Error
- route deviation
- invalid waypoint rate

Closed-loop metrics:

- route completion
- collision count
- off-road count
- red-light violation count
- infraction penalty
- driving score

model을 바꾸기 전에 closed-loop failure를 먼저 분류한다. 많은 failure는 controller, route planner, sensor timing, data bug에서 나온다.

## Hardware Strategy

하드웨어가 바꾸는 것은 scale이지 pipeline이 아니다. 각 장비는 적절한 규모로 CARLA data collection, training, open-loop evaluation, closed-loop evaluation을 실행해야 한다.

MacBook:

- small end-to-end pilot에 사용한다: CARLA smoke data collection, tiny/small training, small open/closed-loop evaluation, docs, code editing, paper notes.
- route는 짧게, resolution은 낮게, traffic은 가볍게 유지하고 run은 재현 가능하게 만든다.
- offline bundle은 120GB 아래로 유지한다.

RTX 5090:

- 같은 pipeline을 medium scale로 실행한다: 더 많은 CARLA data, LoRA/QLoRA, 반복 evaluation.
- 10B full fine-tuning은 피한다.

Company AIP/H100 x2:

- MacBook smoke run과 RTX 5090 medium-scale run이 안정된 뒤에만 사용한다.
- 이 환경으로 옮긴 뒤에는 code를 다시 가져올 수 없다.
