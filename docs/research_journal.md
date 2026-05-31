# 연구일지

이 문서는 프로젝트 생성 시점부터 milestone 진행 상황을 시간순으로 기록한다. 세부 실행 지침은 `TASKS.md`, 환경 재현은 `docs/setup.md`, CARLA Mac 설치는 `docs/carla_mac_setup.md`, 데이터 스키마는 `docs/data.md`를 기준 문서로 둔다.

## 2026-05-29: 프로젝트 초기 구성

목표를 CARLA closed-loop에서 동작하는 VLA 기반 자율주행 agent 구현으로 정했다. 처음부터 대형 VLA를 full fine-tuning하지 않고, MacBook에서 가능한 실험을 최대한 수행한 뒤 리소스 한계가 확인될 때 RTX 5090, 그 다음 AIP/H100으로 확장하는 ladder를 채택했다.

초기 repository 구조를 만들었다.

- `README.md`: 프로젝트 목표, 하드웨어 역할, 전체 폴더 구조 정리
- `project_plan.md`: MacBook -> RTX 5090 -> AIP/H100 진행 전략과 milestone 정의
- `TASKS.md`: coding agent가 순서대로 진행할 canonical task list 작성
- `docs/setup.md`: conda, offline asset, 하드웨어별 환경 정책 정리
- `docs/data.md`: CARLA/nuScenes/NAVSIM/Bench2Drive 데이터 우선순위와 공통 schema 초안 작성
- `docs/research.md`, `docs/experiments.md`: 논문 index, model selection, experiment matrix 정리

초기 코드 layout은 `src/vla_drive/` 아래에 고정했다. simulation, data, model, training, evaluation, utils 영역을 나누고, 각 milestone에서 채울 stub 파일을 먼저 만들었다.

## 2026-05-29: 논문/오프라인 자산 준비

VLA autonomous driving 관련 핵심 논문을 `docs/research/papers/`에 저장하고, 일부는 `docs/research/notes/`에 요약했다. 초기 model 방향은 OpenDriveVLA/AutoVLA를 참고하되, 구현은 custom small VLA baseline으로 시작하기로 했다.

주요 판단:

- 입력은 front RGB, ego state, route command부터 시작한다.
- 출력은 direct control보다 future waypoints in ego frame을 우선한다.
- control은 PID/MPC 계열 controller로 변환한다.
- reasoning/action tokenization은 waypoint regression baseline이 안정된 뒤 확장한다.
- AIP/H100은 MacBook/RTX 5090에서 가능한 축소/최적화 실험을 모두 시도하고, 리소스 한계나 대규모 ablation 필요성이 기록된 뒤에만 사용한다.

MacBook offline environment도 준비했다.

- project-local `.conda` Python 3.10 환경 사용
- `data/offline/wheels/macos-py310-pinned` wheelhouse 기준 설치
- Qwen2.5-VL-3B, nuScenes, Bench2Drive mini, NAVSIM/Bench2Drive/nuscenes-devkit offline repo 준비
- `scripts/check_mac_readiness.py`로 local readiness를 점검하는 흐름 추가

## 2026-05-30: MacBook CARLA 실행 경로 조사

CARLA는 macOS 공식 지원 경로가 아니므로 Windows CARLA 0.9.15를 Apple Silicon Mac에서 실행하는 방법을 실험했다. 처음에는 Sikarugir/Wine10 wrapper와 Windows CARLA runtime을 사용했다.

검증된 부분:

- Windows CARLA 0.9.15 server가 `127.0.0.1:2000` RPC port를 열 수 있음
- Wine prefix 내부 Windows Python 3.7에서 CARLA PythonAPI egg import 가능
- `sensor.camera.depth`, `sensor.camera.semantic_segmentation`은 frame 생성 가능

문제:

- `sensor.camera.rgb` raw buffer가 alpha channel만 채워지고 B/G/R channel이 0이었다.
- PNG 저장 문제가 아니라 renderer backend 문제로 확인했다.
- DXVK, VKD3D, D3DMetal, DXMT 조합을 실험했으나 Sikarugir 단독 경로에서는 RGB가 안정적으로 해결되지 않았다.

이때 생성한 실험용 로그와 임시 산출물은 이후 정리했다.

## 2026-05-31: MacBook CARLA RGB 성공 경로 확정

CrossOver 26.1.0을 설치하고 64-bit bottle `carla-rgb64`를 만든 뒤 D3DMetal backend를 사용했다. 이 경로에서 Windows CARLA 0.9.15 RGB camera가 정상 동작했다.

검증 결과:

- CARLA server port open 확인: `127.0.0.1:2000`
- CrossOver bottle 내부 `C:\Python37\python.exe`에서 CARLA PythonAPI import 확인
- RGB diagnostic에서 `640x360` frame raw `nonzero=921399` 확인
- 이전 실패값은 alpha-only 수준인 `230400`이었다.
- RGB smoke drive 100 frame과 mp4 생성까지 확인

최종 Mac CARLA clean path:

```text
/Applications/CrossOver.app
~/Library/Application Support/CrossOver/Bottles/carla-rgb64
data/offline/simulators/carla/crossover_source/drive_c/CARLA
data/offline/simulators/carla/crossover_source/drive_c/Python37
```

정리 작업:

- 실패한 CrossOver 32-bit bottle `carla-rgb` 삭제
- Sikarugir cask/app 삭제
- `/private/tmp`의 CARLA/DXVK/VKD3D 실험 로그와 다운로드 삭제
- Sikarugir prefix 안 DXVK/VKD3D 임시 잔재 삭제
- 임시 smoke 영상/프레임 삭제

문서화:

- `docs/carla_mac_setup.md`: CrossOver 64-bit bottle + D3DMetal 기준 clean install 문서 작성
- `docs/setup.md`: Mac CARLA 경로를 CrossOver/D3DMetal 기준으로 갱신
- `launchers/01_카를라실행.command`: CARLA 실행 launcher를 CrossOver 기준으로 정리
- `launchers/02_카를라연결확인.command`: CrossOver bottle 내부 Python으로 world name 확인

