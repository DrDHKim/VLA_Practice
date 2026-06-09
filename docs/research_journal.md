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

## 2026-06-01: PID 제어기 완전 제거 및 autopilot-only 수집 정리

사용자 지적에 따라 PID 기반 제어 경로를 완전히 제거했다. 수집과 closed-loop 평가는 CARLA Traffic Manager autopilot만 사용한다.

삭제:

- `src/vla_drive/simulation/pid_controller.py`
- `src/vla_drive/simulation/carla_agent.py`
- `launchers/04_PID튜닝.command`
- PID controller unit tests

변경:

- `scripts/collect_carla_data.py`
  - `local_planner`/`basic_agent` fallback 제거.
  - `--driving-stack`은 `autopilot` 또는 `traffic_manager`만 허용.
  - 기본 수집은 `vehicle.set_autopilot(True, traffic_manager_port)`.
  - `use_fixed_path=false`를 기본으로 두고, 실제 autopilot trajectory를 후처리해 future waypoint target을 만든다.
  - camera transform을 `x=2.2, z=2.0, pitch=-8`로 조정했다.
- `scripts/eval_carla_closed_loop.py`
  - PID closed-loop rollout 제거.
  - Traffic Manager autopilot rollout으로 collision과 distance-based route completion을 기록한다.
- `src/vla_drive/configs/carla_mac_dataset.yaml`, `src/vla_drive/configs/carla_rgb_waypoint.yaml`
  - `driving_stack: traffic_manager`
  - `speed_control: desired`
  - `target_speed_mps: 6.0`
  - `use_fixed_path: false`
  - `min_sample_speed_mps: 0.5`
  - `max_sample_brake: 0.2`
- `scripts/collect_carla_scenes.sh`
  - Wine/CrossOver가 non-zero exit을 반환하더라도 metadata가 생성된 경우 scene을 accept하도록 보강했다.

기존 문제 원인 판단:

- throttle/brake 반복은 Traffic Manager에 fixed path와 낮은 target speed 제한을 동시에 걸면서 생긴 oscillation 가능성이 높다.
- 기존 수집 결과는 `throttle`/`brake` 변화가 각각 120회 이상이었고 `brake=0.7` frame이 반복됐다.
- 새 기본값은 fixed path를 끄고 desired speed autopilot으로 주행하며, brake가 큰 frame은 기본적으로 metadata에서 제외한다.

검증 수집:

```text
output=/Volumes/DATASET/vla_drive_carla/autopilot_smoke_8s
seconds=8
fps=10
image=320x180
driving_stack=autopilot
```

결과:

```text
records=10
speed min/mean/max=0.8737 / 3.2621 / 6.4992 m/s
throttle min/mean/max=0.1578 / 0.7808 / 0.85
throttle changes=1
brake min/mean/max=0.0 / 0.0 / 0.0
brake changes=0
steer changes=0
```

생성 파일:

```text
/Volumes/DATASET/vla_drive_carla/autopilot_smoke_8s/metadata.jsonl
/Volumes/DATASET/vla_drive_carla/autopilot_smoke_8s/preview.gif
/Volumes/DATASET/vla_drive_carla/autopilot_smoke_8s/bev_route.png
/Volumes/DATASET/vla_drive_carla/autopilot_smoke_8s/controls_timeseries.png
```

카메라 확인:

- `/Volumes/DATASET/vla_drive_carla/autopilot_smoke_8s/images/frame_00016_front.png`는 도로 전방 시야가 정상으로 저장됐다.

검증:

```text
.conda/bin/python -m py_compile scripts/collect_carla_data.py scripts/eval_carla_closed_loop.py
bash -n scripts/collect_carla_scenes.sh launchers/05_평가.command launchers/06_데이터수집.command scripts/eval_carla.sh
git diff --check
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest -m 'not slow'
```

결과:

```text
13 passed, 2 deselected
```

`rg` 기준 PID 관련 code/test/launcher 참조는 제거됐고, 남은 `PORT_PIDS`는 port process id 변수명이다.

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

## 2026-06-01: CARLA 수집 주행 기본값을 Traffic Manager Autopilot으로 수정

사용자 지적에 따라 데이터 수집 주행 기본값을 `local_planner` fallback에서 CARLA Traffic Manager autopilot으로 바로잡았다. 이전 설명에서 PID 주행처럼 설명한 것은 부정확했다. 현재 수집 파이프라인은 `CONTROL_MODE=autopilot`을 기본값으로 사용하며, 내부적으로 `driving_stack=traffic_manager`로 매핑된다.

변경 내용:

- `src/vla_drive/configs/carla_mac_dataset.yaml`: `driving_stack: traffic_manager`로 변경.
- `src/vla_drive/configs/carla_rgb_waypoint.yaml`: `driving_stack: traffic_manager`로 변경.
- `launchers/06_데이터수집.command`: `CONTROL_MODE=autopilot` 변수 추가.
- `scripts/collect_carla_scenes.sh`: `CONTROL_MODE`를 `collect_carla_data.py --driving-stack`으로 전달.
- `scripts/collect_carla_data.py`: `--driving-stack autopilot` alias를 `traffic_manager`로 normalize.
- `launchers/README.md`: 06 수집 command가 Traffic Manager autopilot 기반임을 명시.

현재 주행 모드:

```text
CONTROL_MODE=autopilot
  -> --driving-stack autopilot
  -> collect_carla_data.py
  -> driving_stack=traffic_manager
  -> vehicle.set_autopilot(True, traffic_manager_port)
```

Traffic Manager 설정:

```text
speed_control=percentage
target_speed_mps=5.0
assumed_speed_limit_kmh=30.0
auto_lane_change=false
ignore_lights_percentage=100.0
ignore_signs_percentage=100.0
ignore_vehicles_percentage=100.0
distance_to_leading_vehicle_m=3.0
```

`local_planner`와 `basic_agent`는 fallback으로만 남겨두었다. 기본 수집 command에서는 사용하지 않는다.

검증:

```text
bash -n scripts/collect_carla_scenes.sh
bash -n launchers/06_데이터수집.command
.conda/bin/python -m py_compile scripts/collect_carla_data.py
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest -m 'not slow'
```

결과:

```text
15 passed, 2 deselected
```

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

## 2026-06-02: Mac CARLA Traffic Manager autopilot 속도 진동 분석

사용자가 `06_데이터수집.command`로 만든 `/Volumes/DATASET/vla_drive_carla/mac_scenes/scene_000/scene.gif`에서 속도가 5~6m/s와 1m/s 이하를 반복하는 현상을 확인했다.

확인 결과:

- `06_데이터수집.command`는 `CONTROL_MODE=autopilot`이고, `scripts/collect_carla_data.py`는 `vehicle.set_autopilot(True, traffic_manager_port)`만 사용한다.
- PID 기반 controller/agent는 삭제된 상태이며 데이터 수집 경로에서는 `apply_control()`을 호출하지 않는다.
- 기존 `scene_000/metadata.jsonl`은 `frame gaps unique [1, 2, 4, 5, 6]`로 연속 프레임이 아니었다.
- 원인은 `max_sample_brake=0.2`, `min_sample_speed_mps=0.5` 필터가 브레이크/저속 프레임을 제거해서 GIF와 control plot에서 실제 브레이크 구간이 숨겨진 것이다.

수정:

- `src/vla_drive/configs/carla_mac_dataset.yaml`, `src/vla_drive/configs/carla_rgb_waypoint.yaml`
  - `min_sample_speed_mps: 0.0`
  - `max_sample_brake: 1.0`
  - `speed_control: percentage`
- 수집 단계에서는 frame quality filtering을 하지 않고, 후처리/학습 dataset filtering에서 별도로 다루는 방향으로 변경했다.

추가 검증:

- `autopilot_async_nofilter_smoke_20s`: 135 records, `frame gaps [1]`, skipped 0. 하지만 Traffic Manager 자체가 `throttle=0.85`와 `brake=0.7`을 반복했다.
- `autopilot_percentage_smoke_20s`: 135 records, `frame gaps [1]`, skipped 0. `speed_control: percentage`도 진동을 제거하지 못했다.
- `autopilot_percentage_3mps_smoke_20s`: 135 records, `frame gaps [1]`, skipped 0. 목표속도 3m/s도 진동을 제거하지 못했다.
- `autopilot_no_speed_control_smoke_20s`: 135 records, `frame gaps [1]`, skipped 0. `speed_control=none`은 평균속도 0.53m/s로 더 나빠졌다.
- `synchronous_mode: true` smoke는 이미지 2프레임만 생성한 뒤 CrossOver exit code 3으로 종료되어 현재 Mac/CrossOver 조합에서는 기본 수집 옵션으로 쓰지 않는다.
- CARLA 0.9.15 예제 코드도 Traffic Manager/traffic simulation을 async에서 실행하면 문제가 생길 수 있고 sync mode로 바꾸라고 경고한다.
  - `PythonAPI/examples/manual_control.py`
  - `PythonAPI/examples/generate_traffic.py`

결론:

- 현재 Mac 수집은 Traffic Manager autopilot으로 돈다.
- 이전 GIF의 “브레이크 없이 속도만 튐”은 frame filtering 때문에 생긴 표시/로그 문제였다.
- frame filtering 제거 후에는 실제 TM autopilot이 비동기 CrossOver 환경에서 throttle/brake를 과격하게 반복하는 것이 보인다.
- `06_데이터수집.command`와 `scripts/collect_carla_scenes.sh`에 `SPEED_CONTROL` 변수를 추가했지만, Mac/CrossOver stop-go의 해결책은 아니었다.
- Mac에서는 RGB camera/schema/metadata smoke와 작은 학습 연결 검증을 우선하고, 안정적인 closed-loop 속도 품질은 같은 code path를 remote Linux/Windows CARLA host에서 재검증해야 한다.

## 2026-06-02: Mac CARLA synchronous mode 수집 복구

사용자 요청에 따라 sync mode를 우선 목표로 다시 조사했다. 모든 smoke output은 dataset volume을 쓰지 않고 프로젝트 루트 `tmp/carla_sync_smokes/`에 저장했다. `tmp/`는 `.gitignore`에 추가했다.

원인:

- 기존 sync 실패는 CARLA sync 자체가 불가능한 문제가 아니라 collector가 sync tick과 camera `sensor_tick`을 잘못 맞춘 문제였다.
- camera는 `sensor_tick=1/fps=0.1s`인데 world fixed delta는 `0.05s`였다.
- 기존 loop는 world tick 1회마다 camera frame 1장을 기다렸고, 실제 camera frame은 2 tick마다 나오므로 두 번째 tick에서 `_queue.Empty`가 발생했다.

수정:

- `scripts/collect_carla_data.py`
  - `--synchronous-mode true|false`, `--fixed-delta-seconds` CLI 옵션 추가.
  - sync mode에서 `ticks_per_sample = round((1/fps) / fixed_delta_seconds)`를 계산한다.
  - 샘플 하나당 world tick을 `ticks_per_sample`회 진행한 뒤 camera frame을 읽는다.
  - sync 진단용 world setting/tick progress 로그를 flush 출력한다.
- `launchers/01_카를라실행.command`
  - 기본 `CARLA_QUALITY=Low`.
  - `CARLA_FPS=30` 변수 추가, 실행 인자 `-fps=$CARLA_FPS`.
- `src/vla_drive/configs/carla_mac_dataset.yaml`, `src/vla_drive/configs/carla_rgb_waypoint.yaml`
  - `synchronous_mode: true`.
- `launchers/06_데이터수집.command`, `scripts/collect_carla_scenes.sh`
  - `SYNCHRONOUS_MODE`, `FIXED_DELTA_SECONDS` 변수 추가.
  - `collect_carla_scenes.sh`의 CARLA 내부 대기 시간을 `CARLA_INTERNAL_WAIT_SECONDS` 변수로 분리하고 기본 300초로 설정.

검증:

