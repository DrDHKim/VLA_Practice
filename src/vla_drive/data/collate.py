from __future__ import annotations

from pathlib import Path

import torch

from vla_drive.data.transforms import load_image_tensor


REASONING_LABEL_TO_ID = {
    "keep_lane": 0,
    "turn_left": 1,
    "turn_right": 2,
    "slow_or_stop": 3,
}

SLOW_REASONING_LABEL_TO_ID = {
    "keep_lane_slow": 0,
    "keep_lane_cruise": 1,
    "turn_left_slow": 2,
    "turn_left_cruise": 3,
    "turn_right_slow": 4,
    "turn_right_cruise": 5,
}

# Camera names and temporal suffixes, ordered to match AutoVLA's 3-cam × 4-frame layout.
# Axis 0 = camera (front, front_left, front_right)
# Axis 1 = time   (t0=current, t1=0.5s ago, t2=1.0s ago, t3=1.5s ago)
_CAM_KEYS = (
    ("camera_front",       "camera_front_t1",       "camera_front_t2",       "camera_front_t3"),
    ("camera_front_left",  "camera_front_left_t1",  "camera_front_left_t2",  "camera_front_left_t3"),
    ("camera_front_right", "camera_front_right_t1", "camera_front_right_t2", "camera_front_right_t3"),
)
NUM_CAMERAS = 3
NUM_FRAMES = 4


def driving_collate_fn(samples, image_size: int | None = None, reasoning_mode: str = "fast", vlm_frames_per_camera: int = NUM_FRAMES):
    """Convert DrivingSample objects into tensors and text prompts.

    images shape: [B, NUM_CAMERAS, NUM_FRAMES, C, H, W]
      - Falls back to single-camera (shape [B, 1, 1, C, H, W]) when lateral /
        temporal fields are absent (old-format data).
    future_waypoints_ego shape: [B, T, 3]  (Δx, Δy, Δθ)
      - If loaded data has [T, 2] rows, Δθ is zero-padded.
    route_waypoints_ego shape: [B, T, 3]
      - Route centerline input. Missing old-format data is zero-filled.
    """
    # ── images ─────────────────────────────────────────────────────────────
    images = _build_image_tensor(samples, image_size)

    # ── ego state ───────────────────────────────────────────────────────────
    speeds = torch.tensor(
        [s.observation.ego_speed_mps for s in samples], dtype=torch.float32
    )
    accels = torch.tensor(
        [s.observation.ego_accel_mps2 or 0.0 for s in samples], dtype=torch.float32
    )

    # ── waypoints [B, T, 3] ─────────────────────────────────────────────────
    waypoints = _build_waypoint_tensor(samples)
    route_waypoints = _build_route_waypoint_tensor(samples, waypoint_count=int(waypoints.shape[1]))

    # ── controls ────────────────────────────────────────────────────────────
    controls = torch.tensor(
        [
            [
                s.target.steer if s.target.steer is not None else 0.0,
                s.target.throttle if s.target.throttle is not None else 0.0,
                s.target.brake if s.target.brake is not None else 0.0,
            ]
            for s in samples
        ],
        dtype=torch.float32,
    )

    route_commands = [s.observation.route_command for s in samples]
    prompts = [
        _build_prompt(s.observation.route_command, s.observation.ego_speed_mps)
        for s in samples
    ]

    reasoning_targets = [
        _reasoning_target(
            command=s.observation.route_command,
            speed_mps=s.observation.ego_speed_mps,
            explicit=s.target.reasoning,
            mode=reasoning_mode,
        )
        for s in samples
    ]
    reasoning_labels = torch.tensor(
        [_reasoning_label_id(t, mode=reasoning_mode) for t in reasoning_targets],
        dtype=torch.long,
    )

    # image_paths: list of current-front paths (for VLMBackbone backward compat)
    image_paths = [str(s.observation.camera_front) for s in samples]
    # all_image_paths: 샘플당 (3 cam × vlm_frames_per_camera) 경로. VLM forward 비용은
    # 이미지 수에 비례하므로(12장≈3장의 4배), frames_per_camera로 시간축을 줄일 수 있다.
    all_image_paths = _build_all_image_paths(samples, frames_per_camera=vlm_frames_per_camera)

    return {
        "sample_ids": [s.observation.sample_id for s in samples],
        "image_paths": image_paths,
        "all_image_paths": all_image_paths,
        "images": images,
        "ego_speed_mps": speeds,
        "ego_accel_mps2": accels,
        "route_commands": route_commands,
        "prompts": prompts,
        "reasoning_mode": reasoning_mode,
        "reasoning_targets": reasoning_targets,
        "reasoning_labels": reasoning_labels,
        "route_waypoints_ego": route_waypoints,
        "future_waypoints_ego": waypoints,
        "controls": controls,
    }


# ─────────────────────────── helpers ─────────────────────────────────────────

