# Experiments

## Initial Decision

Use a small custom VLA baseline first:

- VLM backbone
- waypoint regression action head
- PID/MPC controller in CARLA
- LoRA/QLoRA fine-tuning

Use OpenDriveVLA/AutoVLA as architecture references. Use Alpamayo only as a large baseline or teacher until the local pipeline is stable.

Consequences:

- The first milestone must be achievable as a tiny MacBook smoke run.
- The RTX 5090 is the medium-scale version of the same data collection, training, and evaluation loop.
- Results will not match SOTA initially.
- The project keeps the option to move to AIP/H100 later without locking in too early.

## Experiment Matrix

### E00 Smoke Test

- model: tiny random VLA policy
- data: 10 CARLA samples
- machine: MacBook
- goal: code path runs without CUDA/CARLA errors

### E01 CARLA Imitation Baseline

- model: frozen VLM + waypoint head
- data: MacBook tiny route first, then up to 1 hour CARLA expert data on RTX 5090
- metric: waypoint L1, FDE

### E02 LoRA VLA

- model: VLM LoRA + waypoint head
- data: CARLA clear/rain/fog
- machine: RTX 5090 after E00/E01 pass on MacBook
- metric: open-loop + 5 closed-loop routes

### E03 nuScenes Transfer

- model: E02 initialized
- data: nuScenes mini, then full
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

- model: selected best E02-E05 variant
- data: expanded CARLA/nuScenes/NAVSIM or Bench2Drive subset
- machine: AIP/H100 only
- gate: MacBook smoke run and RTX 5090 medium run already passed
- metric: ablation report, long-run closed-loop score, failure taxonomy