1. 직접 collector smoke

```text
output=tmp/carla_sync_smokes/sync_low_fps30_fd005_sampling_8s
seconds=8
fps=10
fixed_delta_seconds=0.05
ticks_per_sample=2
frames_raw=80
frames_valid=15
frame gaps=[1]
speed min/mean/max=4.896 / 4.896 / 4.897 m/s
brake>0.01=0
```

2. `scripts/collect_carla_scenes.sh` 경로 smoke

```text
output=tmp/carla_sync_smokes/collect_scenes_sync_8s
seconds=8
fps=10
fixed_delta_seconds=0.05
frames=15
frame gaps=[1]
speed min/mean/max=3.321 / 4.360 / 5.213 m/s
speed<2=0
brake>0.01=3
```

생성 파일:

```text
tmp/carla_sync_smokes/collect_scenes_sync_8s/scene_000/scene.gif
tmp/carla_sync_smokes/collect_scenes_sync_8s/scene_000/controls_timeseries.png
tmp/carla_sync_smokes/collect_scenes_sync_8s/metadata.jsonl
tmp/carla_sync_smokes/collect_scenes_sync_8s/collection_summary.json
```

주의:

- CrossOver/Wine는 collector가 `CARLA_COLLECTION_OK`를 찍고 metadata를 쓴 뒤에도 process exit code 3을 반환하는 경우가 있다.
- `scripts/collect_carla_scenes.sh`는 metadata가 존재하면 scene을 accept하므로 최종 command는 `CARLA_SCENE_COLLECTION_OK`로 종료된다.
- sync smoke 기준 stop-go는 비동기 smoke 대비 사라졌다.

## 2026-06-02: sync smoke time-series 재검증

사용자가 sync smoke time-series에서 속도와 pedal 진동이 심해 보인다고 지적했다. 표기 문제와 실제 주행 문제를 분리해 확인했다.

확인 결과:

- 표기 문제 있음: sync smoke의 sample interval은 `ticks_per_sample=2`, `fixed_delta_seconds=0.05`이므로 실제 metadata timestamp 간격은 `0.1s`여야 했다.
- 기존 metadata writer는 timestamp를 `frame_index * fixed_delta_seconds`로 저장해 `0.05s` 간격처럼 표시했다. 이 때문에 control graph x축이 2배 압축되어 진동이 더 급격해 보였다.
- `scripts/collect_carla_data.py`를 수정해 sync/async 모두 실제 sample interval 기준 timestamp를 저장하게 했다.

실제 여부:

- pedal 값은 `vehicle.get_control()`에서 읽은 실제 CARLA control 값이므로 표기만의 문제는 아니다.
- timestamp를 `0.1s`로 보정한 뒤 위치 변화 기반 속도와 `vehicle.get_velocity()` 기반 logged speed를 비교했다.
- 위치 기반 속도는 `4.213, 4.695, 5.128, 4.759, 3.598, ... m/s`였고 logged speed는 `4.419, 4.917, 5.213, 3.862, 3.668, ... m/s`였다.
- 평균 차이는 약 `0.278m/s`, 최대 차이는 약 `0.968m/s`로, 속도 변화는 실제 이동에서도 관찰된다.

결론:

- 기존 graph는 x축 timestamp 버그 때문에 실제보다 과장되어 보였다.
- 그러나 throttle/brake 변화와 속도 출렁임 자체는 실제 Traffic Manager control/vehicle motion이다.
- sync mode로 비동기 stop-go 문제는 크게 줄었지만, Traffic Manager가 target speed 근처에서 throttle/brake를 bang-bang 형태로 일부 조절하는 현상은 남아 있다.

## 2026-06-02: N-scene CARLA collection 준비

N개 scene 수집 전에 stale output과 duplicate sample id 문제를 보강했다.

변경:

- `scripts/collect_carla_scenes.sh`
  - `OVERWRITE_SCENE_DIRS` 옵션 추가. 기본값은 `1`.
  - scene 수집 시작 전에 기존 `scene_XXX` 디렉터리를 삭제한다.
  - retry 전에 partial scene dir을 삭제해 이전 metadata를 새 성공으로 오인하지 않게 했다.
- `launchers/06_데이터수집.command`
  - `OVERWRITE_SCENE_DIRS=1` 노출.
- `scripts/collect_carla_data.py`
  - `sample_id`를 `scene_000_000015`처럼 scene directory name을 포함하도록 변경했다.
  - combined metadata에서 scene마다 `carla_000015`가 반복되는 문제를 방지한다.

검증:

```text
.conda/bin/python -m py_compile scripts/collect_carla_data.py
bash -n launchers/06_데이터수집.command scripts/collect_carla_scenes.sh
git diff --check
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest
```

결과:

```text
15 passed
```

## OpenDriveVLA Model Specifications

**Reference**: P01 - OpenDriveVLA: Towards End-to-end Autonomous Driving with Large Vision Language Action Model

**Input Specifications**:
- 3-frontal camera images (multi-view)
- Ego states: Velocity, acceleration, yaw rate
- High-level command: Natural language driving instructions

**Output Specifications**:
- Waypoint sequence: 2D coordinates (x, y) in ego frame for T timesteps
- Tokenized discrete waypoint representation for LLM processing

**Training Data Requirements**:
- Multi-view images from 3 front cameras
- Ego vehicle state information (velocity, acceleration, yaw rate)
- High-level driving commands
- Waypoint labels for trajectory prediction

**Key Implementation Notes**:
- Model uses transformer-based architecture with multi-head attention
- Follows multi-stage training approach (frozen projector → instruction tuning → trajectory tuning)
- Waypoints converted to discrete text tokens for LLM integration

## 2026-06-02: launcher 미연결 파일 정리

`launchers/*.command`에서 시작하는 실행 경로를 기준으로 미사용 후보를 조사하고 정리했다.

삭제:

- `scripts/run_data_collection.py`
- `src/vla_drive/simulation/data_collector.py`
- `src/vla_drive/simulation/high_level_command_generator.py`
- `tests/test_high_level_commands.py`
- `src/vla_drive/models/test_vla_model.py`
- `src/vla_drive/models/transformer.py`
- `src/vla_drive/models/vla.py`
- `scripts/render_carla_smoke_video.py`
- `scripts/render_carla_trajectory_video.py`

판단 기준:

- `06_데이터수집.command`는 `scripts/collect_carla_scenes.sh`를 통해 `scripts/collect_carla_data.py`, `scripts/render_scene_gif.py`, `scripts/render_scene_report.py`를 사용한다.
- 삭제한 `data_collector.py` 계열은 현재 launcher 수집 경로와 연결되지 않은 별도 prototype이었다.
- 삭제한 `models/vla.py` 계열은 `03_학습.command`가 사용하는 `src/vla_drive/models/vla_policy.py` 경로와 연결되지 않은 별도 prototype이었다.
- 삭제한 old render utility는 현재 scene GIF/report renderer로 대체됐다.

검증:

```text
rg -n "run_data_collection|data_collector|high_level_command_generator|test_high_level_commands|models\.vla|VLAModel|TransformerEncoder|test_vla_model|render_carla_smoke_video|render_carla_trajectory_video" .
```

결과:

- 현재 코드 참조는 남지 않았다.
- `scripts/render_carla_smoke_video.py`, `scripts/render_carla_trajectory_video.py` 이름은 과거 연구일지 기록에만 남아 있다.

## 2026-06-02: TASKS 현재 작업 대상 갱신

데이터 수집을 다시 시작하기 전에 `TASKS.md`를 최신 파이프라인 기준으로 정리했다.

변경:

- 현재 구현 대상을 `M10D: Autopilot Sync Dataset Collection and Validation`으로 지정했다.
- M10D를 추가해 MacBook에서 새 sync/autopilot dataset 수집, scene GIF/report 검수, DataLoader smoke, tiny training, open-loop/closed-loop baseline 평가, 문서 기록 순서를 명시했다.
- M3 waypoint output shape를 현재 schema와 맞게 `[B, T, 3]`으로 수정했다.
- M6 목표를 Traffic Manager autopilot baseline 평가로 명확히 했다.
- M10C 완료 기준에서 “brake 반복이 사라짐”처럼 과한 표현을 제거하고, 남은 throttle/brake 변동은 scene report에 드러나야 한다고 정리했다.

## 2026-06-02: route command lookahead 공용화

학습 수집과 이후 모델 closed-loop 평가에서 `route_command`가 같은 기준으로 생성되도록 공용 helper를 추가했다.

변경:

- `src/vla_drive/simulation/route_command.py`
  - CARLA yaw sign convention을 공용화했다.
  - positive yaw delta는 `turn_right`, negative yaw delta는 `turn_left`로 고정했다.
  - lookahead는 `meters` 또는 `frames` mode를 지원한다.
- `scripts/collect_carla_data.py`
  - 기존 hard-coded `20 frames` lookahead 대신 config/CLI 입력을 사용한다.
  - 기본값은 `route_command_lookahead_mode=meters`, `route_command_lookahead_meters=30.0`이다.
  - 필요하면 `route_command_lookahead_mode=frames`, `route_command_lookahead_frames=20`으로 기존 방식에 가깝게 되돌릴 수 있다.
- `scripts/collect_carla_scenes.sh`, `launchers/06_데이터수집.command`
  - route command lookahead mode/meters/frames/yaw threshold 변수를 노출했다.
- `src/vla_drive/simulation/route_planner.py`
  - `next_command()`이 같은 공용 helper를 사용하게 바꿨다.

의도:

- 학습 dataset에서 command가 30m 전에 나오도록 수집했다면, 모델 평가/closed-loop에서도 `30m` lookahead로 같은 command prompt를 넣을 수 있게 한다.
- 기존 `RoutePlanner.next_command()`의 좌우 sign이 수집 label과 반대였던 문제를 제거한다.

검증 예정:

- `tests/unit/test_route_command.py`로 meters/frames lookahead와 CARLA yaw sign convention을 검증한다.

추가 수정:

- CrossOver CARLA bottle은 Python 3.7을 사용하므로 `typing.Literal` import가 실패했다.
- `route_command.py`에서 `Literal` 타입힌트를 제거해 Python 3.7 호환으로 수정했다.

검증:

```text
PYTHONIOENCODING=utf-8 /Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine --bottle carla-rgb64 --cx-app 'C:\Python37\python.exe' -c "..."
```

결과:

```text
turn_right
```

## 2026-06-02: 신호등/앞차/보행자 반응 수집 설정 추가

다음 수집 batch부터 신호등 정지, 앞차 정지, random walker crossing에 따른 감속/정지 샘플을 포함하도록 수집 설정을 바꿨다.

원칙:

- 모델 입력에는 `traffic_light_state`, pedestrian state, lead vehicle state를 직접 넣지 않는다.
- 입력은 기존처럼 RGB image + route command + ego speed를 유지한다.
- 정지/대기/출발 이유는 화면에서 학습하게 두고, target은 Traffic Manager autopilot trajectory/control log를 사용한다.

변경:

- `src/vla_drive/configs/carla_mac_dataset.yaml`, `src/vla_drive/configs/carla_rgb_waypoint.yaml`
  - `ignore_lights_percentage: 0.0`
  - `ignore_signs_percentage: 0.0`
  - `ignore_vehicles_percentage: 0.0`
  - NPC vehicle 수와 walker 수/cross factor/running percentage 기본값 추가
- `launchers/06_데이터수집.command`, `scripts/collect_carla_scenes.sh`
  - `IGNORE_LIGHTS_PERCENTAGE`, `IGNORE_SIGNS_PERCENTAGE`, `IGNORE_VEHICLES_PERCENTAGE`
  - `NPC_VEHICLE_COUNT`, `NPC_VEHICLE_TARGET_SPEED_MPS`
  - `PEDESTRIAN_COUNT`, `PEDESTRIAN_CROSS_FACTOR`, `PEDESTRIAN_RUNNING_PERCENTAGE`
  - 위 변수를 상단에서 조정할 수 있게 했다.