## 2026-05-31: M1 CARLA Connection 완료

`TASKS.md`의 M1 파일을 구현했다.

구현 파일:

- `src/vla_drive/simulation/carla_client.py`
- `src/vla_drive/simulation/carla_agent.py`
- `src/vla_drive/simulation/route_planner.py`
- `src/vla_drive/simulation/pid_controller.py`
- `src/vla_drive/utils/io.py`
- `scripts/collect_carla_data.py`
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`

구현 내용:

- `CarlaClient.connect()` 구현
- world/weather 설정, actor tracking, cleanup 구현
- synchronous/asynchronous mode와 fixed delta seconds 설정 지원
- 짧은 route waypoint 생성과 ego-frame future waypoint 변환 구현
- route command는 `lane_follow`, `turn_left`, `turn_right` 기본값으로 생성
- pure-pursuit 계열 steering과 proportional speed control을 쓰는 PID waypoint controller 구현
- RGB front camera spawn, callback queue, frame 저장 구현
- `collect_carla_data.py`에서 CARLA route를 실행하고 JSONL/images 저장

실제 검증:

```text
./launchers/01_카를라실행.command
./launchers/02_카를라연결확인.command
```

결과:

- `CARLA_WORLD Carla/Maps/Town01` 출력 확인
- ego vehicle과 RGB camera spawn 확인
- 30초 collection 성공
- `/private/tmp/vla_drive_carla/m1_smoke/metadata.jsonl` 생성
- RGB image 300장 생성
- metadata 300 line 생성

주의:

- Mac CrossOver에서는 CARLA synchronous sensor callback이 안정적이지 않아 default config는 `synchronous_mode: false`로 둔다.
- Linux/Windows official host에서는 synchronous mode를 다시 켜서 사용할 수 있다.
- CrossOver/Wine에서 `/private/tmp` 같은 Unix absolute path는 `Z:\private\tmp...`로 정규화해서 저장하도록 보정했다.

M1 상태는 `[x]`로 갱신했다.

## 2026-05-31: M2 Common Data Schema 완료

M1에서 생성된 실제 CARLA JSONL을 기준으로 common data path를 구현했다.

구현 파일:

- `src/vla_drive/data/schemas.py`
- `src/vla_drive/data/datasets.py`
- `src/vla_drive/data/collate.py`
- `src/vla_drive/data/transforms.py`
- `src/vla_drive/utils/io.py`
- `docs/data.md`

JSONL schema는 `DrivingSample`에 직접 대응한다.

```json
{
  "observation": {
    "sample_id": "carla_000000",
    "timestamp": 758.7,
    "camera_front": "/private/tmp/vla_drive_carla/m1_smoke/images/frame_00000.png",
    "route_command": "lane_follow",
    "ego_speed_mps": 4.35
  },
  "target": {
    "future_waypoints_ego": [[1.61, -0.05], [3.61, -0.00]],
    "steer": 0.0099,
    "throttle": 0.227,
    "brake": 0.0
  }
}
```

구현 내용:

- `JsonlDrivingDataset`이 absolute image path와 metadata-relative image path를 모두 처리하도록 구현
- OpenCV 기반 image loading transform 구현
- `driving_collate_fn`에서 batch tensor와 prompt 생성
- batch output:
  - `images: float32[B, 3, H, W]`
  - `future_waypoints_ego: float32[B, T, 2]`
  - `controls: float32[B, 3]`
  - `prompts: list[str]`
- `JsonlWriter`, `resolve_data_path`, streaming JSONL helper 보강
- 작은 fixture 기반 unit test 추가

실제 검증:

```text
samples 300
image_shape (4, 3, 64, 64)
waypoint_shape (4, 8, 2)
prompt0 Drive with command=lane_follow at speed=4.35 m/s and predict future ego-frame waypoints.
```

테스트:

```bash
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest
```

결과:

```text
6 passed
```

M2 상태는 `[x]`로 갱신했다.

## 2026-05-31: M3-M6 smoke pipeline 완료

M3부터 M6까지 MacBook tiny smoke path를 같은 code path 위에서 구현했다.

구현 내용:

- M3: `DummyDrivingBackbone`, `VLADrivingPolicy`, waypoint prediction loss, dummy forward/loss/backward unit test
- M4: tiny training loop, checkpoint/log output, stage 선택, checkpoint resume 지원
- M5: open-loop ADE/FDE/route deviation/collision proxy metric과 report 생성
- M6: CARLA closed-loop route runner, spawn index, route completion, collision count, aggregate report

실제 검증:

```text
launchers/03_학습.command
```

학습 결과:

```text
initial_loss 13.673857688903809
final_loss   0.6645678281784058
steps        100
```

resume 검증:

```text
checkpoint=checkpoints/m4_dummy/latest.pt
start_epoch=20
global_step=100
```

closed-loop 평가 검증:

```text
launchers/05_평가.command
```

결과:

```text
route_count           5
mean_driving_score    0.12658227848101267
mean_route_completion 0.12658227848101267
total_collisions      0
```

M3, M4, M5, M6 상태는 `[x]`로 갱신했다.

## 2026-05-31: User command launchers 정리

중요 수동 단계는 macOS `.command` launcher로 묶었다. 파일 상단의 파라미터 블록만 수정해서 실행하는 방식을 기준으로 한다.

- `launchers/03_학습.command`: `STAGE`, `RESUME_FROM`, epoch, batch size, image size, max samples, checkpoint/log 경로
- `launchers/04_PID튜닝.command`: target speed, steer gain, speed gain, brake gain grid, spawn start index, route count/time, output summary
- `launchers/05_평가.command`: route count/time, spawn start index, PID gains, report path

CrossOver CARLA는 RPC port가 열릴 때까지 5분 이상 걸릴 수 있으므로 `04_PID튜닝.command`와 `05_평가.command`에 `WAIT_FOR_CARLA_SECONDS=420` 대기 루프를 추가했다.

## 2026-05-31: 보조 스크립트 및 CLAUDE.md 정리

M6 closed-loop 평가에서 CrossOver bottle 내부 Python으로 실행하는 실제 평가 스크립트를 분리했다.

- `scripts/eval_carla_closed_loop.py`: `eval_carla.sh`에서 호출하는 CrossOver Python 기반 closed-loop 평가 실행기. route rollout, collision 집계, report JSON 저장을 담당한다.
- `scripts/render_carla_smoke_video.py`: 수집된 CARLA frame 이미지를 mp4로 합성하는 유틸리티.
- `scripts/render_carla_trajectory_video.py`: ego trajectory와 waypoint를 시각화해 mp4로 저장하는 유틸리티.

커밋 절차와 Claude Code 작업 규칙을 `CLAUDE.md`에 문서화했다.

## 2026-05-31: Phase A — 논문 노트 작성 완료

M7 이후 작업의 기반이 되는 논문 3편의 요약 노트를 `docs/research/notes/`에 완성했다.

- `P01_OpenDriveVLA.md`: 4단계 학습, waypoint tokenization, multi-view visual token 구조. 우리가 참고할 점: waypoint 텍스트 직렬화, frozen→LoRA→trajectory 순서 학습
- `P02_AutoVLA.md`: Qwen2.5-VL-3B 백본, K-disk clustering K=2048, (∆x, ∆y, ∆θ) per 0.5s, 10 token = 5s horizon. SFT loss 구조 (L_LLM + λ_a·L_action, CoT 샘플에 λ_cot=40). GRPO reward 설계
- `P09_Survey.md`: VLA4AD 4단계 진화 (Explainer → Modular → End-to-end → Reasoning-augmented), 우리 위치 매핑 (M1~M6 = Modular, 다음 = End-to-end)

## 2026-05-31: Phase B — Real VLM Backbone 구현 완료

Qwen2.5-VL-3B를 실제 backbone으로 사용하는 training pipeline을 구현하고 Mac MPS에서 smoke run까지 검증했다.

구현 파일:

- `src/vla_drive/models/backbone_vlm.py`: `VLMBackbone.load()` + `encode()` 구현. `AutoModelForImageTextToText` + `AutoProcessor`로 Qwen2.5-VL-3B 로딩. PIL 이미지 → processor → LLM forward → last-layer hidden state mean pool → `[B, 2048]` float32 반환. `freeze=True`이면 `torch.no_grad()` context에서 encode 실행
- `src/vla_drive/training/lora.py`: `apply_lora()` 구현. PEFT `LoraConfig` (rank=8, alpha=16) + `get_peft_model()`. target_modules: `q_proj, k_proj, v_proj, o_proj` (LLM attention, vision encoder는 fused qkv 명칭 사용해 제외)
- `src/vla_drive/data/collate.py`: batch에 `image_paths: list[str]` 추가 (VLM backbone용 PIL 로딩 경로)
- `src/vla_drive/models/vla_policy.py`: `build_vlm_policy()` 팩토리 함수 추가
- `src/vla_drive/training/train.py`: `frozen_vlm` / `lora_vlm` stage 추가, `--model-path / --lora-rank / --lora-alpha` 인자 추가. optimizer는 `requires_grad=True` 파라미터만 대상으로 함
- `scripts/train_lora.sh`: `MODEL_PATH / LORA_RANK / LORA_ALPHA` env 변수 지원 추가
- `launchers/03_학습.command`: VLM 스테이지 파라미터 블록 추가
- `src/vla_drive/configs/base.yaml`: `model.model_path` 필드 추가
- `pyproject.toml`: pytest `slow` mark 등록
- `tests/unit/test_vla_policy_m3.py`: VLM smoke test 2개 추가 (`@pytest.mark.slow`)

실제 검증:

```
frozen_vlm smoke (1 epoch, 2 samples, MPS):
  trainable_params=6   (WaypointHead만)
  TRAINING_OK

