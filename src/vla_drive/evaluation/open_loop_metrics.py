from __future__ import annotations

import torch


def average_displacement_error(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.linalg.norm(pred[..., :2] - target[..., :2], dim=-1).mean()


def final_displacement_error(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return torch.linalg.norm(pred[:, -1, :2] - target[:, -1, :2], dim=-1).mean()


def route_deviation_error(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Mean lateral deviation from target ego-frame trajectory."""
    return torch.abs(pred[..., 1] - target[..., 1]).mean()


def collision_proxy_rate(pred: torch.Tensor, target: torch.Tensor, threshold_m: float = 2.0) -> torch.Tensor:
    """Proxy failure rate: any waypoint more than threshold meters from target."""
    distances = torch.linalg.norm(pred - target, dim=-1)
    return (distances.max(dim=1).values > threshold_m).float().mean()