- `scripts/collect_carla_data.py`
  - Traffic Manager autopilot NPC vehicle spawn 추가.
  - walker AI controller와 `world.set_pedestrians_cross_factor()` 기반 random crossing 추가.
  - walker crossing은 랜덤이므로 특정 frame에 사람을 강제로 튀어나오게 하는 deterministic scenario runner는 아니다.

현재 기본:

```text
ignore_lights/signs/vehicles = 0/0/0
npc_vehicle_count = 20
npc_vehicle_filter = vehicle.tesla.model3
pedestrian_count = 30
pedestrian_cross_factor = 0.7
pedestrian_running_percentage = 0.1
```

추가 수정:

- random NPC 차량에 큰 트럭/버스가 섞여 회전 중 멈추는 문제가 있어 기본 NPC vehicle filter를 `vehicle.tesla.model3`로 제한했다.
- `launchers/06_데이터수집.command`, `scripts/collect_carla_scenes.sh`, config에서 `NPC_VEHICLE_FILTER`를 조정할 수 있게 했다.

## 2026-06-03: Mac scene 재수집 skip/overwrite 정책 확인

`06_데이터수집.command` 실행 중 기존 `/Volumes/DATASET/vla_drive_carla/mac_scenes/scene_000` 때문에 수집이 중단됐다.

원인:

- `scripts/collect_carla_scenes.sh`의 기존 skip 정책은 완료된 scene도 에러로 처리했다.
- 기존 `OVERWRITE_SCENE_DIRS=0` 동작은 완료된 scene도 에러로 처리했다.
- combined `metadata.jsonl`은 수집 시작 시 새로 생성되므로 완료된 scene을 skip하려면 scene별 `metadata.jsonl`을 다시 합쳐야 한다.

변경:

- `launchers/06_데이터수집.command`와 `scripts/collect_carla_scenes.sh` 기본 `OVERWRITE_SCENE_DIRS`는 `0`으로 둔다.
- `scripts/collect_carla_scenes.sh`에서 기존 scene에 non-empty `metadata.jsonl`이 있으면 완료된 scene으로 보고 combined metadata에 append한 뒤 다음 scene으로 넘어가게 했다.
- 기존 scene 디렉터리는 있지만 `metadata.jsonl`이 없거나 비어 있으면 incomplete output으로 보고 해당 scene 디렉터리를 지운 뒤 자동 재수집한다.
- `collection_summary.json`에 `collected_scene_count`, `skipped_scene_count`를 기록한다.
- M10D 1번 항목의 scene 수/초/FPS/해상도/overwrite 정책 확인을 완료 처리했다.

재실행:

```bash
open launchers/06_데이터수집.command
```

## 2026-06-03: M10D 현재 수집분 DataLoader/training/open-loop smoke

사용자가 100-scene 수집을 계속 진행하는 동안, 현재까지 쌓인 `/Volumes/DATASET/vla_drive_carla/mac_scenes/metadata.jsonl`로 다음 단계를 먼저 검증했다.

수집 artifact 확인:

- combined `metadata.jsonl` 존재.
- `scene_000`부터 `scene_029`까지 scene별 `metadata.jsonl`, `scene.gif`, `bev_route.png`, `controls_timeseries.png`가 생성된 것을 확인했다.
- 검사 시점 metadata는 수집이 계속 진행 중이라 16,050 rows에서 DataLoader smoke 시점 21,935 rows로 증가했다.

metadata 품질 점검:

```text
rows=16050
scenes=30
rows_per_scene=535
duplicate_sample_id=0
missing_camera_paths=0
frame_gap_counts={1: 16020}
route_command_pct={lane_follow: 70.0, turn_left: 16.6, turn_right: 13.4}
speed_lt_0.5_mps=26.6%
brake_gt_0.2=31.2%
```

판단:

- tiny/smoke 학습에는 충분하다.
- 정지/감속 샘플은 들어왔지만 `max_speed=14.6267m/s`, brake-heavy sample 비율이 있으므로 과속/브레이크 과다 scene 제외 여부는 별도 검수로 남긴다.

검증:

```bash
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest tests/unit/test_data_m2.py tests/unit/test_route_command.py
```

결과:

```text
5 passed
```

DataLoader smoke:

```text
dataset_len=21935
batch_images=(2, 3, 4, 3, 128, 128)
batch_waypoints=(2, 10, 3)
```

Training smoke:

```bash
STAGE=reasoning_aux METADATA_PATH=/Volumes/DATASET/vla_drive_carla/mac_scenes/metadata.jsonl CHECKPOINT_DIR=checkpoints/m10d_reasoning_aux_smoke LOG_DIR=outputs/logs/m10d_reasoning_aux_smoke EPOCHS=3 MAX_SAMPLES=300 BATCH_SIZE=8 IMAGE_SIZE=64 DEVICE=auto LOG_EVERY=10 EARLY_STOP_PATIENCE= NUM_ACTION_TOKENS=64 scripts/train_lora.sh
STAGE=action_token METADATA_PATH=/Volumes/DATASET/vla_drive_carla/mac_scenes/metadata.jsonl CHECKPOINT_DIR=checkpoints/m10d_action_token_smoke LOG_DIR=outputs/logs/m10d_action_token_smoke EPOCHS=2 MAX_SAMPLES=300 BATCH_SIZE=8 IMAGE_SIZE=64 DEVICE=auto LOG_EVERY=10 EARLY_STOP_PATIENCE= NUM_ACTION_TOKENS=64 TOKENIZER_PATH=outputs/logs/m10d_action_token_smoke/action_tokenizer.json scripts/train_lora.sh
```

결과:

```text
reasoning_aux: TRAINING_OK, initial_loss=8.769762, final_loss=1.341324, steps=114
action_token: TRAINING_OK, initial_loss=4.082876, final_loss=0.499608, steps=76
```

Open-loop smoke:

- 1000-sample open-loop 평가는 Mac에서 너무 오래 걸려 evaluator process를 종료하고 128-sample smoke로 낮췄다.

```bash
.conda/bin/python -m vla_drive.evaluation.evaluator --mode open_loop --checkpoint-path checkpoints/m10d_reasoning_aux_smoke/latest.pt --metadata-path /Volumes/DATASET/vla_drive_carla/mac_scenes/metadata.jsonl --report-path outputs/reports/m10d_reasoning_aux_open_loop_smoke.json --batch-size 8 --image-size 64 --max-samples 128 --device auto
.conda/bin/python -m vla_drive.evaluation.evaluator --mode open_loop --checkpoint-path checkpoints/m10d_action_token_smoke/latest.pt --metadata-path /Volumes/DATASET/vla_drive_carla/mac_scenes/metadata.jsonl --report-path outputs/reports/m10d_action_token_open_loop_smoke.json --batch-size 8 --image-size 64 --max-samples 128 --device auto
```

결과:

```text
reasoning_aux: sample_count=128, ADE=1.7072, FDE=3.2278, route_deviation=0.2309, collision_proxy_rate=0.5234
action_token: sample_count=128, ADE=1.7848, FDE=3.2818, route_deviation=0.2269, collision_proxy_rate=0.4844
```

다음:

- 수집이 끝난 뒤 전체 metadata로 품질 리포트를 다시 낸다.
- 과속/브레이크 과다 scene을 제외하거나 재수집한다.
- Traffic Manager closed-loop baseline report를 생성한다.

## 2026-06-03: M10D 현재 수집 scene 기준 balanced training/evaluation

128-sample smoke 이후, 사용자가 "스모크말고 제대로 지금까지 수집된 씬에 대해 수행"을 요청했다. 수집은 계속 진행 중이므로 먼저 현재 combined metadata를 snapshot으로 고정했다.

Snapshot:

```bash
mkdir -p tmp/m10d_current
cp /Volumes/DATASET/vla_drive_carla/mac_scenes/metadata.jsonl tmp/m10d_current/metadata_snapshot.jsonl
```

결과:

```text
metadata_snapshot rows=23005
completed scenes in snapshot=43
```

23,005 rows 전체 1 epoch run을 먼저 시도했지만 Mac 외장 볼륨 이미지 I/O와 12-image sample loading 때문에 너무 느렸다.

시도:

```bash
.conda/bin/python -m vla_drive.training.train \
  --stage reasoning_aux \
  --metadata-path tmp/m10d_current/metadata_snapshot.jsonl \
  --max-samples 23005 \
  --batch-size 32 \
  --num-workers 0
```

관찰:

- `num_workers=2`는 기존 `train()` 내부 collate lambda가 pickle되지 않아 실패했다.
- `num_workers=0`은 실행 가능했지만 23k full-row 1 epoch가 Mac에서 몇 시간 단위가 될 것으로 보여 중단했다.
- `train.py` CLI 기본 `--max-samples=10`이 있어서 full/current run에는 명시적으로 `--max-samples`를 넣어야 한다.

대안:

- 현재 완료된 모든 scene을 반영하되, scene별 100 samples를 균등 추출한 balanced dataset을 만들었다.
- 이는 tiny smoke가 아니라 현재 43개 scene 전체를 대표하도록 고정한 Mac-feasible run이다.

```text
tmp/m10d_current/metadata_scene_balanced_100.jsonl
scenes=43
rows=4300
```

Training:

```bash
.conda/bin/python -m vla_drive.training.train --stage reasoning_aux --metadata-path tmp/m10d_current/metadata_scene_balanced_100.jsonl --checkpoint-dir checkpoints/m10d_current_reasoning_aux_balanced --log-dir outputs/logs/m10d_current_reasoning_aux_balanced --epochs 3 --batch-size 32 --num-workers 0 --image-size 64 --max-samples 4300 --device auto --lr 1e-3 --log-every 25 --reasoning-mode fast --reasoning-loss-weight 0.1
.conda/bin/python -m vla_drive.training.train --stage action_token --metadata-path tmp/m10d_current/metadata_scene_balanced_100.jsonl --checkpoint-dir checkpoints/m10d_current_action_token_balanced --log-dir outputs/logs/m10d_current_action_token_balanced --epochs 3 --batch-size 32 --num-workers 0 --image-size 64 --max-samples 4300 --device auto --lr 1e-3 --log-every 25 --num-action-tokens 64 --tokenizer-path checkpoints/m10d_current_action_token_balanced/tokenizer.json
```

Training results:

```text
reasoning_aux: TRAINING_OK, rows=4300, epochs=3, steps=405, initial_loss=8.505414, final_loss=1.222398, best_loss=2.291778
action_token: TRAINING_OK, rows=4300, epochs=3, steps=405, initial_loss=4.094353, final_loss=0.518425, best_loss=1.376413
```

Open-loop evaluation:

```bash
.conda/bin/python -m vla_drive.evaluation.evaluator --mode open_loop --checkpoint-path checkpoints/m10d_current_reasoning_aux_balanced/latest.pt --metadata-path tmp/m10d_current/metadata_scene_balanced_100.jsonl --report-path outputs/reports/m10d_current_reasoning_aux_balanced_open_loop.json --batch-size 32 --image-size 64 --max-samples 4300 --device auto
.conda/bin/python -m vla_drive.evaluation.evaluator --mode open_loop --checkpoint-path checkpoints/m10d_current_action_token_balanced/latest.pt --metadata-path tmp/m10d_current/metadata_scene_balanced_100.jsonl --report-path outputs/reports/m10d_current_action_token_balanced_open_loop.json --batch-size 32 --image-size 64 --max-samples 4300 --device auto
```

Open-loop results:

```text
reasoning_aux: sample_count=4300, ADE=1.806745, FDE=3.995674, route_deviation=0.520595, collision_proxy_rate=0.330465
action_token: sample_count=4300, ADE=1.880799, FDE=4.234489, route_deviation=0.512368, collision_proxy_rate=0.310465
```

판단:

- 현재 수집분으로 Mac에서 full-current scene coverage 학습/평가 path는 통과했다.
- `reasoning_aux`가 ADE/FDE는 약간 낮고, `action_token`은 collision proxy가 약간 낮다.
- 이 결과는 43 scene balanced subset 기준이며, 수집 완료 후 전체 scene 수 기준으로 다시 snapshot을 고정해야 한다.
- 23k full-row 전체 학습은 Mac에서 너무 느려 RTX 5090 확장 후보로 남긴다.

## 2026-06-04 - 100-scene command-conditioned final training/evaluation

사용자가 "command 기준으로 학습"과 모든 단계의 `launchers/*.command` 실행을 요구했다. 기존 Mac dummy backbone은 prompt/route command text를 쓰지 않고 front image + speed만 사용했으므로, `DummyDrivingBackbone`에 route command one-hot feature를 추가했다.

변경:

- `src/vla_drive/models/backbone_vlm.py`
  - `lane_follow/keep_lane`, `turn_left`, `turn_right`를 3-d one-hot으로 인코딩한다.
  - lightweight Mac training도 image + speed + route command 조건으로 학습된다.
- `launchers/03_학습.command`
  - 주요 학습 인자를 `${VAR:-default}`로 바꿔 launcher를 통한 hyperparameter override가 가능하다.
- `launchers/05_평가.command`, `scripts/eval_carla.sh`
  - open-loop/closed-loop 평가 인자를 launcher 환경변수로 override 가능하게 했다.
  - closed-loop CARLA timeout을 `CARLA_TIMEOUT_SECONDS`로 전달한다.
- `src/vla_drive/training/train.py`
  - 기존 `train_log.jsonl`, `train_summary.json` 저장에 더해 `training_curve.png`를 자동 생성하고 summary에 `training_curve` 경로를 기록한다.
- `scripts/eval_carla_closed_loop.py`
  - 이 CARLA PythonAPI에는 `World.get_client()`가 없어 `client`를 `_run_route()`로 직접 전달하게 했다.
  - route 준비 중 실패해도 spawned actor cleanup이 되도록 `try/finally` 범위를 앞당겼다.
- `AGENTS.md`
  - 데이터 수집, 학습, open-loop 평가, closed-loop 평가는 `launchers/*.command`를 통해 실행한다는 규칙을 추가했다.

Validation:

```bash
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest tests/unit/test_vla_policy_m3.py -q -k 'dummy'
bash -n launchers/03_학습.command
bash -n launchers/05_평가.command
bash -n scripts/eval_carla.sh
```

Result:

```text
2 passed, 2 deselected
launcher/script syntax checks passed
```

Hyperparameter tuning was executed through `launchers/03_학습.command` on the 100-scene balanced metadata:

```text
metadata=tmp/m10d_final/metadata_scene_balanced_100.jsonl
rows=10000
tuning subset=3000 rows
stage=reasoning_aux
image_size=64
batch_size=32
reasoning_loss_weight=0.1
```

Tuning results:

| Run | LR | Final loss | Best epoch loss |
| --- | ---: | ---: | ---: |
| `m10d_final_cmd_tune_lr1e3_rw01` | 1e-3 | 1.4158 | 2.8222 |
| `m10d_final_cmd_tune_lr5e4_rw01` | 5e-4 | 2.6592 | 5.0343 |

Selected `LR=1e-3`.

Final training through `launchers/03_학습.command`:

```text
checkpoint=checkpoints/m10d_final_cmd_reasoning_aux_balanced/latest.pt
samples=10000
epochs=3
steps=939
initial_loss=8.4334
final_loss=3.1133
best_epoch=2
best_epoch_loss=1.7789
training_curve=outputs/logs/m10d_final_cmd_reasoning_aux_balanced/training_curve.png
```

Open-loop evaluation through `launchers/05_평가.command`:

```text
report=outputs/reports/m10d_final_cmd_reasoning_aux_balanced_best_open_loop.json
sample_count=10000
ADE=1.4648
FDE=3.1421
route_deviation=0.4466
collision_proxy_rate=31.58%
```

CARLA closed-loop evaluation:

- Current closed-loop runner evaluates Traffic Manager autopilot, not the learned checkpoint policy.
- 5 routes x 20s failed repeatedly on Mac CrossOver CARLA with streaming connection refused and simulator timeout during map/spawn-point access.
- Reduced sanity run succeeded through `launchers/05_평가.command` with 1 route x 8s.

```text
report=outputs/reports/m10d_final_cmd_tm_closed_loop_min.json
policy=Traffic Manager baseline
routes=1
route_completion=35.76%
driving_score=35.76%
infraction_penalty=1.0000
collisions=0
failure_reason=incomplete
```

Summary report:

```text
outputs/reports/m10d_final_cmd_training_eval_summary.md
```

## 2026-06-04 - Learned-policy CARLA closed-loop evaluation path

이전 closed-loop report는 Traffic Manager baseline이어서 "학습 결과의 CARLA 실시간 평가" 요구를 직접 만족하지 못했다. CrossOver CARLA client는 Windows Python 3.7에서 실행되고, 학습 checkpoint는 Mac `.conda` torch 환경에서 실행되므로 learned-policy closed-loop를 socket bridge 구조로 추가했다.

구조:

- `scripts/serve_policy_inference.py`
  - Mac `.conda` Python에서 checkpoint를 로드한다.
  - local TCP socket으로 RGB frame, ego speed, route command를 받아 waypoint/control/reasoning을 반환한다.
- `scripts/eval_carla_learned_closed_loop.py`
  - CrossOver Windows Python에서 CARLA client를 실행한다.
  - RGB camera frame을 inference server로 보내고, 반환된 control을 `vehicle.apply_control()`에 적용한다.
  - route completion, driving score, collision, reasoning/control record, policy latency를 report에 저장한다.
  - HUD 렌더링을 위해 frame image path, `reasoning_head`, `waypoint_head`, `action_head` status, steer/throttle/brake, acceleration, route waypoints, predicted waypoints를 tick별로 저장한다.
- `scripts/eval_carla_learned.sh`
  - CrossOver wrapper.
- `scripts/render_learned_closed_loop_video.py`
  - learned closed-loop report와 저장된 frame을 읽어 HUD mp4를 생성한다.
  - RGB view, head outputs, steer/throttle/brake bar, acceleration, route wp, pred wp mini-map을 1280x720 canvas에 표시한다.
- `launchers/05_평가.command`
  - `EVAL_MODE=learned_closed_loop`를 추가했다.
  - launcher 내부에서 Mac inference server를 background로 띄우고, Wine CARLA client 평가가 끝나면 server를 정리한다.
  - learned 평가가 끝나면 HUD video rendering까지 이어서 실행한다.
- `src/vla_drive/evaluation/waypoint_control.py`
  - predicted ego-frame waypoints를 평가용 CARLA control로 변환한다.

Validation:

```bash
bash -n launchers/05_평가.command
bash -n scripts/eval_carla_learned.sh
.conda/bin/python -m py_compile scripts/serve_policy_inference.py scripts/eval_carla_learned_closed_loop.py
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python -m pytest tests/unit/test_waypoint_control.py tests/unit/test_vla_policy_m3.py -q -k 'dummy or waypoint_control'
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python scripts/serve_policy_inference.py --checkpoint-path checkpoints/m10d_final_cmd_reasoning_aux_balanced/latest.pt --host 127.0.0.1 --port 8766 --device auto --image-size 64
MPLCONFIGDIR=.matplotlib_cache .conda/bin/python scripts/render_learned_closed_loop_video.py --report-path outputs/reports/m10d_final_cmd_learned_closed_loop_hud_report.json --video-path outputs/reports/m10d_final_cmd_learned_closed_loop_hud.mp4 --fps 5
```

Result:

```text
4 passed, 2 deselected
POLICY_SERVER_READY stage=reasoning_aux device=mps
RENDER_LEARNED_CLOSED_LOOP_VIDEO_OK frame_count=40 fps=5.0
```

Learned closed-loop run:

```bash
EVAL_MODE=learned_closed_loop \
CHECKPOINT_PATH=checkpoints/m10d_final_cmd_reasoning_aux_balanced/best.pt \
CARLA_TOWN=current \
ROUTE_COUNT=1 \
ROUTE_SECONDS=8 \
LEARNED_EVAL_FPS=5 \
LEARNED_CLOSED_LOOP_REPORT_PATH=outputs/reports/m10d_final_cmd_learned_closed_loop_best_min.json \
WAIT_FOR_CARLA_SECONDS=60 \
CARLA_TIMEOUT_SECONDS=90.0 \
ROUTE_COMMAND=lane_follow \
DEVICE=auto \
OPEN_LOOP_IMAGE_SIZE=64 \
bash launchers/05_평가.command
```

Result:

```text
EVAL_CARLA_LEARNED_CLOSED_LOOP_OK
report=outputs/reports/m10d_final_cmd_learned_closed_loop_best_min.json
routes=1
seconds_per_route=8
route_completion=0.13%
driving_score=0.13%
infraction_penalty=1.0000
collisions=0
mean_policy_latency_ms=5.49
mean_policy_roundtrip_ms=6.83
reasoning_counts={slow_or_stop: 40}
```

HUD video run:

```bash
EVAL_MODE=learned_closed_loop \
CHECKPOINT_PATH=checkpoints/m10d_final_cmd_reasoning_aux_balanced/best.pt \
CARLA_TOWN=current \
ROUTE_COUNT=1 \
ROUTE_SECONDS=8 \
LEARNED_EVAL_FPS=5 \
LEARNED_CLOSED_LOOP_REPORT_PATH=outputs/reports/m10d_final_cmd_learned_closed_loop_hud_report.json \
LEARNED_ARTIFACT_DIR=outputs/reports/m10d_final_cmd_learned_closed_loop_hud_artifacts \
LEARNED_VIDEO_PATH=outputs/reports/m10d_final_cmd_learned_closed_loop_hud.mp4 \
WAIT_FOR_CARLA_SECONDS=60 \
CARLA_TIMEOUT_SECONDS=90.0 \
ROUTE_COMMAND=lane_follow \
DEVICE=auto \
OPEN_LOOP_IMAGE_SIZE=64 \
bash launchers/05_평가.command
```

HUD artifact:

```text
video=outputs/reports/m10d_final_cmd_learned_closed_loop_hud.mp4
sidecar=outputs/reports/m10d_final_cmd_learned_closed_loop_hud.json
first_frame=outputs/reports/m10d_final_cmd_learned_closed_loop_hud_frame000.png
report=outputs/reports/m10d_final_cmd_learned_closed_loop_hud_report.json
frames=40
```

HUD includes:

- RGB camera view
- `reasoning_head`: all ticks `slow_or_stop`
- `waypoint_head`: first and final predicted waypoint text
- `action_head`: `N/A for reasoning_aux`
- steer, throttle, brake bars
- speed and acceleration
- route waypoints and predicted waypoints mini-map

2026-06-04 추가 수정:

- `launchers/02_카를라연결확인.command` 기준 현재 평가 서버 world는 `Carla/Maps/Town10HD_Opt`였다.
- `scripts/eval_carla_learned_closed_loop.py` report에 `map_name`과 `town_arg`를 저장하게 했다.
- `launchers/05_평가.command` learned mode 기본 출력 경로를 날짜별 run directory로 바꿨다.

Default learned output layout:

```text
outputs/reports/learned_closed_loop/YYYYmmdd_HHMMSS/
  report.json
  hud.mp4
  hud.json
  run_metadata.json
  policy_server.log
  eval.log
  render.log
  artifacts/
```

Verified run:

```text
run_dir=outputs/reports/learned_closed_loop/20260604_064103
map_name=Carla/Maps/Town10HD_Opt
town_arg=current
video=outputs/reports/learned_closed_loop/20260604_064103/hud.mp4
frame_count=40
fps=5.0
logs=policy_server.log, eval.log, render.log
metadata=run_metadata.json
```