lora_vlm smoke (1 epoch, 2 samples, MPS):
  trainable_params=294 (LoRA 288 + WaypointHead 6)
  TRAINING_OK
```

pytest slow 포함 전체 통과:
```
3 passed (VLM tests) + 7 passed (기존 unit tests, not slow)
```

주의:
- Mac bitsandbytes는 GPU 미지원이라 `cadam32bit_grad_fp32` 경고가 출력되지만 학습에는 영향 없음 (AdamW 사용)
- MPS에서는 float16 사용 (bfloat16은 CUDA에서만)
- `frozen_vlm`은 WaypointHead 6개 파라미터만 학습: 메모리 효율적이고 빠름

## 현재 상태 요약

완료:

- 준비 완료 상태 `[x]`
- M1 CARLA Connection `[x]`
- M2 Common Data Schema `[x]`
- M3 Baseline VLA Policy `[x]`
- M4 Training Loop `[x]`
- M5 Open-loop Evaluation `[x]`
- M6 Closed-loop Evaluation Stub `[x]`
- Phase A 논문 노트 작성 `[x]`
- Phase B Real VLM Backbone `[x]`

## 2026-05-31: Phase C — Action Tokenizer 구현 완료

AutoVLA 방식의 이산 action token 학습 pipeline을 구현하고 MacBook CPU smoke run까지 검증했다.

구현 파일:

- `src/vla_drive/models/action_tokenizer.py`: `TrajectoryActionTokenizer` 구현. `fit()`: K-means on (∆x, ∆y) deltas, `encode()`: nearest codebook entry per step → [T] int indices, `decode()`: codebook lookup + cumsum → [T, 2] abs positions. `save()`/`load()` JSON persistence
- `src/vla_drive/models/action_token_head.py`: `ActionTokenHead(hidden_dim, T, K)` → [B, T, K] logits
- `src/vla_drive/training/losses.py`: `action_token_loss()` 추가 (cross-entropy, [B,T,K] logits vs [B,T] targets)
- `src/vla_drive/models/vla_policy.py`: `ActionTokenPolicy`, `build_action_token_policy()`, `build_vlm_action_token_policy()` 추가. `decode_waypoints()` — greedy argmax → tokenizer.decode → [B,T,2]
- `src/vla_drive/training/train.py`: `action_token` stage 추가. `_load_or_fit_tokenizer()` (학습 데이터로 fit 후 저장), `_action_token_step_loss()` helper. `--num-action-tokens`, `--tokenizer-path` 인자 추가
- `scripts/train_lora.sh`: `NUM_ACTION_TOKENS`, `TOKENIZER_PATH` 지원 추가
- `tests/unit/test_action_tokenizer.py`: 5개 단위 테스트 추가

실제 검증:

```
action_token smoke (5 epochs, 20 samples, K=64, MPS):
  tokenizer fitted and saved
  initial_loss=4.21 → final_loss=3.43 (loss_decreased=true)
  TRAINING_OK
