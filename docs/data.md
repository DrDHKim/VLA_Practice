# 데이터 (Data)

## Dataset 우선순위

1. CARLA short routes
2. CARLA weather variants
3. nuScenes mini
4. nuScenes full
5. NAVSIM 또는 Bench2Drive

## CARLA 우선

CARLA는 closed-loop feedback을 가장 빨리 얻을 수 있는 경로다.

Scale 정책:

- MacBook: 먼저 low traffic, low image resolution으로 1-3개의 tiny smoke route를 수집한다.
- RTX 5090: 더 많은 route, weather variant, traffic density, 긴 collection job으로 확장한다.
- AIP/H100: schema와 evaluation이 MacBook/RTX 5090에서 안정된 뒤에만 사용한다.

작업:

- clear weather에서 10개 short route를 수집한다.
- rain/fog/night variant에서 10개 route를 수집한다.
- RGB, ego state, route command, expert waypoints/control을 기록한다.
- train/val/test split은 frame 단위가 아니라 route 단위로 나눈다.

## nuScenes 다음

full nuScenes보다 nuScenes mini를 먼저 사용한다.

mini split은 MacBook schema/debug 작업에 적합하다. full nuScenes는 RTX 5090 또는 external storage path가 준비된 뒤 처리한다.

작업:

- sample을 common schema로 변환한다.
- ego-frame future trajectory를 추출한다.
- scene description 또는 route command를 text prompt로 매핑한다.
- 처음에는 open-loop metric만 실행한다.

## NAVSIM / Bench2Drive 이후

baseline training이 동작한 뒤 추가한다.

작업:

- install을 검증한다.
- metric을 `closed_loop_metrics.py`에 매핑한다.
- 가능한 경우 literature metric과 비교한다.

## Observation Schema

```text
sample_id: str
timestamp: float
camera_front: image path or tensor
camera_left/right/rear: optional image path or tensor
ego_speed_mps: float
ego_accel_mps2: optional float
ego_yaw_rate: optional float
route_command: str
nav_goal: optional structured target
```

## Action Target Schema

```text
future_waypoints_ego: float[T, 2]
low_level_control:
  steer: float
  throttle: float
  brake: float
reasoning: optional str
```

## 초기 파일 형식

JSONL metadata와 image file 조합으로 시작한다.

```text
data/processed/carla/
├── episodes/
│   └── episode_000001/
│       ├── metadata.jsonl
│       └── images/
└── splits/
    ├── train.txt
    ├── val.txt
    └── test.txt
```

schema가 안정되기 전에는 복잡한 binary format을 설계하지 않는다.

## Split Rule

frame 단위 random split은 거의 같은 observation을 train/test에 동시에 넣을 수 있다. split은 route 또는 scene 단위로 나눈다.