2026-06-04 Town01 재평가:

사용자가 평가 맵을 Town01로 진행하라고 지정했다. `CARLA_TOWN=Town01`로 learned closed-loop를 다시 실행해 report의 `map_name`이 `Carla/Maps/Town01`로 저장되는 것을 확인했다.

```text
run_dir=outputs/reports/learned_closed_loop/20260604_065005
map_name=Carla/Maps/Town01
town_arg=Town01
video=outputs/reports/learned_closed_loop/20260604_065005/hud.mp4
report=outputs/reports/learned_closed_loop/20260604_065005/report.json
frame_count=40
fps=5.0
route_completion=0.074%
driving_score=0.074%
collisions=0
reasoning_counts={slow_or_stop: 40}
```

Driving evaluation table:

| Policy | Eval mode | Routes | Seconds/route | Route completion | Driving score | Infraction penalty | Collisions | Red lights | Offroad | Failure reason |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Traffic Manager baseline | closed_loop | 1 | 8 | 35.76% | 35.76% | 1.0000 | 0 | 0 | 0 | incomplete |
| Learned waypoint policy | learned_closed_loop | 1 | 8 | 0.13% | 0.13% | 1.0000 | 0 | 0 | 0 | incomplete |

판단:

- learned checkpoint가 CARLA에서 실시간으로 추론되고 control이 적용되는 경로는 통과했다.
- 그러나 현재 모델은 closed-loop 시작 상태에서 `slow_or_stop`만 출력하고 throttle을 0으로 유지한다.
- open-loop ADE/FDE는 감소했지만 closed-loop에서는 정지 policy로 붕괴한다. 다음 개선은 stop/start 불균형, speed-conditioned waypoint label, 초기 정지 상태에서 출발해야 하는 샘플 보강, 또는 control head 직접 학습을 우선 확인해야 한다.
- Mac CrossOver CARLA는 map reload 후 streaming timeout이 자주 발생했다. `CARLA_TOWN=current`로 현재 world를 재사용하면 learned 1-route sanity는 성공했다.

2026-06-04 전진 불가 원인 분석과 control horizon 조정:

- Town01 learned eval에서 route waypoint는 첫 점부터 약 2m 앞이었지만, 모델 `waypoint_head[-1].x` 평균은 거의 0m였다.
- 100-scene 학습 데이터의 `speed < 0.5m/s` 샘플은 GT final waypoint가 거의 0m이고 brake 평균이 0.99라서, 정지 입력은 "출발"보다 "계속 정지"로 학습됐다.
- 같은 CARLA frame에 speed만 바꿔 넣으면 speed 3m/s 이상에서 `keep_lane`과 큰 forward waypoint가 나오므로 warm-up은 타당한 평가 우회다.
- 추가로 learned eval의 waypoint-to-control adapter가 `final_x / horizon_seconds`로 desired speed를 계산하므로, 5s horizon은 moving prediction에서도 brake를 유발할 수 있다.
- `launchers/05_평가.command`에 `POLICY_HORIZON_SECONDS`를 추가하고 learned eval 기본값을 2.0s로 설정했다.
- learned eval 시작 전에 policy control을 적용하지 않는 warm-up 구간을 추가했다. 기본값은 `LEARNED_WARMUP_TARGET_SPEED_MPS=3.0`, `LEARNED_WARMUP_SECONDS=8.0`, `LEARNED_WARMUP_THROTTLE=0.7`이며, 3m/s에 도달하거나 최대 시간이 지나면 policy 평가를 시작한다. route completion은 warm-up 이후 위치부터 계산한다.
- `launchers/05_평가.command`만 실행해도 이 설정을 검증할 수 있도록 기본 `EVAL_MODE`를 `learned_closed_loop`, checkpoint를 command-conditioned best checkpoint, route count를 1, CARLA timeout을 90s로 맞췄다.
- `launchers/05_평가.command` 시작 시 `127.0.0.1:2000`이 이미 열려 있으면 실행 중인 CARLA를 그대로 쓰고, 닫혀 있으면 `launchers/01_카를라실행.command`를 자동 실행한 뒤 기다리게 했다.
- learned HUD에 `phase=policy after warmup`, warm-up duration, target speed, post-warmup speed를 표시하게 했다.
- `launchers/05_평가.command` 상단을 사용자 입력값 중심으로 재정리했다. spawn index, 평가 시간, completion 목표 거리, route command, warm-up target/throttle, checkpoint, output directory를 상단에서 바로 조정한다.

2026-06-04 route waypoint conditioned policy 구현:

- 기존 learned eval은 `route_waypoints_ego`를 HUD 비교용으로만 저장했고, 모델 입력은 RGB + ego speed + route command였다.
- `Observation.route_waypoints_ego`와 collate tensor `batch["route_waypoints_ego"]`를 추가해 route centerline waypoint를 모델 입력으로 전달할 수 있게 했다.
- CARLA 수집 metadata에 map waypoint 기반 `observation.route_waypoints_ego`를 저장한다. 이는 `target.future_waypoints_ego`와 분리된 route input이다.
- 기존 Town01 100-scene metadata를 재수집하지 않고 쓸 수 있도록 `scripts/backfill_route_waypoints.py`와 CrossOver wrapper `scripts/backfill_route_waypoints.sh`를 추가했다. 기본 출력은 `tmp/m10d_final/metadata_scene_balanced_100_routewp_town01.jsonl`이다.
- `client.load_world("Town01")`는 CrossOver CARLA에서 streaming connection refused로 서버를 죽일 수 있어, backfill wrapper 기본 town은 `current`로 둔다. 01 launcher가 Town01로 CARLA를 띄운 뒤 current map에서 backfill한다.
- `launchers/03_학습.command`는 route-wp metadata가 없고 raw metadata가 있으면 01 launcher를 자동 실행하고 backfill을 먼저 수행한 뒤 학습한다.
- `DummyDrivingBackbone(use_route_waypoints=True)`는 route waypoint tensor를 flatten해 image/speed/route-command feature와 함께 projection한다.
- `--use-route-waypoints` 학습 옵션과 `USE_ROUTE_WAYPOINTS=1` launcher 기본값을 추가했다. route-conditioned checkpoint는 `checkpoints/m10d_final_routewp_reasoning_aux_balanced`에 저장한다.
- learned closed-loop eval은 CARLA map에서 계산한 route wp를 policy server 요청에 포함한다. checkpoint가 `use_route_waypoints=True`로 학습된 경우 실제 모델 입력으로 사용된다.
- HUD는 `route_wp_input=on/off`를 표시한다. 기존 checkpoint로 평가하면 off, route-wp checkpoint로 평가하면 on이다.

2026-06-04 route waypoint backfill map 정합성 보강:

- 리소스 점검 중 `tmp/m10d_final/metadata_scene_balanced_100_routewp_town01.jsonl`의 `route_waypoint_source.map_name`이 `Carla/Maps/Town10HD_Opt`로 기록된 것을 확인했다.
- 같은 샘플의 GT future waypoint는 2m대부터 시작하지만 잘못 backfill된 route waypoint는 80m대부터 시작해 학습 라벨로 사용할 수 없는 상태였다.
- 잘못된 route-wp 라벨로 진행 중이던 학습 프로세스는 중단했다.
- `launchers/03_학습.command`의 route waypoint backfill 기본 town을 `Town01`로 되돌리고, 기존 metadata가 요청 town과 다르면 `.bad_map_YYYYmmdd_HHMMSS`로 격리 후 재생성하게 했다.
- `scripts/backfill_route_waypoints.py`는 요청한 town과 실제 CARLA map이 다르면 파일을 쓰기 전에 실패하도록 검증을 추가했다.
- MacBook 학습 리소스 점검 결과 route-wp reasoning_aux 학습은 모델 메모리 사용량이 약 0.5GB 수준이고 CPU idle이 남아 있었다.
- DataLoader worker를 늘릴 수 있도록 lambda collate를 top-level callable class로 바꾸고, 03 launcher 기본값을 `BATCH_SIZE=64`, `NUM_WORKERS=2`, `LOG_EVERY=10`으로 조정했다.
- `num_workers=2`, `batch_size=64`, `max_samples=128` dry run은 2 step 정상 종료했다.

2026-06-04 route waypoint 입력 범위 재정리:

- AutoVLA notes와 현재 baseline 문서는 모델 입력을 multi-view/multi-frame RGB, ego state, navigation instruction/route command로 정의한다.
- Raw/local `route_waypoints_ego`를 numeric model input으로 넣는 것은 알고리즘 충실 구현이 아니라 planner prior를 추가한 ablation이다.
- 진행 중이던 route-conditioned 학습은 epoch 1 step 260에서 중단했다.
- `launchers/03_학습.command`의 기본 `USE_ROUTE_WAYPOINTS`는 `0`으로 되돌렸다. route waypoint metadata는 HUD, route adherence 분석, closed-loop 비교, ablation 옵션으로 남긴다.
- `launchers/03_학습.command`는 command-only 기본값일 때 raw metadata와 `m10d_final_reasoning_aux_balanced` checkpoint/log 경로를 사용한다. route-wp 경로는 `USE_ROUTE_WAYPOINTS=1` ablation일 때만 사용한다.
- learned closed-loop eval은 global path에서 local route waypoint를 계산하되, 이를 모델 numeric input으로 쓰지 않고 tick별 `route_command` 생성과 HUD/metadata 기록에 사용한다.
- policy inference server도 command-only checkpoint에서는 `route_waypoints_ego` batch field를 만들지 않고, checkpoint args의 `use_route_waypoints=True`일 때만 ablation input으로 전달한다.

2026-06-04 repo 산출물 정리:

- `.DS_Store`, Python cache, pytest/ruff/matplotlib cache를 repo 작업 트리에서 제거했다.
- `tmp/train_worker_check_*` 1회성 worker dry-run 산출물과 잘못 생성된 Town10 route-wp backfill 파일을 제거했다.
- `outputs/reports/learned_closed_loop/`의 오래된 날짜별 run 4개를 제거하고 최신 run 1개만 남겼다.
- smoke report/checkpoint/log 산출물(`m10d_action_token_smoke`, `m10d_reasoning_aux_smoke`)을 제거했다.
- `outputs/reports/m10d_current_prediction_examples/`, `outputs/reports/m10d_scene_quality/`, `scene_031_contact_sheet.png` 등 1회성 분석 산출물을 제거했다.
- checkpoint는 현재 기본 command-only 평가 후보인 `checkpoints/m10d_final_cmd_reasoning_aux_balanced/`만 남기고 smoke/current/tune/route-wp ablation checkpoint를 제거했다.
- 기존 tracked `outputs/reports/*.json` 결과 파일을 제거 대상에 포함하고, 새 report 산출물이 다시 git에 잡히지 않도록 `.gitignore`에 `outputs/reports/`를 추가했다.
- `tmp/m10d_current/`와 `tmp/m10d_final/metadata_snapshot_100_scenes.jsonl` 과거 metadata snapshot을 제거했다. 현재 기본 command-only 학습/평가는 `tmp/m10d_final/metadata_scene_balanced_100.jsonl`을 사용한다.

2026-06-04 VLA 아키텍처 방향 결정 (진짜 AutoVLA로 전환, M4는 PoC만):

