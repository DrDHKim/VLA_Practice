from __future__ import annotations

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


def driving_collate_fn(samples, image_size: int | None = None, reasoning_mode: str = "fast"):
    """Convert DrivingSample objects into tensors and text prompts."""
    images = torch.stack([load_image_tensor(sample.observation.camera_front, image_size=image_size) for sample in samples])
    speeds = torch.tensor([sample.observation.ego_speed_mps for sample in samples], dtype=torch.float32)
    waypoints = torch.tensor([sample.target.future_waypoints_ego for sample in samples], dtype=torch.float32)
    controls = torch.tensor(
        [
            [
                sample.target.steer if sample.target.steer is not None else 0.0,
                sample.target.throttle if sample.target.throttle is not None else 0.0,
                sample.target.brake if sample.target.brake is not None else 0.0,
            ]
            for sample in samples
        ],
        dtype=torch.float32,
    )
    route_commands = [sample.observation.route_command for sample in samples]
    prompts = [
        _build_prompt(command=sample.observation.route_command, speed_mps=sample.observation.ego_speed_mps)
        for sample in samples
    ]
    reasoning_targets = [
        _reasoning_target(
            command=sample.observation.route_command,
            speed_mps=sample.observation.ego_speed_mps,
            explicit=sample.target.reasoning,
            mode=reasoning_mode,
        )
        for sample in samples
    ]
    reasoning_labels = torch.tensor(
        [_reasoning_label_id(target, mode=reasoning_mode) for target in reasoning_targets],
        dtype=torch.long,
    )
    sample_ids = [sample.observation.sample_id for sample in samples]

    image_paths = [str(sample.observation.camera_front) for sample in samples]

    return {
        "sample_ids": sample_ids,
        "image_paths": image_paths,
        "images": images,
        "ego_speed_mps": speeds,
        "route_commands": route_commands,
        "prompts": prompts,
        "reasoning_mode": reasoning_mode,
        "reasoning_targets": reasoning_targets,
        "reasoning_labels": reasoning_labels,
        "future_waypoints_ego": waypoints,
        "controls": controls,
    }


def _build_prompt(command: str, speed_mps: float) -> str:
    return "Drive with command=%s at speed=%.2f m/s and predict future ego-frame waypoints." % (
        command,
        speed_mps,
    )


def reasoning_label_count(mode: str) -> int:
    if mode == "fast":
        return len(REASONING_LABEL_TO_ID)
    if mode == "slow":
        return len(SLOW_REASONING_LABEL_TO_ID)
    raise ValueError(f"Unsupported reasoning_mode: {mode}")


def _reasoning_target(command: str, speed_mps: float, explicit: str | None = None, mode: str = "fast") -> str:
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
        speed_suffix = "slow" if (
            "slow" in normalized or "stop" in normalized or "brake" in normalized
        ) else "cruise"
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
    if "slow" in normalized or "stop" in normalized or "brake" in normalized:
        return REASONING_LABEL_TO_ID["slow_or_stop"]
    return REASONING_LABEL_TO_ID["keep_lane"]
