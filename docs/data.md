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

## nuScenes 다음

full nuScenes보다 nuScenes mini를 먼저 사용한다.

mini split은 MacBook schema/debug 작업에 적합하다. full nuScenes는 먼저 MacBook에서 가능한 변환/샘플링/metric path를 검증하고, 용량/시간 한계가 확인되면 RTX 5090 또는 external storage path에서 처리한다.

작업:

- sample을 common schema로 변환한다.
- ego-frame future trajectory를 추출한다.
- scene description 또는 route command를 text prompt로 매핑한다.
- 처음에는 open-loop metric만 실행한다.

현재 MacBook smoke 변환:

```bash
.conda/bin/python scripts/prepare_nuscenes.py \
  --input-tar data/offline/datasets/nuscenes/v1.0-mini.tgz \
  --output-root /private/tmp/vla_drive_nuscenes_mini \
  --max-samples 40 \
  --future-steps 8 \
  --sample-stride 2
```

출력:

```text
/private/tmp/vla_drive_nuscenes_mini/
├── metadata.jsonl
├── conversion_summary.json
└── images/
```

Mapping:

- `camera_front`: nuScenes key-frame `CAM_FRONT` 이미지를 subset output으로 추출한다.
- `future_waypoints_ego`: 현재 ego pose 기준 future sample 8개의 ego-frame `(x, y)` displacement다.
- `ego_speed_mps`: 현재 pose와 다음 pose의 timestamp/translation 차이로 계산한다.
- `route_command`: 마지막 future waypoint의 lateral offset이 `> 1.5m`면 `turn_left`, `< -1.5m`면 `turn_right`, 그 외 `lane_follow`.
- `reasoning`: route command를 `keep_lane`, `turn_left`, `turn_right`로 매핑하고, 속도 `< 0.5m/s`면 `slow_or_stop`.

평가 smoke:

```bash
.conda/bin/python -m vla_drive.evaluation.evaluator \
  --checkpoint-path checkpoints/m4_dummy/latest.pt \
  --metadata-path /private/tmp/vla_drive_nuscenes_mini/metadata.jsonl \
  --report-path outputs/reports/m9_nuscenes_carla_checkpoint_open_loop.json \
  --max-samples 40 --batch-size 4 --image-size 64 --device cpu
```

full 변환은 아직 하지 않는다. mini tar에서 JSON table을 읽고 선택 이미지만 추출하는 40-sample 변환은 MacBook에서 약 1분 내로 완료됐다. full 변환은 전체 image extraction, storage, train/eval 반복 시간이 커지므로 5090 handoff 근거가 생긴 뒤 확장한다.

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