- 현재 `frozen_vlm`/`lora_vlm`(`build_vlm_policy`→`VLADrivingPolicy`)은 Qwen2.5-VL-3B 마지막 hidden state를 mean-pool한 뒤 MLP waypoint head로 궤적을 회귀한다. VLM을 frozen feature extractor로만 쓰고 추론 텍스트 생성도, 자기회귀 action token 생성도 없다 → AutoVLA 충실 구현이 아니라 단순화 버전이다.
- AutoVLA 원안: VLM이 멀티뷰 이미지+명령을 받아 chain-of-thought 추론 텍스트를 생성하고, 이어 궤적을 이산 action token으로 자기회귀 생성한다(행동이 LM 디코더 출력의 일부). 학습은 SFT(+RL).
- 결정: (B) 진짜 AutoVLA 방식으로 간다. 데이터를 `명령+이미지 → (추론 텍스트 + action token열)` instruction 시퀀스로 구성하고, VLM(LoRA)을 next-token loss로 학습해 추론+행동 토큰을 생성하게 하며, 추론 시 generate로 토큰을 뽑아 궤적을 디코드한다. 이 생성 경로(데이터 포맷·loss·inference)는 아직 미구현이며 다음 작업이다.
- 리소스: 현재 머신 Apple M4 / 32GB / MPS. frozen Qwen2.5-VL-3B forward 실측 — 단일 이미지 0.48 samp/s(배치 1/2/4/8 모두 평평 = MPS compute-bound, 메모리 9~10GB 여유), 12-view(3캠×4프레임) 28.5s/샘플(0.04 samp/s, 14.3GB). batch를 키워도 throughput이 안 늘어 "리소스 최대화"로 속도를 못 올린다. generate는 forward보다 더 비싸다.
- 따라서 M4에서는 진짜 AutoVLA 본학습이 비현실적이다(12-view 풀학습 추정 ~633시간). M4는 데이터 포맷/학습 파이프라인 검증용 소규모 PoC만 수행하고, 본학습은 GPU(H100/RTX5090)에서 한다.
- M4 PoC 절충: AutoVLA 3카메라는 유지하되 시간축을 1프레임으로 줄여 샘플당 3장만 VLM에 넣는다. `collate.driving_collate_fn`에 `vlm_frames_per_camera`(기본 4=12장 하위호환, 1=3장) 옵션을 추가하고 `_build_all_image_paths(frames_per_camera)`로 슬라이스한다. `--vlm-frames-per-camera` 학습 인자와 `VLM_FRAMES_PER_CAMERA` launcher 변수로 연결했다.
- `launchers/03_학습.command` 기본 STAGE를 `frozen_vlm`으로 두고, STAGE별 분기를 추가해 VLM 스테이지에서는 route_waypoints/reasoning head를 쓰지 않고 명령을 프롬프트 텍스트로 전달한다. M4 PoC 기본값은 `VLM_FRAMES_PER_CAMERA=1`, `MAX_SAMPLES=1500`, `EPOCHS=3`, `BATCH_SIZE=4`, `LR=5e-4`이며 checkpoint/log는 `checkpoints|outputs/logs/m10d_final_frozen_vlm`이다.
- 주의: 현재 `frozen_vlm`은 여전히 회귀 head 방식이다. 진짜 AutoVLA(추론텍스트+action token 자기회귀 생성)는 별도 구축이 필요하며, 위 03 설정은 그 PoC를 위한 발판이다. 학습에는 `/Volumes/DATASET` 마운트가 필요하다(현재 미마운트).

2026-06-04 LoRA-VLA(진짜 AutoVLA) PoC 1단계 — instruction 데이터 포맷터:

- PoC 설계 확정: action=스페셜 토큰 `<act_i>`, 추론=템플릿 합성, 코드북 K=256, 이미지=3카메라 현재프레임, 모델=lora_vlm(생성 학습). frozen+회귀 head로는 토큰 생성이 불가하므로 PoC는 사실상 lora_vlm이다.
- `src/vla_drive/data/autovla_format.py` 추가: DrivingSample → SFT 예시 `{prompt, completion, image_paths, reasoning, action_token_ids}`.
  - completion = 추론 문장 + ` Trajectory: ` + `<act_i>`×waypoint_count. `TrajectoryActionTokenizer.encode`로 궤적[10×3]→10토큰.
  - `encode_action_text`/`parse_action_text`(정규식 라운드트립), `action_special_tokens(K)`(LM 토크나이저에 등록할 스페셜 토큰 목록) 제공.
  - 추론 텍스트는 command/speed/brake 규칙 템플릿(데이터에 CoT가 없어 teacher 증류 대체). explicit reasoning이 있으면 우선 사용.
  - 프롬프트 라벨 마스킹(assistant 구간만 loss)은 2단계 학습 collator에서 처리.
- `scripts/build_autovla_dataset.py` 추가: 메타데이터 → tokenizer fit → 예시 JSONL + `.codebook.json` + `.special_tokens.json` 저장.
- 검증: 단위테스트 `tests/unit/test_autovla_format.py` 3개 통과(토큰 라운드트립/추론 템플릿/예시 구조). 실제 메타데이터 500샘플 dry-run 정상 — 예) `lane_follow 4.9 m/s` → "…cruising at 4.9 m/s; following the current lane… Trajectory: <act_1>…<act_154>"(10토큰). 포맷터/빌더는 경로만 쓰므로 `/Volumes/DATASET` 미마운트로도 동작.
- 다음 2단계(lora_vlm 생성 학습): Qwen 토크나이저에 action 스페셜 토큰 등록 + 임베딩/lm_head 학습 포함, chat 포맷 + 프롬프트 라벨 마스킹 next-token loss. 3단계: `generate`로 토큰 생성 → 궤적 디코드 → eval/HUD 연결. 본학습은 GPU, M4는 소규모 PoC.

2026-06-04 LoRA-VLA PoC 2단계 — 토큰 등록 + chat 라벨 마스킹 collator:

- Qwen2.5-VL-3B 토크나이저에 `<act_i>` 스페셜 토큰 등록 검증: 256개 추가 시 base vocab 151665→151921, 각 `<act_i>`가 **단일 token id**로 매핑(5 action→5 token), decode→parse 라운드트립 정확. resize_token_embeddings는 학습 스크립트에서 호출 예정.
- `src/vla_drive/data/autovla_sft.py` 추가:
  - `register_action_tokens(tokenizer, K)` — 스페셜 토큰 등록(추가 개수 반환).
  - `build_chat_messages(prompt, completion, num_images)` — full(user[이미지×N+텍스트]+assistant[completion]) / prompt-only 메시지 쌍.
  - `mask_prompt_prefix(input_ids, prompt_len)` — 프롬프트 구간을 `-100`으로 마스킹.
  - `AutoVLASFTCollator(processor)` — full/prompt를 chat 템플릿+processor로 토크나이즈해 `input_ids/labels/pixel_values` 생성. prompt(이미지 포함) prefix 길이로 labels 마스킹, padding도 -100. (런타임에 이미지 픽셀 필요.)
- 검증: `tests/unit/test_autovla_sft.py` 3개 통과(마스킹/메시지 구조/토큰 등록). 단위테스트 누계 6개(format 3 + sft 3) 통과. 텍스트/마스킹 로직은 이미지 없이 검증, 멀티모달 collate 런타임은 `/Volumes/DATASET` 마운트 필요.
- 남은 작업: (2-b) `scripts/train_autovla_lora.py` — Qwen2.5-VL 로드 + 스페셜토큰 resize + LoRA(+embed/lm_head trainable) + 위 collator로 next-token SFT. (3) generate 추론→`parse_action_text`→tokenizer.decode로 궤적 복원→eval/HUD. 둘 다 실제 실행은 GPU/데이터 마운트 필요(M4는 소규모 PoC만).

2026-06-04 LoRA-VLA PoC 2-b·3단계 — 생성 학습 스크립트 + 추론 디코드 (골격; 실학습은 GPU/마운트 필요):

- `training/lora.apply_lora`에 `modules_to_save` 인자 추가. AutoVLA 학습 시 `["embed_tokens","lm_head"]`를 full 학습해 새 `<act_i>` 토큰 임베딩/출력 행을 실제로 학습한다.
- `scripts/train_autovla_lora.py` 추가: instruction JSONL+codebook → Qwen2.5-VL 로드 → `register_action_tokens` + `resize_token_embeddings` → `apply_lora(+embed/lm_head)` → `AutoVLASFTCollator`로 next-token SFT(`model(**batch).loss`) → adapter/processor/codebook/summary 저장. 기본 batch_size=1·grad_accum=4(VLM 메모리).
- `src/vla_drive/models/autovla_generate.py` 추가: `decode_trajectory_from_text`(생성텍스트→parse→tokenizer.decode→[T,3], 순수·테스트가능), `load_autovla`(base+LoRA adapter+processor+codebook), `generate_trajectory`(prompt-only chat→`model.generate`→디코드).
- 검증: `tests/unit/test_autovla_generate.py` 2개 포함 AutoVLA 단위테스트 8개 통과, 전체 33개 통과, 관련 파일 컴파일 OK. 실제 학습/generate는 3B VLM+이미지라 GPU/`/Volumes/DATASET` 마운트에서만 실행(여기선 미실행).
- 실행 절차(데이터/GPU 준비 시):
  1) `python scripts/build_autovla_dataset.py --metadata-path tmp/m10d_final/metadata_scene_balanced_100.jsonl --output-path tmp/autovla/train.jsonl --num-tokens 256 --frames-per-camera 1`
  2) `python scripts/train_autovla_lora.py --instruction-path tmp/autovla/train.jsonl --codebook-path tmp/autovla/train.codebook.json --output-dir checkpoints/m10d_autovla_lora --num-tokens 256 [--max-samples N]`
  3) `autovla_generate.generate_trajectory(...)`로 추론 후 기존 waypoint_control 어댑터로 CARLA 평가 연결(eval 통합은 후속).
- 미해결/후속: M4 단일 step generation SFT 실측, eval(`serve`/05) 경로에 generate 모델 연결, 추론 텍스트 teacher 증류 품질 개선.

2026-06-04 LoRA-VLA PoC 실학습 스모크 검증 + 전용 런처:

- `/Volumes/DATASET` 마운트 확인 후 실제 학습 스모크 수행(2~4샘플, 1~2 epoch): Qwen2.5-VL 로드 → action 토큰 16개 등록·임베딩 resize → LoRA(+embed/lm_head) → 실이미지 `AutoVLASFTCollator` → `model(**batch).loss` → backward → adapter 저장까지 **엔드투엔드 정상 동작** 확인.
- 버그 발견·수정: MPS에서 `dtype=float16`로 학습 시 step 2부터 loss=NaN(fp16 backward 불안정). `train_autovla_lora.py` 학습 dtype을 MPS/CPU=fp32, CUDA=bf16으로 변경하니 loss 7.09→6.20로 유한·감소 확인. inference dtype도 CUDA만 fp16, 그 외 fp32로 정리.
- 성능: M4 fp32에서 3카메라(3장) 기준 step당 수십 초로 느리다. 따라서 M4는 `MAX_SAMPLES` 작은 PoC만, 본학습은 GPU.
- `launchers/07_AutoVLA학습.command` 추가: (1) instruction 데이터셋 생성(없거나 `REBUILD_DATASET=1`) → (2) `train_autovla_lora.py` 실행. `.conda` MPS 파이썬으로 돈다(CrossOver 아님). M4 PoC 기본값 `NUM_TOKENS=256`, `FRAMES_PER_CAMERA=1`, `MAX_SAMPLES=48`, `EPOCHS=2`, `BATCH_SIZE=1`, `GRAD_ACCUM_STEPS=4`, `LR=1e-4`, `LORA r/a=8/16`, 출력 `checkpoints/m10d_autovla_lora`. 첫 샘플 이미지 경로로 마운트 여부도 점검.
- 03_학습.command(frozen_vlm=특징추출+회귀 head)과 07_AutoVLA학습.command(진짜 생성 VLA)은 다른 파이프라인임을 명확히 분리했다.

2026-06-05 AutoVLA LoRA 학습 하이퍼파라미터 M4 실측 튜닝:

- 목표: 이 MacBook(M4/32GB/MPS)에서 GPU(MPS)·통합메모리를 최대 활용하도록 AutoVLA LoRA 학습 파라미터 튜닝.
- 실측(fp32, batch=1, 3카메라 현재프레임, trainable 626M=full embed+lm_head+LoRA):
  - 이미지 원본(seqlen 1006) = 103s/step, 384²(seqlen 697) = 98s/step, 224²(seqlen 301) = 24s/step.
  - 메모리는 세 경우 모두 약 44~45GB로 보고됨(32GB 초과 → MPS 스왑). 그래도 크래시 없이 동작.
