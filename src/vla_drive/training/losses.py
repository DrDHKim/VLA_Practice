from __future__ import annotations

import torch
import torch.nn.functional as F


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


def action_token_loss(logits: torch.Tensor, token_targets: torch.Tensor) -> torch.Tensor:
    """Cross-entropy loss for per-timestep action token prediction.

    Args:
        logits:        [B, T, K] - raw per-step token logits
        token_targets: [B, T]    - ground-truth token indices (long)
    Returns:
        Scalar cross-entropy loss averaged over B and T.
    """
    B, T, K = logits.shape
    return F.cross_entropy(logits.reshape(B * T, K), token_targets.reshape(B * T))
