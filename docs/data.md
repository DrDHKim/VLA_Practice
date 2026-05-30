# Data

## Dataset Priority

1. CARLA short routes
2. CARLA weather variants
3. nuScenes mini
4. nuScenes full
5. NAVSIM or Bench2Drive

## CARLA First

CARLA is the fastest path to closed-loop feedback.

Scale policy:

- MacBook: collect 1-3 tiny smoke routes first, with low traffic and low image resolution.
- RTX 5090: scale to more routes, weather variants, traffic density, and longer collection jobs.
- AIP/H100: use only after the schema and evaluation are stable on MacBook and RTX 5090.

Tasks:

- collect 10 short routes with clear weather
- collect 10 routes with rain/fog/night variants
- log RGB, ego state, route command, expert waypoints/control
- build train/val/test splits by route, not by frame

## nuScenes Second

Use nuScenes mini before full nuScenes.

The mini split is suitable for MacBook schema/debug work. Full nuScenes should wait until the RTX 5090 or external storage path is ready.

Tasks:

- convert samples into the common schema
- extract ego-frame future trajectory
- map scene descriptions or route commands into text prompts
- run open-loop metric only at first

## NAVSIM / Bench2Drive Third

Add only after baseline training works.

Tasks:

- verify install
- map metrics into `closed_loop_metrics.py`
- compare to literature metrics where possible

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

## Initial File Format

Start with JSONL metadata plus image files:

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

Do not design a complex binary format until the schema stabilizes.

## Split Rule

Split by route or scene, not by frame. Frame-level random splits leak near-duplicate observations.
