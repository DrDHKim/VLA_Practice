# Handbook

This is the compact working guide for people and local LLMs. Detailed execution order lives in `TASKS.md`.

## Local LLM Workflow

Required reading order:

1. `README.md`
2. `project_plan.md`
3. `TASKS.md`
4. `docs/setup.md` if offline setup matters
5. the files listed under the current task

Rules:

- Do not redesign the repository.
- Do not skip milestones.
- Do not implement paper extensions before CARLA and baseline training work.
- Prefer small, testable code.
- If internet is unavailable, continue with local stubs and mark missing downloads as blocked.
- After editing code, run the smallest relevant test.

Progress report format:

```text
Task: M1.1 Implement CarlaClient
Files changed:
- src/vla_drive/simulation/carla_client.py
Validation:
- Connected to CARLA Town01
Blocked:
- None
Next:
- Implement RGB camera callback
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

Waypoints come first because they are easier to debug than direct low-level controls, allow controller replacement without retraining, and match common planning metrics.

Later extensions:

- multi-view cameras
- trajectory action tokenizer
- reasoning auxiliary output
- fast/slow reasoning mode
- RL fine-tuning in CARLA

## CARLA Pipeline

First reliable loop:

```text
connect -> spawn -> sense -> predict waypoints -> control -> log -> cleanup
```

Implementation files:

- `src/vla_drive/simulation/carla_client.py`
- `src/vla_drive/simulation/carla_agent.py`
- `src/vla_drive/simulation/route_planner.py`
- `src/vla_drive/simulation/pid_controller.py`
- `scripts/collect_carla_data.py`
- `scripts/eval_carla.sh`

Minimum demo:

- CARLA server running
- one vehicle
- one front RGB camera
- one route
- 30 seconds of driving
- metadata JSONL and image frames saved

Common failures:

- actors not cleaned up after crash
- async/sync mode mismatch
- sensor queue lag
- control commands applied before first observation
- route completion metric tied to frame count instead of distance

## Data Pipeline

All datasets should become `DrivingSample`:

- `Observation`
- `ActionTarget`
- optional reasoning text

See `docs/data.md`.

Priority:

1. CARLA short routes
2. CARLA weather variants
3. nuScenes mini
4. nuScenes full
5. NAVSIM or Bench2Drive

Split by route or scene, not by frame.

## Training Pipeline

First goal: overfit 10-100 samples. Do not start large training until this works.

Training order:

1. dummy backbone + waypoint head
2. frozen VLM + waypoint head
3. VLM LoRA/QLoRA
4. multi-view input
5. reasoning auxiliary loss
6. action tokenizer

RTX 5090 rules:

- start batch size 1
- use bf16
- use gradient accumulation
- use LoRA before full fine-tuning
- lower image size before changing architecture
- keep checkpoints outside git

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

Closed-loop failures should be categorized before changing the model. Many failures come from controller, route planner, sensor timing, or data bugs.

## Hardware Strategy

The hardware changes scale, not the pipeline. Each machine should run CARLA data collection, training, open-loop evaluation, and closed-loop evaluation at an appropriate size.

MacBook:

- use for the small end-to-end pilot: CARLA smoke data collection, tiny/small training, small open/closed-loop evaluation, docs, code editing, paper notes
- keep routes short, resolution low, traffic light, and runs reproducible
- keep offline bundle under 120GB

RTX 5090:

- use for the same pipeline at medium scale: more CARLA data, LoRA/QLoRA, repeated evaluation
- avoid 10B full fine-tuning

Company AIP/H100 x2:

- use only after MacBook smoke runs and RTX 5090 medium-scale runs are stable
- code cannot be brought back after moving into that environment
