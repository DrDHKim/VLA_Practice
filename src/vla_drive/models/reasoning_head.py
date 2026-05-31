from __future__ import annotations

import torch
from torch import nn


class ReasoningHead(nn.Module):
    """Small auxiliary classifier for driving reasoning labels."""

    def __init__(self, hidden_dim: int, num_labels: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, num_labels),
        )

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.net(hidden)