- 결론:
  - **이미지 해상도가 속도 지배 인자.** 224로 줄이면 ~4배 빠름(vision token 수 ↓). 본격 학습 전 image_size를 낮추는 게 M4 최대 레버.
  - **배치는 의미 없음**(MPS compute-bound: 앞 forward 벤치에서도 throughput 평평). batch=1 고정, effective batch는 grad_accum으로.
  - **fp32 필수**(fp16=NaN). 메모리는 trainable 626M(full embed/lm_head)+fp32가 지배해 이미 포화(스왑) → "VRAM을 더 채워 가속"은 불가, 이미 한계. 대규모는 GPU가 정답.
- `launchers/07_AutoVLA학습.command` 기본값 갱신: `IMAGE_SIZE=224`(0=원본 느림), `MAX_SAMPLES=150`, `EPOCHS=2`, `BATCH_SIZE=1`, `GRAD_ACCUM_STEPS=4`, `LR=1e-4`, `LORA r/a=8/16`. 예상 소요 ≈ MAX_SAMPLES×EPOCHS×24s(@224) → 150×2 ≈ 2시간.
- 후속(메모리 완화): full embed/lm_head 대신 신규 토큰 행만 학습하면 trainable/옵티마이저 메모리를 크게 줄여 스왑을 없앨 수 있다(현재 미구현, 안정성 문제 시 적용).

2026-06-05 AutoVLA LoRA PoC 첫 실학습 완료 + 추론 점검:

- `07_AutoVLA학습.command`(IMAGE_SIZE=224, MAX_SAMPLES=150, EPOCHS=2)로 첫 실학습 완료: 300 step, loss 7 → 0.03(best 0.027). 체크포인트 `checkpoints/m10d_autovla_lora/`에 adapter/processor/tokenizer/codebook/summary 저장됨.
- 주의: 150샘플·2epoch + 템플릿(결정론) 추론 + 저엔트로피 action 토큰이라 **loss가 0.03까지 떨어진 것은 과적합 신호**이지 주행 품질 지표가 아니다. 의미있는 평가엔 더 많은 데이터 + held-out + closed-loop가 필요.
- `scripts/autovla_generate_smoke.py` 추가(체크포인트 로드→실샘플 generate→추론문장/action토큰/디코드 궤적 vs GT 출력). `load_autovla`로 base+adapter+processor+codebook 로드는 정상 확인.
- 그러나 generate 실행 시점에 `/Volumes/DATASET`가 다시 언마운트되어 이미지 로드 실패 → generate 스모크는 **마운트 복구 후 재실행 필요**. 실행: `.conda/bin/python scripts/autovla_generate_smoke.py --sample-index <존재하는 idx>`.
- 다음: (재마운트 후) generate 스모크로 "추론문장+action토큰 생성→궤적 디코드" 확인 → 데이터/샘플 확대 → eval(05/serve) 연결.

2026-06-05 AutoVLA generate 스모크 — 파이프라인 동작 확인 + mode collapse:

- DATASET 재마운트 후 `autovla_generate_smoke.py`로 실샘플 5개 생성 성공: 추론문장 + `Trajectory:` + action 토큰 + 궤적 디코드까지 **엔드투엔드 동작 확인**(진짜 AutoVLA 생성 경로 검증 완료). 추론문장이 프롬프트 속도를 반영(4.9/4.3/5.2 m/s 각기 다름).
- 그러나 모든 샘플에서 action 토큰이 `<act_4>`만 9회 반복으로 **mode collapse**. 입력 조건에 따른 다른 궤적을 못 냄. 원인: 학습 150샘플이 거의 lane_follow 순항(직진)이고 action 분포가 저엔트로피라, 모델이 다수 패턴 하나로 수렴(앞서 본 loss 0.03 과적합과 일치).
- 부차 관찰: EOS가 1토큰 일찍 나와 10개 중 9개만 생성(`<|im_end|>`). pred(9)≠GT(10)로 ADE 미산출 — generate를 waypoint_count로 맞추거나 decode에서 길이 보정 필요(소소).
- 결론: 배선·생성·디코드는 검증됨. 품질을 보려면 **회전/정지 포함 균형 데이터 + 샘플 확대 + (가능하면) GPU 본학습**이 필요. 150샘플 PoC로는 다수클래스 붕괴가 당연.
- 신규 파일 `scripts/autovla_generate_smoke.py`(존재하는 이미지 샘플만 사용, 누락 skip).

2026-06-05 AutoVLA collapse 원인 진단(에폭/데이터 의문 해소):

- "에폭2까지 안 돈다" 오해 해소: `range(EPOCHS=2)` = epoch 0,1 각 150 step = 300 step으로 **2에폭 정상 완주**. 로그가 0-인덱스라 헷갈림. `train_autovla_lora.py` 로그를 1-인덱스(`epoch+1`, `epochs` 동반)로 변경.
- "데이터 충분한데 직진만" 검증: 학습 첫 150행에 route_command turn_left 27 + turn_right 49(=51%) 존재, |final_y|>3 실제 큰 회전도 19개. 전체 10000행은 turn_left 1530 + turn_right 1518. **데이터에 회전은 충분하다.**
- 진짜 원인 = **action 토큰 다수클래스 붕괴**: 첫150 토큰 빈도 token1(정지)=743(~50%), token4(전진)=301(~20%), 회전 고유 토큰은 희소. generate 결과 순항 샘플→`<act_4>` 반복, 회전 샘플→`<act_1>` 반복(디코드 final xy≈0, GT는 (10,−14.9), ADE≈10). 추론 문장은 명령 반영해 정확("turning right at the intersection")하나 궤적은 빈도 1·2위 토큰만 출력.
- 해석: next-token CE는 다수 토큰만 찍어도 loss가 낮아져(0.03=주변분포 암기) **조건부(이미지→기동) 학습이 안 됨**. 150샘플로는 이미지→회전 신호 부족 + 토큰 불균형(특히 trailing stop=token1)으로 collapse가 필연. trajectory의 약 50%가 정지토큰인 것이 핵심.
- 후속 수정안(택1 이상): (a) action-token loss에 inverse-frequency 가중/포컬로 정지·전진 다운웨이트, (b) trailing stop 토큰 trim 또는 horizon 단축으로 token1 비중↓, (c) 셔플·command 균형 샘플링으로 MAX_SAMPLES 확대(첫N 슬라이스 탈피), (d) 데이터 수천+ GPU 본학습. 실효 검증은 GPU 필요.

2026-06-05 AutoVLA collapse 대응: 전체데이터 학습 + action-token 손실 가중 + grad checkpointing:

- 전체 데이터 학습: `07_AutoVLA학습.command`에서 `MAX_SAMPLES=0`=전체 10000 사용(빈 배열 가드로 `--max-samples` 생략), DataLoader shuffle=True로 epoch마다 섞음("첫 N 슬라이스" 문제 해소). M4 추정 ≈ 67h/epoch → 실질 GPU용.
- 손실 가중(붕괴 방지): `train_autovla_lora.py`에 `_build_action_class_weights` 추가. 학습 데이터 action 토큰 빈도로 `w=(1/freq)^0.5`, 평균 1 정규화 + `[1/cap, cap]` 클립. **action 토큰에만** 적용(추론 텍스트 토큰=1.0). model 내부 균일 CE 대신 logits로 weighted `cross_entropy`(라벨 마스킹 유지) 계산. 토글 `--balance-action-loss`(기본 1), `--action-weight-power`(0.5)/`--action-weight-cap`(5.0). 런처에 `BALANCE_ACTION_LOSS` 등 연결.
- OOM 대응: weighted CE가 logits를 따로 물려 MPS watermark(42.4GB) 초과 OOM 발생(626M full embed/lm_head 학습이 근본 부담). `--gradient-checkpointing`(기본 1) 추가(`use_cache=False`+`gradient_checkpointing_enable`+`enable_input_require_grads`)로 활성화 메모리 절감 → 해결. GPU에도 이득.
- 로그 1-인덱스화(`epoch+1`, `epochs`).
- 검증(M4, 4샘플 스모크): weighted loss 정상 동작, loss 5.97→3.48로 유한·감소(이전 7→0.03 붕괴와 달리 0으로 안 떨어짐=다수토큰 치트 억제). NaN/OOM 없음.
- 한계: 실효(회전 실제 학습) 검증은 데이터 수천+ epoch 필요 → GPU 본학습에서 확인.

2026-06-05 AutoVLA 학습 체크포인트 2단계 + 완전 resume:

- 장시간(M4 전체데이터 ≈ 55h/epoch) run 중단 대비. `train_autovla_lora.py`에 체크포인트/resume 추가.
- 2단계 저장: `--save-every`(latest, 덮어쓰기) + `--keep-every`(milestone `step_NNNNNN`, `--keep-last`로 회전). 둘 다 adapter+processor+codebook+`training_state.json`+`optimizer.pt` 저장(완전 resume용). 런처 기본 `SAVE_EVERY=10`, `KEEP_EVERY=500`, `KEEP_LAST=3`.
- `_save_checkpoint(optimizer=)`로 optimizer 상태 저장, `_rotate_milestones`로 오래된 milestone 삭제.
- 완전 resume `--resume-from <dir>`: base+resize 후 `PeftModel.from_pretrained(is_trainable=True)`로 adapter 로드 + `optimizer.pt` 로드 + `training_state`의 epoch/step/step_in_epoch 복원. epoch별 loader를 `seed+epoch`로 seeded shuffle해 순서 재현 → 재개 epoch에서 done batch를 skip(중간 epoch resume). 로그는 append.
- 검증(M4): run1(3 step, save_every1/keep_every3) → latest+milestone(step_000003)에 optimizer.pt/training_state(step_in_epoch=3) 생성 확인. run2(`--resume-from step_000003`, epochs2) → `RESUME_ADAPTER`/`RESUME_STATE(start_epoch=2-1, skip=3)`로 epoch1 skip, epoch2 step4·5·6 실행, global_step 3→6 연속, loss 4.6→2.7로 끊김 없이 이어짐(optimizer 복원 확인).
- 주의: 저장 1회가 adapter(~2.4GB)+optimizer(~5GB)≈7.5GB라 save_every가 너무 잦으면 I/O가 throughput을 갉아먹는다. latest는 덮어쓰기라 디스크 안 늘고, milestone은 keep_last로 제한.

2026-06-05 AutoVLA 전체데이터+가중 학습 100-step 체크포인트 분석:

- 재시작 run(전체데이터, weighted loss, save_every=10)이 step 100(epoch 1/2, =epoch의 1%)까지 진행. weighted loss 4.11→0.20(step 79에서 1.65 스파이크).
- step 100 체크포인트로 generate 분석(직진 0/200, 우회전 83/82/84, 좌회전 27): 추론 문장은 정확(속도·명령 반영, "turning right/left at the intersection")하나 **action 토큰을 0개 생성**("Trajectory:" 직후 즉시 EOS).
- 해석: 100/10000 = 1%로 **심한 학습 부족**. 결정론적 추론 텍스트+마커+EOS는 빨리 학습됐지만, 이미지 조건부 action 토큰열은 아직 안 나옴(회피). 무가중=act_4/act_1 붕괴, 가중=즉시 EOS — 둘 다 데이터/스텝 부족의 다른 양상. 가중+EOS(weight 1.0) 동학이 초반 action 학습을 늦출 가능성도 관찰 대상.
- 결론: 100스텝으론 판정 불가. 의미있는 판정엔 수천 스텝~1에폭 필요 → M4 ~55h/epoch라 GPU 본학습 필수. M4에선 step~1000 체크포인트에서 action 토큰 출현 여부 재확인 정도가 한계.
- 운영 이슈: 분석마다 `/Volumes/DATASET`가 반복 언마운트되어 generate가 자주 막힘(슬립/연결 점검 필요). 학습/추론 충돌 방지로 체크포인트 스냅샷(optimizer 제외) 후 분석하는 절차 사용.

