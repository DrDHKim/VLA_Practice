from __future__ import annotations

import torch

from vla_drive.models.waypoint_head import WaypointHead


def test_waypoint_head_shape() -> None:
    head = WaypointHead(hidden_dim=16, waypoint_count=8)
    output = head(torch.zeros(4, 16))
    assert tuple(output.shape) == (4, 8, 3)

