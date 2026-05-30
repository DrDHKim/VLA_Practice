from __future__ import annotations

import torch


def average_displacement_error(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.linalg.norm(pred - target, dim=-1).mean()


def final_displacement_error(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.linalg.norm(pred[:, -1] - target[:, -1], dim=-1).mean()