2026-06-06 AutoVLA collapse 탈출(step 800) + 학습 robustness:

- step 진행에 따른 생성 변화(전체데이터, weighted, fp32, 224, 3카메라): step 100=action 0개(즉시 EOS) → step 310=전부 act_1(정지) → **step 800=붕괴 탈출**.
- step 800 생성 분석(직진 0/200, 우회전 83/82/84, 좌회전 27): 명령별로 **서로 다른 토큰 시퀀스** 생성.
  - 직진: `act_4`(고속전진) 위주 → 예측 final (24.0, 0.0), sample0 ADE **0.18m**, sample200 ADE 2.55.
  - 우회전: `act_94/86/38/176/...` → final (10.9, **+4.55**)로 우향(+y) 맞으나 GT +20 대비 **undershoot**(ADE~8).
  - 좌회전: 또 다른 패턴(`act_205/17/...`). 즉 collapse 아님.
  - 한계: turn_right 83/82/84가 동일 출력 → 아직 명령+속도 위주, 장면별 image 조건화 약함. 급회전 토큰이 코드북에서 희소(<0.1%)해 약한 회전 토큰을 써 undershoot.
- 결론: weighted loss + 충분한 step(800=epoch의 8%)이 붕괴를 깸. 방향 검증됨(직진 정확, 회전 방향 정확·크기 약함). 회전 강화는 더 학습 + codebook/데이터 회전 보강 필요. 본격은 GPU.
- 학습 robustness: step 809에서 `/Volumes/DATASET` 언마운트로 이미지 1장 못 읽어 전체 크래시. `AutoVLASFTCollator._load_images`에 재시도(3회×2s) + 실패 샘플 drop, 배치 전부 실패 시 `None` 반환→트레이너가 step skip. 짧은 마운트 블립에 학습이 죽지 않게 함(완전 언마운트 지속 시엔 skip만 누적되므로 마운트 안정화가 근본). step 800 체크포인트 보존됨 → auto-resume 가능.

2026-06-06 07 launcher 자동 resume(실수 방지):

- 증상: 학습 재개하려 07을 그냥 실행했는데 resume가 안 되고 step1부터 새로 시작(train_log가 잘림). 원인: launcher `RESUME_FROM` 기본값이 빈 값이라 fresh start. 단 fresh run이 save_every(10) 전 step4에서 멈춰 가중치는 안 덮였고 step-100 체크포인트는 보존됨(로그만 손실).
- 수정: `07_AutoVLA학습.command`에 자동 resume 추가 — `RESUME_FROM`이 비어 있어도 `OUTPUT_DIR/training_state.json`이 있으면 자동으로 그 dir에서 이어서 학습(adapter+optimizer+step 복원). 처음부터 다시 하려면 `FRESH=1`. 실행 로그에 `RESUME_FROM` 상태 표시. 이로써 07을 무심코 다시 돌려 진행분을 덮어쓰는 사고를 방지.
- 운영: 실학습/생성은 M4에 3B 모델을 동시 2개 못 올림(메모리 폭증) → 분석할 땐 학습을 멈추고(Ctrl-C) 단독으로 generate 후 `./07`로 auto-resume하는 절차 사용. 학습 도중 분석은 비권장.

2026-06-04~06 CARLA learned closed-loop eval 개선(이번 세션, 위 AutoVLA와 함께 커밋):

- 전진 불가 원인 분석: learned 정책이 정지 상태(speed≈0)에서 미래 변위≈0 waypoint를 내고, waypoint→control 어댑터가 throttle 0을 주어 출발 못 하는 speed-shortcut 데드락 확인(DummyDrivingBackbone이 ego_speed를 직접 입력으로 쓰고, 데이터의 32%가 정지 프레임). eval 우회책으로 warm-up 강제 throttle(목표속도 도달 OR 시간 충족 시 해제) 사용.
- 글로벌 start→goal 라우팅: `--spawn-goal-index`로 CARLA `GlobalRoutePlanner` 사용. CrossOver Python37엔 numpy/networkx가 없어 import 실패 → 순수 Python Dijkstra(`_plan_route_waypoints`, `waypoint.next`+lane change, heapq/stdlib만) 폴백 추가. route_command는 RoadOption→command 매핑(`route_command_from_road_option`) 또는 yaw-delta. 도착 감지/route_completion 추가.
- train/eval 정합: 학습 route_waypoints는 `waypoint.next(2m)` 등간격인데 eval 글로벌 플랜은 불규칙(2~4m)이라 회전을 일찍 꺾어 가로등 충돌 → eval route waypoint를 누적거리 기준 **고정 2m 등간격 재샘플**(`upcoming_waypoints_ego`)로 맞춤. route_command lookahead도 학습 수집값(30m)에 맞춤.
- HUD 영상: warm-up 구간도 프레임 기록(`phase=WARM-UP`)해서 영상에 포함. HUD 영상용 **3인칭 체이스 카메라**(`_spawn_chase_camera`, 뒤7m·위3.5m·-15°) 추가 — 모델 입력은 전방 카메라 유지, 영상만 체이스. render에 phase/policy_type/action_tokens 표시.
- 안정화: 이미 같은 맵이면 `load_world` 재로드(타임아웃·크래시 원인) 생략하고 현재 world 재사용(REUSING_WORLD). `05_평가.command`가 policy server 기동 전 포트(8765) 점유 프로세스·잔존 eval 클라이언트를 정리하고, 기동을 `POLICY_SERVER_READY`+PID 생존으로 확인(Address already in use/유령 프로세스로 인한 fatal 방지). synchronous mode/fixed delta 옵션 추가.
- AutoVLA eval 통합(구현, closed-loop 실검증 미완): `POLICY_TYPE=autovla`면 serve/eval/05가 회귀 어댑터 대신 generate 모델(`autovla_generate`)로 평가하도록 배선. 05 기본 checkpoint를 `checkpoints/m10d_autovla_lora`로. 실제 CARLA closed-loop 검증은 후속.

2026-06-06 AutoVLA step-800 평가 launcher 사전 검증:

- `05_평가.command` 기본 평가 대상을 `checkpoints/m10d_autovla_lora`의 AutoVLA LoRA로 전환하고, base model/codebook/adapter 필수 파일 검사와 policy server 최대 300초 기동 대기를 추가했다. 현재 root `training_state.json`은 step 800(epoch 1/2, step_in_epoch 800)이다.
- Mac policy server에서 실제 step-800 adapter+base model을 MPS로 로드한 뒤 합성 3카메라 요청을 전송했다. 약 1분 46초 후 서버 ready, 단일 생성 약 8.55초, reasoning 문장 + action token 10개 + waypoint 10개 + control 응답까지 정상 확인했다.
- closed-loop 모델 입력을 학습과 같은 front/front-left/front-right 카메라 extrinsic과 gamma 2.2로 맞췄다. AutoVLA에는 글로벌 route waypoint 자체를 입력하지 않고, 글로벌 경로에서 계산한 high-level command만 입력한다. route waypoint는 HUD/분석에 사용한다.
- 생성 지연 중 CARLA world가 비동기로 진행되는 평가 오류를 막기 위해 learned closed-loop 기본값을 synchronous mode, fixed delta 0.2초(5 FPS)로 변경했다. HUD/report에 생성 reasoning, action token, predicted waypoint, route waypoint, control을 기록한다.
- 사전 검증: launcher/shell 구문 검사, local Python 및 CrossOver Python 3.7 compile, `git diff --check`, HUD MP4 writer 실제 생성, AutoVLA/route/control 관련 unit test 16개 통과. CARLA port 2000은 현재 닫혀 있지만 05가 `01_카를라실행.command`를 자동 실행하도록 준비되어 있다. 실제 Town01 closed-loop 주행은 사용자 실행 후 결과 확인이 필요하다.
- HUD reasoning 가독성: 기존 한 줄 46자 절단을 제거하고 reasoning을 별도 최대 5줄로 줄바꿈해 약 225자까지 표시한다. 늘어난 텍스트 영역과 겹치지 않도록 steer/throttle/brake bar를 아래로 이동했다.

2026-06-07 launcher 중심 프로젝트 정리:

- 사용 승인 후 launcher에서 직접·간접 호출되지 않는 script 9개를 삭제했다: offline asset/paper download, offline budget, CARLA camera diagnostic, nuScenes prepare/open-loop, 5090 handoff, Mac scale sweep 경로.
- `launchers/*.command`에서 shell 호출과 Python import를 재귀 추적한 결과, 남은 launcher 연결 script 17개와 `src/vla_drive` Python 모듈 전체가 현재 실행 경로에서 도달 가능함을 확인했다.
- 수동 보존 script는 `check_mac_readiness.py`(AGENTS 필수 검증)와 `autovla_generate_smoke.py`(AutoVLA 단독 생성 검사)다.
- 추가 미연결 후보는 삭제하지 않고 보고 대상으로 남겼다: `src/vla_drive/configs/base.yaml`, `src/vla_drive/configs/nuscenes_open_loop.yaml`, `outputs/handoff/5090_manifest.json`, 삭제된 script를 가리키는 문서 참조.
- 사용자 승인 후 고립된 `src/vla_drive/configs/nuscenes_open_loop.yaml`과 `outputs/handoff/5090_manifest.json`을 삭제했다. 현재 안내 문서에서 삭제된 script 실행 지시를 제거했으며, 과거 실험 기록의 명령은 역사 보존을 위해 유지했다. `base.yaml`은 실행에 연결되지 않은 초기 공통 설정 템플릿이지만 사용자 요청으로 보존한다.
- 검증 과정에서 생성된 `__pycache__`, `.pytest_cache`, `.matplotlib_cache`를 삭제했다. 전체 unit test 33개와 launcher/shell 구문 검사는 삭제 전후 정상 통과했다.
- 사용자 승인 후 현재 launcher가 읽지 않는 초기 공통 설정 템플릿 `src/vla_drive/configs/base.yaml`도 삭제했다.
- 커밋 전 전체 diff 재감사에서 `check_mac_readiness.py`와 setup/data/TASKS 문서가 삭제된 offline 자산을 여전히 필수 또는 준비 완료로 취급하는 누락을 발견했다. readiness 필수 asset을 현재 launcher가 사용하는 Qwen2.5-VL-3B와 CARLA 경로로 맞추고, 현재 유지 자산/용량/외부 dataset 제거 상태를 문서에 반영했다.

2026-06-09 AutoVLA checkpoint 로컬 보관 상태:

- `checkpoints/m10d_autovla_lora/`는 약 12GB이며 `.gitignore`의 `checkpoints/`, `*.pt`, `*.safetensors` 규칙과 offline 정책에 따라 Git에 커밋하지 않고 로컬 artifact로 보관한다.
- 최신 resume 기준은 `training_state.json`: epoch 1/2, global step 1200, step_in_epoch 1205, loss 0.0002822203. `train_summary.json`의 300-step/final loss 0.03035 값은 초기 PoC 완료 시점 기록이므로 최신 resume 상태로 해석하지 않는다.
- 재현/무결성 확인용 SHA-256: `adapter_model.safetensors`=`36b78849a0d31109c70ceca6e4bc5f250db51cf60c7dd8771aa276fea59bcead`, `optimizer.pt`=`4182fbf2b2cfcd576013a154836740d9ba98e3dfa925cefd66c626bf1dd9aeea`, `training_state.json`=`09189024bc50e6ff62059e140b541012ea23fbf090bcff0390364045b3849675`, `trajectory_codebook.json`=`ee637b10e0def08e2e8366e9c7f5ca0e1105b7fe921dbd7251fcb3323487a1dd`.
