from __future__ import annotations

import torch
from torch import nn


class ActionTokenHead(nn.Module):
    """Predict per-timestep action token logits from a pooled hidden state.

    Output shape: [B, T, K]  where K = num_tokens.
    """

    def __init__(self, hidden_dim: int, waypoint_count: int, num_tokens: int) -> None:
        super().__init__()
        self.waypoint_count = waypoint_count
        self.num_tokens = num_tokens
        self.net = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, waypoint_count * num_tokens),
        )

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        logits = self.net(hidden)
        return logits.view(hidden.shape[0], self.waypoint_count, self.num_tokens)
