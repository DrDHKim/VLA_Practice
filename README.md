# VLA Autonomous Driving Starter Kit

이 저장소는 Vision-Language-Action(VLA)을 이용한 자율주행 연구/구현을 시작하기 위한 사전 작업 공간이다. 목표는 인터넷이 느리거나 없는 환경에서도 Qwen3 Coder 30B급 저성능 AI가 문서와 파일 스텁을 따라 끝까지 구현을 이어갈 수 있게 만드는 것이다.

## 목표

- CARLA 폐쇄 루프에서 동작하는 VLA 기반 자율주행 에이전트 구현
- nuScenes, NAVSIM, Bench2Drive/CARLA를 단계적으로 사용
- 오픈 모델을 우선 활용하고, MacBook에서 작은 end-to-end 시범 루프를 먼저 만든 뒤 RTX 5090 32GB에서 중간 규모로 확장
- 회사 AIP/H100 2장은 최후의 확장 선택지로만 사용한다. 코드 반출이 불가능하므로, AIP로 들어가는 순간 이후 개발/실험은 회사 환경에 고정된다는 제약이 있다.

## 현재 권장 전략

1. **1차 구현 기준 모델: OpenDriveVLA 계열**
   - 자율주행 VLA에 직접 맞춰져 있고, nuScenes 기반 open-loop planning 및 QA 태스크를 목표로 한다.
   - Qwen/LLaVA/UniAD 계열 의존성이 있어 구현 참고가 쉽다.
   - 단, 공개 코드/체크포인트 상태는 계속 확인해야 한다.

2. **2차 비교 기준 모델: AutoVLA**
   - trajectory tokenization, fast/slow reasoning, GRPO 기반 reinforcement fine-tuning 아이디어가 좋다.
   - nuPlan, nuScenes, Waymo, CARLA까지 언급되어 최종 로드맵과 잘 맞는다.

3. **대형 기준선: NVIDIA Alpamayo**
   - 10B급 open reasoning VLA이며 자율주행 장기 방향을 보기 좋다.
   - MacBook에서는 tiny smoke run, RTX 5090 32GB에서는 inference/LoRA/오프로딩 검증 중심으로 보고, 더 큰 학습은 AIP/H100 진입 조건을 만족한 뒤 판단한다.

4. **당장 구현 가능한 최소 시스템**
   - CARLA RGB 카메라 + ego state + route command 입력
   - Qwen2.5-VL 또는 LLaVA 계열 backbone
   - action head는 waypoint regression으로 시작
   - 추론은 `throttle`, `steer`, `brake` 직접 출력보다 future waypoints 출력 후 PID/MPC controller로 변환

## 하드웨어별 역할

| 환경 | 역할 | 하지 말 것 |
| --- | --- | --- |
| MacBook | 전체 파이프라인의 소규모 시범: CARLA 데이터 수집, tiny/small 학습, open/closed-loop 평가, 문서화/코딩 | 장시간/대량 학습, 대규모 route sweep |
| 집 데스크탑 RTX 5090 32GB | 같은 파이프라인의 중간 규모 실행: CARLA 수집량 확대, LoRA/QLoRA, 평가 반복 | 10B 이상 full fine-tuning |
| 회사 AIP/H100 x2 | Mac/5090에서 검증된 파이프라인의 대규모 확장, 장시간 ablation, 대형 모델 실험 | 초기 탐색. 코드 반출 제약 때문에 너무 일찍 들어가지 말 것 |

## 폴더 구조

```text
.
├── README.md
├── project_plan.md
├── TASKS.md
├── pyproject.toml
├── wiki/                         # 최상위 탐색 문서
│   ├── Home.md
│   ├── Handbook.md
│   └── Glossary.md
├── docs/
│   ├── setup.md                 # 환경, 하드웨어, 오프라인 다운로드
│   ├── research.md              # 모델 선정, 논문 index
│   ├── data.md                  # 데이터 우선순위와 스키마
│   ├── experiments.md           # 실험 매트릭스
│   └── research/
│       ├── papers/              # PDF 저장 위치
│       └── notes/               # 논문별 요약 노트
├── src/vla_drive/
│   ├── configs/
│   │   ├── base.yaml
│   │   ├── carla_rgb_waypoint.yaml
│   │   └── nuscenes_open_loop.yaml
│   ├── data/
│   │   ├── datasets.py
│   │   ├── transforms.py
│   │   ├── collate.py
│   │   └── schemas.py
│   ├── models/
│   │   ├── backbone_vlm.py
│   │   ├── action_tokenizer.py
│   │   ├── waypoint_head.py
│   │   └── vla_policy.py
│   ├── training/
│   │   ├── train.py
│   │   ├── losses.py
│   │   └── lora.py
│   ├── evaluation/
│   │   ├── open_loop_metrics.py
│   │   ├── closed_loop_metrics.py
│   │   └── evaluator.py
│   ├── simulation/
│   │   ├── carla_client.py
│   │   ├── carla_agent.py
│   │   ├── route_planner.py
│   │   └── pid_controller.py
│   └── utils/
│       ├── logging.py
│       ├── seed.py
│       └── io.py
├── scripts/
│   ├── download_papers.sh
│   ├── prepare_nuscenes.py
│   ├── collect_carla_data.py
│   ├── train_lora.sh
│   ├── eval_open_loop.sh
│   └── eval_carla.sh
├── data/                         # 실제 데이터는 git에 넣지 않음
├── checkpoints/                  # 모델 weight 저장 위치
├── outputs/                      # 실험 결과
└── tests/
```

