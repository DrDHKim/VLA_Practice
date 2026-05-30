# 실험 (Experiments)

## 초기 판단

먼저 작은 custom VLA baseline을 사용한다.

- VLM backbone
- waypoint regression action head
- CARLA 안의 PID/MPC controller
- LoRA/QLoRA fine-tuning

OpenDriveVLA/AutoVLA는 architecture reference로 사용한다. Alpamayo는 local pipeline이 안정되기 전까지 large baseline 또는 teacher로만 본다.

결과:

- 첫 milestone은 MacBook tiny smoke run으로 달성 가능해야 한다.
- RTX 5090은 같은 data collection, training, evaluation loop의 medium-scale 버전이다.
- 초기 결과는 SOTA와 맞지 않아도 된다.
- AIP/H100으로 너무 일찍 lock-in되지 않도록 migration option을 유지한다.

## Experiment Matrix

### E00 Smoke Test

- model: tiny random VLA policy
- data: 10 CARLA samples
- machine: MacBook
- goal: code path가 CUDA/CARLA error 없이 실행됨

### E01 CARLA Imitation Baseline

- model: frozen VLM + waypoint head
- data: MacBook tiny route 먼저, 이후 RTX 5090에서 최대 1시간 CARLA expert data
- metric: waypoint L1, FDE

### E02 LoRA VLA

- model: VLM LoRA + waypoint head
- data: CARLA clear/rain/fog
- machine: E00/E01이 MacBook에서 통과한 뒤 RTX 5090
- metric: open-loop + 5 closed-loop routes

### E03 nuScenes Transfer

- model: E02 initialized
- data: nuScenes mini, 이후 full
- metric: open-loop trajectory error

### E04 Reasoning Auxiliary Loss

- model: E02 plus reasoning text head
- data: generated/annotated reasoning
- metric: action quality and reasoning-action consistency

### E05 Action Tokenizer

- model: AutoVLA-style discrete trajectory tokens
- data: CARLA + nuScenes
- metric: open-loop, closed-loop, invalid action rate

### E06 AIP/H100 Scale-Up

- model: 선택된 best E02-E05 variant
- data: expanded CARLA/nuScenes/NAVSIM 또는 Bench2Drive subset
- machine: AIP/H100 only
- gate: MacBook smoke run과 RTX 5090 medium run이 이미 통과됨
- metric: ablation report, long-run closed-loop score, failure taxonomy
