# 실험 (Experiments)

## 초기 판단

먼저 작은 custom VLA baseline을 사용한다.

- VLM backbone
- waypoint regression action head
- CARLA Traffic Manager autopilot data collection
- LoRA/QLoRA fine-tuning

OpenDriveVLA/AutoVLA는 architecture reference로 사용한다. Alpamayo는 local pipeline이 안정되기 전까지 large baseline 또는 teacher로만 본다.

결과:

- 첫 milestone은 MacBook에서 달성 가능해야 한다.
- MacBook에서는 tiny smoke에서 시작하되 가능한 범위까지 data collection, training, evaluation 규모를 키운다.
- RTX 5090은 MacBook 리소스 한계가 기록된 뒤 같은 loop를 확장하는 장비다.
- 초기 결과는 SOTA와 맞지 않아도 된다.
- AIP/H100으로 너무 일찍 lock-in되지 않도록 migration option을 유지한다.

## 장비 전환 기록 양식

MacBook -> RTX 5090, RTX 5090 -> AIP/H100 전환 전에는 아래 항목을 실험 로그나 연구일지에 남긴다.

```text
from_machine:
to_machine:
experiment_id:
objective:
last_successful_command:
last_successful_result:
failed_command:
failure_type: oom | timeout | disk | simulator_instability | training_time | other
resource_evidence:
attempted_reductions:
  - batch_size:
  - image_size:
  - route_count:
  - route_seconds:
  - traffic_density:
  - model_size:
  - lora_rank:
  - quantization/offload:
reason_next_machine_required:
```

## Experiment Matrix

### E00 Smoke Test

- model: tiny random VLA policy
- data: 10 CARLA samples
- machine: MacBook
- goal: code path가 CUDA/CARLA error 없이 실행됨

### E01 CARLA Imitation Baseline

- model: frozen VLM + waypoint head
- data: MacBook tiny route 먼저, MacBook에서 가능한 만큼 route/sample 수를 확장, 한계 기록 후 RTX 5090에서 최대 1시간 CARLA expert data
- metric: waypoint L1, FDE

### E02 LoRA VLA

- model: VLM LoRA + waypoint head
- data: CARLA clear/rain/fog
- machine: E00/E01이 MacBook에서 통과하고 MacBook 리소스 한계가 확인된 뒤 RTX 5090
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

### E06 MacBook Scale Envelope

- model: dummy/regression, reasoning_aux, action_token, frozen_vlm where possible
- data: CARLA local CrossOver routes, 가능한 경우 nuScenes/Bench2Drive mini subset
- machine: MacBook
- goal: MacBook에서 성공 가능한 최대 설정과 실패하는 최소 설정을 찾음
- metric: max successful route seconds/count, max image size, max samples, training time, open-loop ADE/FDE, closed-loop score

### E07 5090 Handoff Smoke

- model: E06에서 선택한 best small variant
- data: E06 manifest에 포함된 CARLA/mini dataset
- machine: RTX 5090
- gate: E06에서 MacBook 리소스 한계가 문서화됨
- metric: MacBook-equivalent command가 5090에서 같은 report schema로 재현됨

현재 handoff package:

```text
outputs/handoff/5090_manifest.json
```

전환 사유:

- MacBook에서 M8 scale envelope는 training/open-loop 16개 run, CARLA collection 1개 run, closed-loop 2개 run을 모두 통과했다.
- MacBook에서 M9 nuScenes mini conversion, DataLoader, tiny training, open-loop comparison까지 통과했다.
- 다음 확장은 route/weather/traffic 수, image size, CUDA LoRA/QLoRA, 반복 closed-loop를 키우는 단계라 RTX 5090이 적절하다.
- H100은 아직 사용하지 않는다. RTX 5090에서 MacBook-equivalent smoke를 재현한 뒤 batch/image/model/LoRA/quantization/offload 축소를 먼저 시도한다.

첫 실행 순서:

```text
1. environment_check
2. carla_collection_smoke
3. training_smoke
4. open_loop
5. closed_loop
6. lora_smoke
```

정확한 command는 `outputs/handoff/5090_manifest.json`의 `first_5090_commands`와 `docs/setup.md`의 RTX 5090 section을 따른다.

### E08 5090 Expansion

- model: LoRA/QLoRA VLM + waypoint/action-token head
- data: expanded CARLA routes/weather/traffic, mini/full dataset subset
- machine: RTX 5090
- metric: open-loop, 5+ closed-loop routes, training throughput, memory peak, failure taxonomy

### E09 H100 Final Ablation

- model: best E08 variants only
- data: expanded CARLA + selected real/sim datasets
- machine: AIP/H100
- gate: E08에서 5090 리소스 한계 또는 large ablation 필요성이 기록됨
- metric: final ablation table, long-run closed-loop score, failure taxonomy, cost/time