```

pytest 전체 (not slow):
```
12 passed
```

주의:
- K > n_samples 에러 방어 로직 추가 (자동으로 K를 min(K, n_samples)으로 캡)
- CARLA tiny smoke (300 samples)에서 K=256 사용 시 충분한 샘플 확보됨
- `decode_waypoints()`가 [B,T,2]를 반환하므로 regression metric과 직접 비교 가능

다음 작업:

1. Phase D: reasoning auxiliary loss 또는 CARLA data 규모 확장을 MacBook에서 가능한 범위까지 먼저 수행
2. MacBook에서는 tiny route에서 시작해 CPU/MPS-safe mode, 작은 LoRA, 작은 batch/image 설정으로 가능한 확장을 계속 시도
3. RTX 5090 전환은 MacBook 리소스 한계와 전환 사유를 기록한 뒤 진행

## 2026-05-31: 프로젝트 장비 전환 구조 수정

프로젝트 구조를 단순한 `Mac tiny -> RTX 5090 medium -> H100 large` 단계가 아니라, 현재 장비에서 가능한 실험을 먼저 끝까지 수행하고 리소스 한계가 확인될 때만 다음 장비로 넘어가는 방식으로 바꿨다.

갱신한 문서:

- `TASKS.md`: 전역 규칙을 Mac-first resource-exhaustion gate로 수정
- `README.md`: 하드웨어 전환 원칙과 역할표 수정
- `project_plan.md`: MacBook -> RTX 5090, RTX 5090 -> H100 전환 조건 구체화
- `docs/setup.md`: scale ladder, 하드웨어 역할, AIP/H100 진입 기준 수정
- `docs/data.md`: CARLA/nuScenes data scale 정책 수정
- `docs/experiments.md`: 장비 전환 기록 양식 추가

## 2026-05-31: Phase D — Reasoning Auxiliary Target 구현

M7의 reasoning auxiliary target을 Mac에서 바로 검증 가능한 route/speed 기반 보조 label로 구현했다.

구현 내용:

- `src/vla_drive/models/reasoning_head.py`: hidden state -> reasoning class logits
- `src/vla_drive/data/collate.py`: `reasoning_targets`, `reasoning_labels` 생성
- `src/vla_drive/models/vla_policy.py`: `ReasoningAuxPolicy`, `build_reasoning_aux_policy()`
- `src/vla_drive/training/losses.py`: `reasoning_aux_loss()`
- `src/vla_drive/training/train.py`: `reasoning_aux` stage, `--reasoning-loss-weight`, `--num-reasoning-labels`
- `tests/unit/test_reasoning_aux.py`: reasoning label heuristic와 forward/backward test

검증:

```text
reasoning_aux smoke:
initial_loss=13.104373931884766
final_loss=8.940935134887695
steps=30
loss_decreased=true
```

Open-loop 비교 report:

```text
outputs/reports/m7_regression_vs_action_token.json
regression ADE=0.6609331727027893, FDE=0.5310325622558594
action_token ADE=0.5860463201999664, FDE=0.5834009408950805
reasoning_aux ADE=7.2080940246582035, FDE=11.141493988037109
```

테스트:

```text
tests/unit/test_reasoning_aux.py + test_action_tokenizer.py + test_vla_policy_m3.py + test_metrics.py
11 passed
```

다음 작업:

1. fast/slow reasoning mode의 최소 smoke 비교를 추가한다.
2. MacBook에서 가능한 CARLA data scale 확장을 먼저 시도하고, 한계가 확인될 때만 5090 전환 기록을 남긴다.

## 2026-05-31: M7 이후 milestone 구조 추가

M7 이후 작업이 끊기지 않도록 `TASKS.md`, `project_plan.md`, `docs/experiments.md`에 후속 milestone을 추가했다. 기준은 MacBook에서 가능한 실험을 먼저 계량하고, 리소스 한계가 문서화될 때만 5090/H100으로 넘어가는 구조다.

추가한 흐름:

- M8: MacBook Scale Envelope — Mac에서 성공 가능한 최대 수집/학습/평가 설정과 실패 설정을 기록
- M9: Dataset Expansion on Mac — nuScenes/Bench2Drive mini subset을 common schema로 변환
- M10: 5090 Handoff Package — Mac 결과와 전환 사유를 5090 재현 bundle로 정리
- M11: RTX 5090 Expansion — 같은 code path를 5090에서 확장하고 H100 필요성을 판단
- M12: H100 Final Scale and Ablation — 5090 한계가 확인된 실험만 H100에서 final run/ablation 수행

실험 matrix도 E06 MacBook Scale Envelope, E07 5090 Handoff, E08 5090 Expansion, E09 H100 Final Ablation 순서로 정리했다.

## 2026-05-31: AGENTS.md 변경 기록 규칙 추가

`AGENTS.md`에 변경내용이 발생하면 `docs/research_journal.md`에 날짜와 함께 기록한다는 규칙을 추가했다.

함께 정리한 내용:

- 프로젝트 방향을 MacBook 가능한 최대 검증 -> MacBook 리소스 한계 기록 후 RTX 5090 확장 -> RTX 5090 리소스 한계 기록 후 AIP/H100 확장으로 갱신
- 규모 규칙도 Mac-first/resource-gated 정책에 맞게 수정

## 2026-05-31: M7 Fast/Slow Reasoning Mode 완료

M7의 마지막 남은 항목인 fast/slow reasoning mode smoke 비교를 구현했다.

구현 내용:

- `src/vla_drive/data/collate.py`: `reasoning_mode=fast|slow` 지원
  - fast: `keep_lane`, `turn_left`, `turn_right`, `slow_or_stop` 4-class label
  - slow: command와 speed bucket을 결합한 6-class label
- `src/vla_drive/training/train.py`: `--reasoning-mode`, 자동 `num_reasoning_labels` 설정
- `scripts/train_lora.sh`, `launchers/03_학습.command`: reasoning mode/loss weight 전달
- `src/vla_drive/evaluation/evaluator.py`: report에 `reasoning_mode` 기록
- `tests/unit/test_reasoning_aux.py`: slow reasoning label test 추가

검증:

```text
fast reasoning_aux:
initial_loss=13.104373931884766
final_loss=8.940935134887695
loss_decreased=true

