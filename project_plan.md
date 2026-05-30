# VLA Autonomous Driving Project Plan

## 0. 핵심 판단

이 프로젝트는 처음부터 거대 VLA를 full training하는 방식으로 시작하면 실패 확률이 높다. 현재 환경에서는 다음 순서가 가장 현실적이다.

1. MacBook에서 CARLA 데이터 수집-학습-평가의 아주 작은 end-to-end 루프를 먼저 만든다.
2. 같은 루프를 RTX 5090에서 중간 규모 데이터/학습/평가로 확장한다.
3. 작은 VLM backbone + waypoint head로 baseline을 만든다.
4. nuScenes/NAVSIM에서 open-loop 평가를 붙인다.
5. OpenDriveVLA/AutoVLA 논문 구조를 따라 action tokenization과 reasoning supervision을 확장한다.
6. Alpamayo 같은 10B급 모델은 inference/reference/teacher 용도로 먼저 쓴다.

## 1. 모델 후보

| 후보 | 용도 | 장점 | 리스크 |
| --- | --- | --- | --- |
| OpenDriveVLA | 1차 구조 참고 | 자율주행 VLA 직접 대상, nuScenes planning/QA 지향 | 공개 코드와 체크포인트 상태 확인 필요 |
| AutoVLA | 2차 구조 참고 | fast/slow reasoning, trajectory tokenization, GRPO | 구현 복잡도 높음 |
| Alpamayo-R1/1.5 | teacher/대형 기준선 | open reasoning VLA, AV long-tail 목적 | 10B급, 메모리 부담 큼 |
| DriveVLM/DriveGPT4 | 배경/해석 가능성 | VLM 기반 reasoning/설명/계층 planning | 순수 VLA action 학습과 거리가 있음 |
| Qwen2.5-VL/LLaVA 계열 + custom head | 최소 구현 | RTX 5090에서 LoRA 가능, 구현 통제 가능 | 논문 SOTA와는 차이 |

권장 시작점은 **custom small VLA baseline**이다. OpenDriveVLA를 그대로 복제하려고 하기보다 파일 구조와 데이터 표현을 맞춰 두고, 공개 구현이 안정화되면 어댑터를 붙인다.

## 2. 데이터 계획

### 2.1 CARLA

- 목적: closed-loop 평가와 자체 imitation 데이터 생성
- 실행 규모:
  - MacBook: tiny smoke routes, low resolution, low traffic, 짧은 학습/평가
  - RTX 5090: 중간 규모 route/weather/traffic 확장, LoRA/QLoRA 반복
  - AIP/H100: 검증된 실험의 대규모 ablation/장시간 학습
- 입력:
  - front RGB
  - optional multi-view RGB
  - ego speed, acceleration, yaw rate
  - high-level command: follow lane, left, right, straight, lane change
- 출력:
  - future waypoints in ego frame: shape `[T, 2]`
  - optional low-level control: steer, throttle, brake
  - optional reasoning text

### 2.2 nuScenes

- 목적: open-loop trajectory prediction 및 multi-view perception 기반 사전학습
- 시작은 mini split로 한다.
- full dataset은 MacBook smoke run 이후 RTX 5090 또는 외부 저장소에서 처리한다.

### 2.3 NAVSIM / Bench2Drive

- 목적: 최신 E2E driving 평가 방식과 맞추기
- 우선 문서와 설치 난이도를 확인한 뒤, CARLA 기본 루프가 완성된 다음 붙인다.

## 3. 구현 마일스톤

### M0: 저장소 사전 정리

- README, 논문 index, setup 문서, 코드 스텁 생성
- 논문 PDF 저장
- 완료 기준: 인터넷 없이도 다음 구현자가 무엇을 해야 하는지 알 수 있음

### M1: CARLA 연결

- `carla_client.py`: 서버 연결, world/weather/spawn 설정
- `carla_agent.py`: sensor callback, observation 생성, action 적용
- `pid_controller.py`: waypoints를 control로 변환
- 완료 기준: rule-based waypoint로 1개 route 완주

### M2: 데이터셋 포맷

- `schemas.py`: Observation/Action/Trajectory dataclass 정의
- `datasets.py`: CARLA episode와 nuScenes sample loader
- `collate.py`: variable length/text/image batch 처리
- 완료 기준: 10개 샘플 batch가 학습 코드로 들어감

### M3: VLA baseline

- `backbone_vlm.py`: Qwen2.5-VL 또는 LLaVA wrapper
- `waypoint_head.py`: hidden state to future waypoints
- `vla_policy.py`: observation -> prompt -> model -> trajectory
- 완료 기준: overfit small batch 성공

### M4: open-loop 학습/평가

- `train.py`: LoRA/QLoRA 학습 루프
- `open_loop_metrics.py`: L2, final displacement error, route deviation
- 완료 기준: held-out CARLA/nuScenes split에서 metric 출력

### M5: closed-loop 평가

- `evaluator.py`: route별 rollout 관리
- `closed_loop_metrics.py`: collision, red light, off-road, progress
- 완료 기준: CARLA route 5개 자동 평가 리포트 생성

### M6: reasoning/action 확장

- AutoVLA 방식의 fast/slow mode 추가
- reasoning annotation은 처음엔 template/teacher model로 생성
- action tokenization은 waypoint regression baseline이 안정된 뒤 추가

## 4. Qwen3 Coder 작업 지침

- 새 기능을 만들기 전에 관련 문서와 TODO가 있는 스텁 파일을 먼저 읽는다.
- 대형 의존성을 추가하기 전에 `docs/setup.md`에 설치 이유를 기록한다.
- 하나의 PR/작업 단위는 한 단계만 완료한다.
- 인터넷이 없으면 `docs/research/papers/`와 `docs/research/notes/`만 보고 구현한다.
- CUDA OOM이 나면 모델을 키우지 말고 batch size, image size, sequence length, LoRA rank, quantization을 먼저 줄인다.

## 5. AIP/H100 사용 판단 기준

AIP/H100으로 넘어가는 조건:

- MacBook에서 CARLA loop, dataset, baseline 학습, open/closed-loop metric의 smoke run이 모두 동작한다.
- RTX 5090에서 같은 파이프라인의 중간 규모 LoRA/QLoRA 실험 결과가 있고, 대형 학습이 필요한 이유가 문서화되어 있다.
- 회사 환경으로 코드가 들어간 뒤 되돌릴 수 없다는 운영 리스크를 감수할 만큼 실험 설계가 고정되어 있다.

넘어가지 말아야 하는 조건:

- 아직 CARLA 평가가 불안정하다.
- 데이터 포맷이 바뀌고 있다.
- 단순 OOM 회피가 목적이다.
- 논문 재현 범위가 명확하지 않다.
