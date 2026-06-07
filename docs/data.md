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

- MacBook: low traffic, low image resolution의 tiny smoke route에서 시작하고, 가능한 범위까지 route 수, weather variant, image resolution, collection 시간을 키운다.
- RTX 5090: MacBook에서 수집/평가 리소스 한계가 기록된 뒤 더 많은 route, weather variant, traffic density, 긴 collection job으로 확장한다.
- AIP/H100: schema와 evaluation이 MacBook/RTX 5090에서 안정되고, RTX 5090 리소스 한계가 기록된 뒤에만 사용한다.

작업:

- clear weather에서 10개 short route를 수집한다.
- rain/fog/night variant에서 10개 route를 수집한다.
- RGB, ego state, route command, expert waypoints/control을 기록한다.
- train/val/test split은 frame 단위가 아니라 route 단위로 나눈다.

## 외부 dataset

nuScenes/NAVSIM/Bench2Drive 변환 경로와 offline asset은 현재 launcher 중심 pipeline에서 제거했다.
현재 수집, 학습, 평가는 CARLA metadata를 기준으로 한다. 외부 dataset을 다시 도입할 때는 launcher 진입점과
필요 용량을 먼저 정의한 뒤 별도 milestone로 추가한다.

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

현재 JSONL record는 `DrivingSample`에 직접 대응한다.

```json
{
  "observation": {
    "sample_id": "carla_000000",
    "timestamp": 0.0,
    "camera_front": "/private/tmp/vla_drive_carla/m1_smoke/images/frame_00000.png",
    "route_command": "lane_follow",
    "ego_speed_mps": 4.35
  },
  "target": {
    "future_waypoints_ego": [[1.0, 0.0], [2.0, 0.0]],
    "steer": 0.0,
    "throttle": 0.2,
    "brake": 0.0
  }
}
```

Path rule:

- absolute image path는 그대로 사용한다.
- relative image path는 `metadata.jsonl`이 있는 directory 기준으로 resolve한다.
- CrossOver/Wine에서 수집할 때 `Z:\...` image path는 POSIX `/...` path로 기록한다.

Batch rule:

- `driving_collate_fn`은 `images: float32[B, 3, H, W]`, `future_waypoints_ego: float32[B, T, 2]`, `controls: float32[B, 3]`를 만든다.
- prompt는 route command와 ego speed를 포함한 짧은 driving instruction으로 만든다.

## Split Rule

frame 단위 random split은 거의 같은 observation을 train/test에 동시에 넣을 수 있다. split은 route 또는 scene 단위로 나눈다.
