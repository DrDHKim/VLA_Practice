from __future__ import annotations

import torch
from torch import nn


class WaypointHead(nn.Module):
    """MLP head predicting T future waypoints.

    Output shape: [B, T, waypoint_dim]
      - waypoint_dim=3 → (Δx, Δy, Δθ) per step  (AutoVLA spec)
      - waypoint_dim=2 → (Δx, Δy) legacy
    """

    def __init__(
        self,
        hidden_dim: int,
        waypoint_count: int = 10,
        waypoint_dim: int = 3,
    ) -> None:
        super().__init__()
        self.waypoint_count = waypoint_count
        self.waypoint_dim = waypoint_dim
        self.net = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, waypoint_count * waypoint_dim),
        )

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        waypoints = self.net(hidden)
        return waypoints.view(hidden.shape[0], self.waypoint_count, self.waypoint_dim)