slow reasoning_aux:
initial_loss=13.202237129211426
final_loss=9.018375396728516
loss_decreased=true
```

Open-loop 비교 report:

```text
outputs/reports/m7_fast_slow_reasoning_comparison.json
fast ADE=7.2080940246582035, FDE=11.141493988037109
slow ADE=7.201081943511963, FDE=11.119636535644531
```

M7 상태는 `[x]`로 갱신했다. 다음 구현 대상은 M8 MacBook Scale Envelope다.

## 2026-05-31: M8 MacBook Scale Envelope 시작

M8의 첫 실행 기반으로 `scripts/run_mac_scale_sweep.sh`를 추가했다. 기본 모드는 CARLA server 없이 현재 수집된 JSONL로 training/open-loop evaluation scale을 계량하고, `RUN_CARLA_CLOSED_LOOP=1`일 때만 짧은 closed-loop smoke를 포함한다.

구현 내용:

- 환경 기록: platform, Python version, metadata sample count, disk free/total
- training sweep: `dummy_overfit`, `reasoning_aux fast`, `reasoning_aux slow`, `action_token`
- open-loop evaluation: 각 checkpoint를 같은 ADE/FDE/route deviation/collision proxy metric으로 평가
- summary output: `outputs/reports/mac_scale_envelope.json`

Smoke 실행:

```text
EPOCHS=1 MAX_SAMPLES_LIST=10 IMAGE_SIZES=64 OUT_DIR=/private/tmp/vla_drive_mac_scale_smoke SUMMARY_PATH=outputs/reports/mac_scale_envelope.json DEVICE=cpu scripts/run_mac_scale_sweep.sh
```

결과:

```text
run_count=4
successful_count=4
failed_count=0
best_by_ade=action_token_i64_n10
closed_loop_status=skipped
```

M8 상태는 `[~]`로 갱신했다. 남은 항목은 CARLA collection scale sweep과 closed-loop scale sweep이다.

## 2026-05-31: M8 MacBook Scale Envelope 완료

M8 scale envelope를 CARLA collection과 closed-loop까지 포함해 실행했다.

최종 실행:

```text
EPOCHS=2 MAX_SAMPLES_LIST="10 20" IMAGE_SIZES="64 128" \
OUT_DIR=/private/tmp/vla_drive_mac_scale_final \
SUMMARY_PATH=outputs/reports/mac_scale_envelope.json \
DEVICE=cpu \
RUN_CARLA_COLLECTION=1 COLLECTION_SECONDS_LIST=3 COLLECTION_RESOLUTIONS=160x90 \
RUN_CARLA_CLOSED_LOOP=1 CLOSED_LOOP_ROUTE_COUNTS="1 5" CLOSED_LOOP_ROUTE_SECONDS=3 \
scripts/run_mac_scale_sweep.sh
```

결과:

```text
training/open-loop runs: 16
successful_count: 16
failed_count: 0
best_by_ade: action_token_i64_n10
collection_status: ok
collection_successful_count: 1
closed_loop_status: ok
closed_loop_successful_count: 2
closed_loop_routes: [1, 5]
```

CARLA collection:

```text
collect_3s_160x90
frames=30
metadata=/private/tmp/vla_drive_mac_scale_final/collections/collect_3s_160x90/metadata.jsonl
```

Closed-loop smoke:

```text
1 route, 3 seconds: mean_driving_score=0.0379746835443038, collisions=0
5 routes, 3 seconds: mean_driving_score=0.0379746835443038, collisions=0
```

MacBook 기준으로 image size 128, max samples 20, four training stages, 3-second collection, 1/5 route closed-loop smoke까지 성공했다. 아직 5090 전환 근거는 없다. 다음 MacBook 실험 범위는 M9 dataset expansion이며, nuScenes mini 또는 Bench2Drive mini subset을 common schema로 변환한다.

M8 상태는 `[x]`로 갱신했다.

## 2026-05-31: M9 Dataset Expansion on Mac 완료

CARLA 외 dataset path로 nuScenes mini를 선택했다. `data/offline/datasets/nuscenes/v1.0-mini.tgz`가 metadata table과 CAM_FRONT 이미지를 포함하고 있어, Bench2Drive보다 M9 stub 파일명과 목표에 직접 맞는다.

구현 내용:

- `scripts/prepare_nuscenes.py`: nuScenes mini tar에서 JSON table을 읽고, 선택한 CAM_FRONT 이미지만 `/private/tmp/vla_drive_nuscenes_mini/images/`로 추출한다.
- common schema 변환: `metadata.jsonl`의 `DrivingSample` record에 image path, ego speed, route command, future ego-frame waypoints 8개, reasoning label을 기록한다.
- `src/vla_drive/configs/nuscenes_open_loop.yaml`: M9 smoke metadata/report path로 갱신했다.
- `docs/data.md`: 변환 command와 route command/reasoning mapping을 문서화했다.

변환 실행:

```text
.conda/bin/python scripts/prepare_nuscenes.py --output-root /private/tmp/vla_drive_nuscenes_mini --max-samples 40 --future-steps 8 --sample-stride 2
```

결과:

```text
sample_count=40
metadata_path=/private/tmp/vla_drive_nuscenes_mini/metadata.jsonl
future_steps=8
sample_stride=2
```

DataLoader 검증:

```text
len=40
front_exists=True
batch_images=(4, 3, 64, 64)
batch_waypoints=(4, 8, 2)
```

동일 metric 비교:

```text
CARLA-trained checkpoint:
ade=5.945708167552948
fde=10.292439889907836
route_deviation=0.6837800443172455
collision_proxy_rate=1.0