상위 폴더는 의도적으로 `wiki`, `docs`, `src`, `scripts`, `tests`, `data`, `checkpoints`, `outputs`만 유지한다. 문서는 주제별 단일 파일을 우선하고, 논문 PDF/노트처럼 파일 수가 자연스럽게 늘어나는 경우만 하위 폴더를 둔다.

## 단계별 실행

### Phase 0: 오프라인 준비

- `docs/research.md`를 읽고 주요 논문 PDF를 `docs/research/papers/`에 저장한다.
- `docs/setup.md`를 기준으로 MacBook 소규모 시범 환경을 먼저 만든다.
- Qwen3 Coder는 새 파일을 만들기 전에 반드시 이 README와 `project_plan.md`를 먼저 읽는다.

### Phase 1: 최소 CARLA 주행 파이프라인

- 목표: 학습 없이도 CARLA에서 센서 수집, route command, PID 제어가 동작하게 만들기
- 구현 파일:
  - `src/vla_drive/simulation/carla_client.py`
  - `src/vla_drive/simulation/carla_agent.py`
  - `src/vla_drive/simulation/pid_controller.py`
  - `scripts/collect_carla_data.py`

### Phase 2: 작은 VLA policy 구현

- 목표: RGB 이미지, ego state, route command를 받아 future waypoints를 예측
- 우선 LoRA/QLoRA로 시작하고 full fine-tuning은 금지
- 구현 파일:
  - `src/vla_drive/models/backbone_vlm.py`
  - `src/vla_drive/models/waypoint_head.py`
  - `src/vla_drive/models/vla_policy.py`
  - `src/vla_drive/training/train.py`

### Phase 3: nuScenes/NAVSIM open-loop 평가

- 목표: closed-loop 이전에 trajectory L2, collision proxy, route adherence 등을 확인
- 구현 파일:
  - `scripts/prepare_nuscenes.py`
  - `src/vla_drive/evaluation/open_loop_metrics.py`
  - `src/vla_drive/evaluation/evaluator.py`

### Phase 4: CARLA closed-loop 평가

- 목표: Bench2Drive 또는 CARLA route benchmark에서 driving score 측정
- 구현 파일:
  - `scripts/eval_carla.sh`
  - `src/vla_drive/evaluation/closed_loop_metrics.py`

### Phase 5: 모델 확장

- OpenDriveVLA/AutoVLA 구조를 참고해 action tokenization, reasoning supervision, RL fine-tuning을 추가한다.
- MacBook에서 먼저 데이터 수집-학습-평가의 최소 루프를 확인한다.
- RTX 5090에서 같은 루프를 중간 규모로 확장하고, OOM이면 gradient checkpointing, 4-bit quantization, CPU offload를 먼저 시도한다.
- AIP/H100은 최종 대규모 학습/ablation이 명확해진 뒤에만 사용한다.

## 중요 원칙

- 실제 차량 제어 목적이 아니라 연구/시뮬레이션 목적이다.
- 자연어 reasoning은 디버깅과 long-tail 판단에는 유용하지만, 최종 제어는 항상 물리적으로 검증 가능한 waypoint/controller 경로를 거친다.
- 처음부터 10B 모델을 학습하지 않는다. 작은 재현 가능한 baseline을 먼저 만든다.
- 데이터, 체크포인트, 대용량 로그는 저장소에 커밋하지 않는다.

## 바로 다음 작업

1. `scripts/download_papers.sh`를 실행해 주요 논문 PDF를 저장한다.
2. `docs/setup.md`를 보고 오프라인 작업용 모델/데이터/패키지를 미리 받는다.
3. `docs/setup.md`에 맞춰 MacBook에서는 MPS/CPU smoke run, 5090에서는 CUDA 중간 규모 run, AIP/H100에서는 최종 확장 run을 구분한다.
4. `src/vla_drive/simulation/`부터 구현해 CARLA 데이터 수집 루프를 MacBook에서 먼저 완성한다.
5. `src/vla_drive/models/`의 TODO를 채워 waypoint prediction baseline을 만든다.

## 문서 사용법

- `README.md`: 전체 프로젝트 개요
- `project_plan.md`: 모델, 데이터, 하드웨어 전략
- `TASKS.md`: 로컬 LLM이 따라야 할 실제 구현 todo
- `wiki/Home.md`: 위키 시작점
- `wiki/Handbook.md`: 로컬 LLM용 압축 구현 가이드
- `docs/setup.md`: Anaconda, 하드웨어, 오프라인 다운로드, 120GB 예산
- `docs/research.md`: 모델 선정, 논문 목록과 읽는 순서
- `docs/data.md`: 데이터 우선순위와 스키마
- `docs/experiments.md`: 실험 매트릭스
