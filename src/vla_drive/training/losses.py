from __future__ import annotations

import torch


def waypoint_l1_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.l1_loss(pred, target)


def final_displacement_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.l1_loss(pred[:, -1], target[:, -1])


def waypoint_prediction_loss(
    pred: torch.Tensor,
    target: torch.Tensor,
    l1_weight: float = 1.0,
    fde_weight: float = 1.0,
) -> torch.Tensor:
    return l1_weight * waypoint_l1_loss(pred, target) + fde_weight * final_displacement_loss(pred, target)
