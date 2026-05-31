from __future__ import annotations

import torch

from vla_drive.data.transforms import load_image_tensor


def driving_collate_fn(samples, image_size: int | None = None):
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
    sample_ids = [sample.observation.sample_id for sample in samples]

    return {
        "sample_ids": sample_ids,
        "images": images,
        "ego_speed_mps": speeds,
        "route_commands": route_commands,
        "prompts": prompts,
        "future_waypoints_ego": waypoints,
        "controls": controls,
    }


def _build_prompt(command: str, speed_mps: float) -> str:
    return "Drive with command=%s at speed=%.2f m/s and predict future ego-frame waypoints." % (
        command,
        speed_mps,
    )
