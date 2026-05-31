from __future__ import annotations

import torch

from vla_drive.data.collate import _reasoning_label_id, _reasoning_target, reasoning_label_count
from vla_drive.models.vla_policy import build_reasoning_aux_policy
from vla_drive.training.losses import reasoning_aux_loss, waypoint_prediction_loss


def test_reasoning_target_heuristics() -> None:
    assert _reasoning_target("lane_follow", 4.0) == "keep_lane"
    assert _reasoning_target("turn_left", 4.0) == "turn_left"
    assert _reasoning_target("turn_right", 4.0) == "turn_right"
    assert _reasoning_target("lane_follow", 0.1) == "slow_or_stop"
    assert _reasoning_label_id("prepare to turn left") == 1
    assert _reasoning_label_id("brake for obstacle") == 3
    assert reasoning_label_count("fast") == 4


def test_slow_reasoning_target_uses_speed_bucket() -> None:
    assert _reasoning_target("lane_follow", 2.0, mode="slow") == "keep_lane_slow"
    assert _reasoning_target("lane_follow", 4.0, mode="slow") == "keep_lane_cruise"
    assert _reasoning_target("turn_left", 2.0, mode="slow") == "turn_left_slow"
    assert _reasoning_target("turn_right", 4.0, mode="slow") == "turn_right_cruise"
    assert _reasoning_label_id("turn_right_slow", mode="slow") == 4
    assert reasoning_label_count("slow") == 6


def test_reasoning_aux_policy_forward_backward() -> None:
    policy = build_reasoning_aux_policy(hidden_dim=32, waypoint_count=8, num_reasoning_labels=4)
    batch = {
        "images": torch.zeros(2, 3, 32, 32),
        "ego_speed_mps": torch.tensor([1.0, 2.0]),
        "reasoning_labels": torch.tensor([0, 1], dtype=torch.long),
    }
    target = torch.zeros(2, 8, 3)

    output = policy(batch)
    assert output["future_waypoints_ego"].shape == (2, 8, 3)
    assert output["reasoning_logits"].shape == (2, 4)

    loss = waypoint_prediction_loss(output["future_waypoints_ego"], target)
    loss = loss + 0.1 * reasoning_aux_loss(output["reasoning_logits"], batch["reasoning_labels"])
    loss.backward()
    assert loss.item() >= 0.0
    assert any(param.grad is not None for param in policy.reasoning_head.parameters())