nuScenes tiny checkpoint:
ade=1.8858193516731263
fde=4.195649659633636
route_deviation=0.644213505834341
collision_proxy_rate=0.85
```

Report files:

```text
outputs/reports/m9_nuscenes_carla_checkpoint_open_loop.json
outputs/reports/m9_nuscenes_tiny_checkpoint_open_loop.json
outputs/reports/m9_nuscenes_checkpoint_comparison.json
```

주의: nuScenes tiny checkpoint는 같은 40-sample subset에서 20 epoch smoke overfit으로 만든 것이므로 held-out benchmark가 아니다. 목적은 MacBook에서 non-CARLA dataset conversion, DataLoader, training, open-loop evaluation code path가 한 번에 연결되는지 확인하는 것이다.

full nuScenes 변환은 아직 진행하지 않는다. mini tar에서 JSON table을 읽고 선택 이미지만 추출하는 범위는 MacBook에서 가능했지만, full 변환은 image extraction/storage/train-eval 반복 시간이 커져 5090 handoff 근거가 필요하다.

M9 상태는 `[x]`로 갱신했다. 다음 구현 대상은 M10 5090 handoff package다.

검증:

```text
.conda/bin/python -m py_compile scripts/prepare_nuscenes.py
git diff --check
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest -m 'not slow'
```

결과:

```text
15 passed, 2 deselected
```

## 2026-05-31: M10 5090 Handoff Package 완료

MacBook에서 검증한 code path를 RTX 5090으로 넘기기 위한 manifest 생성 스크립트와 첫 실행 command set을 추가했다.

구현 내용:

- `scripts/export_handoff_bundle.sh`: git commit/status, MacBook report 요약, offline path 점검, 5090 첫 실행 command를 `outputs/handoff/5090_manifest.json`으로 기록한다.
- `docs/setup.md`: RTX 5090 첫 smoke command set을 기록했다.
- `docs/experiments.md`: E07 5090 handoff smoke의 전환 사유와 실행 순서를 기록했다.

Manifest 생성:

```text
MANIFEST_PATH=outputs/handoff/5090_manifest.json scripts/export_handoff_bundle.sh
```

결과:

```text
HANDOFF_MANIFEST_OK
manifest_path=outputs/handoff/5090_manifest.json
```

Manifest에 기록된 MacBook 근거:

```text
M8 scale envelope:
run_count=16
successful_count=16
failed_count=0
best_by_ade=action_token_i64_n10
collection_status=ok
collection_successful_count=1
closed_loop_status=ok
closed_loop_successful_count=2

M9 nuScenes mini:
delta_tiny_minus_carla ADE=-4.059888815879821
delta_tiny_minus_carla FDE=-6.0967902302742
```

Offline path 점검에서 `data/offline/wheels/linux-x86_64-cu12`는 현재 MacBook repo에는 없다. 5090 환경에서는 online install 또는 별도 Linux/CUDA wheelhouse 준비가 필요하다. 다른 핵심 path인 Qwen2.5-VL-3B, nuScenes mini, Bench2Drive mini, CARLA config는 존재한다.

전환 방침:

- RTX 5090은 larger CARLA route/weather collection, CUDA LoRA/QLoRA, higher image size, repeated open/closed-loop evaluation을 위한 다음 장비다.
- H100은 아직 사용하지 않는다. 5090에서 MacBook-equivalent smoke를 먼저 재현하고, 리소스 한계가 나오면 batch/image/model/LoRA/quantization/offload 축소를 먼저 시도한다.

M10 상태는 `[x]`로 갱신했다. 다음 구현 대상은 M11 RTX 5090 Expansion이며, 실제 5090 장비가 필요하다.

검증:

```text
bash -n scripts/export_handoff_bundle.sh
MANIFEST_PATH=outputs/handoff/5090_manifest.json scripts/export_handoff_bundle.sh
git diff --check
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest -m 'not slow'
```

결과:

```text
HANDOFF_MANIFEST_OK
15 passed, 2 deselected
```

## 2026-05-31: M10A MacBook CARLA Dataset and VLA Training Extension 완료

5090 handoff 전에 MacBook에서 더 할 수 있는 작업이 남아 있었으므로, 추가 CARLA dataset 수집과 VLA 학습 smoke를 먼저 수행했다.

Mac readiness:

```text
result: no blocking issues
MPS is available
free disk space: 88.1GiB
offline cache: 84.9GiB / 120GiB
```

CARLA dataset 수집:

```text
config=src/vla_drive/configs/carla_mac_dataset.yaml
output=/private/tmp/vla_drive_carla/mac_dataset_60s_320x180
seconds=60
resolution=320x180
frames=600
disk_usage=57M
metadata=/private/tmp/vla_drive_carla/mac_dataset_60s_320x180/metadata.jsonl
```

DataLoader 확인:

```text
len=600
first_image_exists=True
last_image_exists=True
batch_images=(8, 3, 64, 64)
batch_waypoints=(8, 8, 2)
```

Mac MPS 학습 결과:

```text
reasoning_aux:
max_samples=300
epochs=5
steps=190
loss=15.661927 -> 1.794994
open_loop ADE=1.662644
open_loop FDE=3.413585

action_token:
max_samples=300
epochs=5
steps=190
loss=4.184484 -> 3.272334
open_loop ADE=1.884458
open_loop FDE=3.807930
```

Qwen2.5-VL VLA smoke:

```text
frozen_vlm:
model=Qwen2.5-VL-3B-Instruct
device=mps
max_samples=2
epochs=1
steps=2
loss=12.562702 -> 11.732220
open_loop ADE=4.811620
open_loop FDE=3.496264

