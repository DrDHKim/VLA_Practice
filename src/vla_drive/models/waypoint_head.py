from __future__ import annotations

import torch
from torch import nn


class WaypointHead(nn.Module):
    def __init__(self, hidden_dim: int, waypoint_count: int = 8) -> None:
        super().__init__()
        self.waypoint_count = waypoint_count
        self.net = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, waypoint_count * 2),
        )

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        waypoints = self.net(hidden)
        return waypoints.view(hidden.shape[0], self.waypoint_count, 2)

