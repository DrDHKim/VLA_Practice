from __future__ import annotations

import torch

from vla_drive.models.vla_policy import build_dummy_policy
from vla_drive.training.losses import waypoint_prediction_loss


def test_dummy_vla_policy_forward_loss_backward() -> None:
    policy = build_dummy_policy(hidden_dim=32, waypoint_count=8)
    batch = {
        "images": torch.zeros(2, 3, 32, 32),
        "ego_speed_mps": torch.tensor([1.0, 2.0]),
    }
    target = torch.zeros(2, 8, 2)

    output = policy(batch)
    pred = output["future_waypoints_ego"]
    assert tuple(pred.shape) == (2, 8, 2)

    loss = waypoint_prediction_loss(pred, target)
    loss.backward()
    assert loss.item() >= 0.0
    assert any(param.grad is not None for param in policy.parameters())
