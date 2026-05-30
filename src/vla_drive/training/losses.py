from __future__ import annotations

import torch


def waypoint_l1_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.l1_loss(pred, target)


def final_displacement_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.l1_loss(pred[:, -1], target[:, -1])