lora_vlm:
model=Qwen2.5-VL-3B-Instruct
device=mps
lora_rank=2
lora_alpha=4
max_samples=1
epochs=1
steps=1
loss=12.933957 -> 12.933957
open_loop ADE=7.549566
open_loop FDE=11.681428
```

Report files:

```text
outputs/reports/m10_mac_carla_60s_reasoning_aux_open_loop.json
outputs/reports/m10_mac_carla_60s_action_token_open_loop.json
outputs/reports/m10_mac_carla_60s_frozen_vlm_open_loop.json
outputs/reports/m10_mac_carla_60s_lora_vlm_open_loop.json
outputs/reports/m10_mac_carla_60s_vla_training_summary.json
```

Evaluator update:

- `frozen_vlm`과 `lora_vlm` checkpoint도 open-loop evaluator에서 로딩 가능하도록 추가했다.

Mac 한계:

- Qwen2.5-VL frozen VLM은 2 sample smoke 학습/평가가 가능했다.
- LoRA VLM도 1 step smoke와 1 sample 평가가 가능했다.
- 다만 Mac bitsandbytes는 GPU 기능 없이 설치되어 있고 `cadam32bit` 경고를 출력한다. LoRA는 실행 가능성 확인 수준이며, 의미 있는 반복 학습은 매우 느리다.
- 따라서 다음 Mac 실험은 dataset 크기/route 다양성 확장과 dummy/reasoning/action-token 반복 평가가 우선이고, full LoRA 반복은 5090 확장 후보로 남긴다.

M10A 상태는 `[x]`로 추가했다. M11은 여전히 5090 장비에서만 진행한다.

검증:

```text
.conda/bin/python -m py_compile scripts/prepare_nuscenes.py src/vla_drive/evaluation/evaluator.py
git diff --check
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest -m 'not slow'
MANIFEST_PATH=outputs/handoff/5090_manifest.json scripts/export_handoff_bundle.sh
```

결과:

```text
15 passed, 2 deselected
HANDOFF_MANIFEST_OK
```

handoff manifest에도 M10A Mac CARLA/VLA 결과를 추가했다.

## 2026-05-31: M10B User-Editable Mac Command Launchers 완료

사용자가 command 파일 상단 변수만 수정해서 CARLA dataset 수집과 VLA 학습을 반복 실행할 수 있도록 launcher를 확장했다.

구현 내용:

- `launchers/06_데이터수집.command` 추가
  - `SCENE_COUNT`, `SECONDS_PER_SCENE`, `FPS`, `IMAGE_WIDTH`, `IMAGE_HEIGHT`, `TARGET_SPEED_MPS`, `ROUTE_LENGTH`, `TOWN`, `WEATHER`, `OUTPUT_ROOT`를 파일 상단에서 수정한다.
  - CARLA port를 최대 `WAIT_FOR_CARLA_SECONDS=420`초 기다린다.
  - scene 실패 시 `SCENE_RETRY_COUNT`만큼 재시도한다.
- `scripts/collect_carla_scenes.sh` 추가
  - scene별 output은 `scene_000`, `scene_001` 형식으로 저장한다.
  - 전체 metadata는 `${OUTPUT_ROOT}/metadata.jsonl`로 합친다.
- `scripts/collect_carla_data.py` 확장
  - CLI에서 `--seconds`, `--fps`, `--image-width`, `--image-height`, `--target-speed-mps`, `--route-length`, `--town`, `--weather`, `--spawn-seed`를 override할 수 있다.
- `launchers/03_학습.command` 확장
  - `dummy_overfit`, `reasoning_aux`, `action_token`, `frozen_vlm`, `lora_vlm` stage를 파일 상단에서 선택한다.
  - epoch, batch size, max samples, lr, weight decay, grad accumulation, loss weight, early stopping, resume, model path, LoRA rank/alpha를 노출했다.
- `src/vla_drive/training/train.py` 확장
  - `--early-stop-patience`, `--early-stop-min-delta`, `--early-stop-min-epochs` 추가.
  - best epoch를 `best.pt`로 저장하고 summary에 `best_loss`, `stopped_early`를 기록한다.
- `scripts/train_lora.sh` 확장
  - launcher에서 넘기는 optimizer/early-stop/full VLM 관련 옵션을 argparse로 전달한다.
- `launchers/README.md` 갱신

검증:

```text
chmod +x scripts/collect_carla_scenes.sh launchers/06_데이터수집.command launchers/03_학습.command
bash -n scripts/collect_carla_scenes.sh
bash -n launchers/06_데이터수집.command
bash -n launchers/03_학습.command
.conda/bin/python -m py_compile scripts/collect_carla_data.py src/vla_drive/training/train.py
```

Early stopping smoke:

```text
STAGE=dummy_overfit
METADATA_PATH=/private/tmp/vla_drive_carla/mac_dataset_60s_320x180/metadata.jsonl
EPOCHS=3
MAX_SAMPLES=16
BATCH_SIZE=4
EARLY_STOP_PATIENCE=1
EARLY_STOP_MIN_DELTA=1000
EARLY_STOP_MIN_EPOCHS=1
```

결과:

```text
TRAINING_OK
stopped_early=True
best_checkpoint=/private/tmp/vla_drive_early_stop_smoke_ckpt/best.pt
steps=8
```

CARLA 수집 smoke:

```text
SCENE_COUNT=1
SECONDS_PER_SCENE=1
FPS=5
IMAGE=160x90
OUTPUT_ROOT=/private/tmp/vla_drive_carla/command_collect_smoke
```

결과:

```text
RuntimeError: time-out of 30000ms while waiting for the simulator
```

원인:

- `127.0.0.1:2000` port는 열려 있었지만 `02_카를라연결확인.command`도 timeout이 발생했다.
- 즉 CARLA process는 살아 있으나 Python client에 world load 응답을 주지 않는 hung server 상태였다.

대응:

- 수집 script에 port wait와 scene retry를 추가했다.
- 이 상태에서는 `01_카를라실행.command`로 CARLA를 재시작한 뒤 `06_데이터수집.command`를 실행해야 한다.

M10B 상태는 `[x]`로 추가했다.

## 2026-05-31: 데이터 저장 경로 외장 볼륨으로 통일

내장 Mac 디스크 용량 절약을 위해 CARLA 데이터 수집 경로를 모두 `/Volumes/DATASET/vla_drive_carla`로 변경했다. 239GB 외장 볼륨이 `/Volumes/DATASET`에 마운트되어 있다.

변경 파일 (15개):

- `launchers/06_데이터수집.command`: `OUTPUT_ROOT` 변경
- `scripts/collect_carla_scenes.sh`, `eval_carla.sh`, `eval_open_loop.sh`, `run_mac_scale_sweep.sh`
- `src/vla_drive/configs/carla_mac_dataset.yaml`, `carla_rgb_waypoint.yaml`
- `src/vla_drive/configs/nuscenes_open_loop.yaml`
- `scripts/eval_carla_closed_loop.py`, `prepare_nuscenes.py`
- 기타 default metadata/output path가 하드코딩된 나머지 파일

## 2026-05-31: CARLA 실행 및 연결 안정화

### Kill 수정

`01_카를라실행.command`의 KILL_EXISTING이 기존 CARLA 프로세스를 제대로 종료하지 못하는 문제를 수정했다.

- `WINEPREFIX` + `wineserver -k`로 bottle 전체를 종료하는 방식으로 교체
- `pkill -f "CarlaUE4"` / `pkill -f "carla-rgb64"` 패턴 보강

### load_world() timeout 수정

`carla_client.py`에서 `load_world("Town01")` 호출이 30000ms ~ 120000ms timeout을 일으키는 문제를 수정했다.

근본 원인: CARLA는 map 리로드 중 RPC를 일시적으로 차단한다. port는 열려 있어도 요청이 응답을 받지 못했다.

수정:
- `01_카를라실행.command`와 `scripts/run_carla_mac_crossover.sh`에 `CARLA_MAP=/Game/Carla/Maps/Town01`을 전달해 CARLA가 Town01로 초기 로딩되도록 했다.
- `carla_client.connect()`를 `get_world()` 우선으로 변경했다. 현재 map이 이미 Town01이면 `load_world()`를 호출하지 않는다.
- warmup sleep을 120초로 연장했다.

검증: CARLA를 Town01로 시작한 뒤 `get_world()` 경로로 연결 성공. 수집 정상 동작 확인.

### 06 자동 CARLA 실행 추가

`06_데이터수집.command` 실행 시 CARLA가 꺼져 있으면 `01_카를라실행.command`를 자동으로 실행한다. `nc -z` port 확인 후 실행 여부를 결정한다.

## 2026-05-31: AutoVLA I/O 정렬 완료

첫 번째 목표 모델 AutoVLA(Qwen2.5-VL-3B, 논문 P02)의 입출력 구조를 코드베이스 전체에 반영했다. 리소스 제약으로 줄여야 할 경우 우선순위 낮은 항목부터 줄이되, 처음부터 구조를 맞추는 원칙을 채택했다.

**목표 모델 I/O 정의**:

- 입력: 3 cameras (front 0°, front-left -60°, front-right +60°) × 4 temporal frames (t0, t-0.5s, t-1.0s, t-1.5s) = 12 images
- 출력: T=10 future ego waypoints @ 0.5s intervals, (Δx, Δy, Δθ) in ego frame
- Action token: K-means codebook on (Δx, Δy, Δθ) deltas; K=256 (Mac smoke), K=2048 (target)

**구현 파일**:

- `src/vla_drive/data/schemas.py`: `Observation`에 12개 temporal camera 필드 추가 (`camera_front_*_t1/t2/t3`)
- `scripts/collect_carla_data.py`: 전면 재작성. 3 camera spawn, raw frame buffer, post-process로 T=10 ego-frame waypoints 생성. `_world_to_ego_delta()` 구현 (Δx, Δy, Δθ)
- `src/vla_drive/data/collate.py`: `_CAM_KEYS` 3×4 layout 추가. images `[B, 3, 4, 3, H, W]`, waypoints `[B, T, 3]`, `all_image_paths` [B, 12]
- `src/vla_drive/data/datasets.py`: 12개 camera 필드 읽기 지원
- `src/vla_drive/models/action_tokenizer.py`: 3D codebook `(Δx, Δy, Δθ)`. `encode()`/`decode()` 모두 3D. `decode_xy()`로 2D 변환
- `src/vla_drive/models/backbone_vlm.py`: `all_image_paths` [B, 12]를 받아 12개 PIL 이미지로 multi-image encode. 1장 single-image backward compat 유지
- `src/vla_drive/models/waypoint_head.py`: `waypoint_dim` 파라미터 추가 (default=3)
- `src/vla_drive/models/vla_policy.py`: 모든 builder에 `waypoint_dim=3` 기본값 적용
- `src/vla_drive/training/train.py`: `--waypoint-dim` 인자 추가
- `scripts/train_lora.sh`: `--waypoint-count`, `--waypoint-dim` 전달 추가
- `src/vla_drive/configs/base.yaml`: `waypoint_count: 10`, `waypoint_dim: 3`, `waypoint_interval_s: 0.5`, `num_cameras: 3`, `num_frames: 4` 추가
- `src/vla_drive/evaluation/open_loop_metrics.py`: ADE/FDE를 spatial `[..., :2]`만 사용하도록 수정 (Δθ는 단위가 달라 L2 norm에 포함하지 않음)

**Unit test 갱신** (7개 수정, 17 passed):

- `test_waypoint_head.py`, `test_vla_policy_m3.py`, `test_reasoning_aux.py`, `test_action_tokenizer.py`, `test_data_m2.py`에서 `(*, 2)` shape → `(*, 3)` 또는 이에 맞는 fixture 수정

Smoke 검증:

```text
ALL OK: WaypointHead(T=10,dim=3)  DummyPolicy(B=2,T=10,3)  Tokenizer3D
pytest: 17 passed
```

Mac smoke 단계에서는 3 camera 모두 front fallback을 사용하고, temporal history도 동일 frame을 반복하므로 추가 compute 없이 구조 정합성만 확인한다. 실제 3-camera 동기 수집은 CARLA collection에서 검증 예정.
