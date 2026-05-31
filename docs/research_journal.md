# 연구일지

이 문서는 프로젝트 생성 시점부터 milestone 진행 상황을 시간순으로 기록한다. 세부 실행 지침은 `TASKS.md`, 환경 재현은 `docs/setup.md`, CARLA Mac 설치는 `docs/carla_mac_setup.md`, 데이터 스키마는 `docs/data.md`를 기준 문서로 둔다.

## 2026-05-29: 프로젝트 초기 구성

목표를 CARLA closed-loop에서 동작하는 VLA 기반 자율주행 agent 구현으로 정했다. 처음부터 대형 VLA를 full fine-tuning하지 않고, MacBook tiny smoke run에서 시작해 RTX 5090 medium run, AIP/H100 large run으로 확장하는 ladder를 채택했다.

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
- AIP/H100은 MacBook/RTX 5090에서 pipeline이 검증된 뒤에만 사용한다.

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

다음 작업:

1. Phase C: M7 Action Tokenizer 구현 (K-disk clustering, K=256 시작, cross-entropy loss)
2. MacBook에서는 tiny route와 CPU/MPS-safe mode만 유지한다.
3. RTX 5090 확장 전까지 같은 code path에서 반복 검증한다.