def _build_image_tensor(samples, image_size: int | None) -> torch.Tensor:
    """Build [B, C, NUM_CAMERAS, NUM_FRAMES, H, W] → stored as [B, NUM_CAMERAS, NUM_FRAMES, C, H, W]."""
    batch = []
    for s in samples:
        cam_tensors = []
        obs = s.observation
        for cam_row in _CAM_KEYS:
            frame_tensors = []
            for key in cam_row:
                path: Path | None = getattr(obs, key, None)
                if path is None:
                    # fall back: repeat the front-current frame to fill missing slots
                    path = obs.camera_front
                frame_tensors.append(load_image_tensor(path, image_size=image_size))
            cam_tensors.append(torch.stack(frame_tensors, dim=0))  # [NUM_FRAMES, C, H, W]
        batch.append(torch.stack(cam_tensors, dim=0))              # [NUM_CAMERAS, NUM_FRAMES, C, H, W]
    return torch.stack(batch, dim=0)                               # [B, NUM_CAMERAS, NUM_FRAMES, C, H, W]


def _build_waypoint_tensor(samples) -> torch.Tensor:
    """[B, T, 3] — zero-pad Δθ if data only has 2D rows."""
    rows = []
    for s in samples:
        wps = s.target.future_waypoints_ego
        if wps and len(wps[0]) == 2:
            wps = [[r[0], r[1], 0.0] for r in wps]
        rows.append(wps)
    return torch.tensor(rows, dtype=torch.float32)


def _build_route_waypoint_tensor(samples, waypoint_count: int) -> torch.Tensor:
    rows = []
    for s in samples:
        route_wps = s.observation.route_waypoints_ego or []
        rows.append(_normalize_waypoints(route_wps, waypoint_count))
    return torch.tensor(rows, dtype=torch.float32)


def _normalize_waypoints(waypoints: list[list[float]], count: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for waypoint in waypoints[:count]:
        if len(waypoint) >= 3:
            rows.append([float(waypoint[0]), float(waypoint[1]), float(waypoint[2])])
        elif len(waypoint) == 2:
            rows.append([float(waypoint[0]), float(waypoint[1]), 0.0])
    while len(rows) < count:
        rows.append([0.0, 0.0, 0.0])
    return rows


def _build_all_image_paths(samples, frames_per_camera: int = NUM_FRAMES) -> list[list[str]]:
    """(3 cam × frames_per_camera) image paths per sample in camera-major order.

    frames_per_camera=4 → 12장(현재+t1~t3). =1 → 3카메라 현재프레임만(AutoVLA 3캠 유지).
    """
    frames_per_camera = max(1, min(int(frames_per_camera), NUM_FRAMES))
    result = []
    for s in samples:
        obs = s.observation
        paths = []
        for cam_row in _CAM_KEYS:
            for key in cam_row[:frames_per_camera]:
                p: Path | None = getattr(obs, key, None)
                paths.append(str(p if p is not None else obs.camera_front))
        result.append(paths)
    return result


def _build_prompt(command: str, speed_mps: float) -> str:
    return "Drive with command=%s at speed=%.2f m/s, follow route waypoints, and predict future ego-frame waypoints." % (
        command, speed_mps,
    )


def reasoning_label_count(mode: str) -> int:
    if mode == "fast":
        return len(REASONING_LABEL_TO_ID)
    if mode == "slow":
        return len(SLOW_REASONING_LABEL_TO_ID)
    raise ValueError(f"Unsupported reasoning_mode: {mode}")


def _reasoning_target(
    command: str, speed_mps: float, explicit: str | None = None, mode: str = "fast"
) -> str:
    if explicit:
        return explicit
    if mode == "slow":
        speed_suffix = "slow" if speed_mps < 3.0 else "cruise"
        if command == "turn_left":
            return f"turn_left_{speed_suffix}"
        if command == "turn_right":
            return f"turn_right_{speed_suffix}"
        return f"keep_lane_{speed_suffix}"
    if mode != "fast":
        raise ValueError(f"Unsupported reasoning_mode: {mode}")
    if speed_mps < 0.5:
        return "slow_or_stop"
    if command == "turn_left":
        return "turn_left"
    if command == "turn_right":
        return "turn_right"
    return "keep_lane"


def _reasoning_label_id(target: str, mode: str = "fast") -> int:
    normalized = target.strip().lower()
    if mode == "slow":
        if normalized in SLOW_REASONING_LABEL_TO_ID:
            return SLOW_REASONING_LABEL_TO_ID[normalized]
        speed_suffix = "slow" if any(w in normalized for w in ("slow", "stop", "brake")) else "cruise"
        if "left" in normalized:
            return SLOW_REASONING_LABEL_TO_ID[f"turn_left_{speed_suffix}"]
        if "right" in normalized:
            return SLOW_REASONING_LABEL_TO_ID[f"turn_right_{speed_suffix}"]
        return SLOW_REASONING_LABEL_TO_ID[f"keep_lane_{speed_suffix}"]
    if mode != "fast":
        raise ValueError(f"Unsupported reasoning_mode: {mode}")
    if normalized in REASONING_LABEL_TO_ID:
        return REASONING_LABEL_TO_ID[normalized]
    if "left" in normalized:
        return REASONING_LABEL_TO_ID["turn_left"]
    if "right" in normalized:
        return REASONING_LABEL_TO_ID["turn_right"]
    if any(w in normalized for w in ("slow", "stop", "brake")):
        return REASONING_LABEL_TO_ID["slow_or_stop"]
    return REASONING_LABEL_TO_ID["keep_lane"]
