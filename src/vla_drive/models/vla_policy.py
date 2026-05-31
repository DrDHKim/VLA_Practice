from __future__ import annotations

import numpy as np
import torch
from torch import nn

from vla_drive.models.action_token_head import ActionTokenHead
from vla_drive.models.reasoning_head import ReasoningHead
from vla_drive.models.waypoint_head import WaypointHead


class VLADrivingPolicy(nn.Module):
    def __init__(
        self,
        backbone,
        hidden_dim: int,
        waypoint_count: int = 10,
        waypoint_dim: int = 3,
    ) -> None:
        super().__init__()
        self.backbone = backbone
        self.waypoint_head = WaypointHead(hidden_dim, waypoint_count, waypoint_dim)

    def forward(self, batch):
        hidden = self.backbone.encode(batch)
        return {"future_waypoints_ego": self.waypoint_head(hidden)}


class ReasoningAuxPolicy(nn.Module):
    """Waypoint policy with an auxiliary driving-reason classifier."""

    def __init__(
        self,
        backbone,
        hidden_dim: int,
        waypoint_count: int = 10,
        waypoint_dim: int = 3,
        num_reasoning_labels: int = 4,
    ) -> None:
        super().__init__()
        self.backbone = backbone
        self.waypoint_head = WaypointHead(hidden_dim, waypoint_count, waypoint_dim)
        self.reasoning_head = ReasoningHead(hidden_dim, num_reasoning_labels)

    def forward(self, batch):
        hidden = self.backbone.encode(batch)
        return {
            "future_waypoints_ego": self.waypoint_head(hidden),
            "reasoning_logits": self.reasoning_head(hidden),
        }


class ActionTokenPolicy(nn.Module):
    """Policy that predicts per-timestep action token logits.

    forward() returns {"action_logits": [B, T, K]}.
    decode_waypoints() converts token predictions to [B, T, 3] via tokenizer.
    """

    def __init__(
        self,
        backbone,
        hidden_dim: int,
        waypoint_count: int = 10,
        num_tokens: int = 256,
    ) -> None:
        super().__init__()
        self.backbone = backbone
        self.action_head = ActionTokenHead(hidden_dim, waypoint_count, num_tokens)
        self._waypoint_count = waypoint_count

    def forward(self, batch: dict) -> dict:
        hidden = self.backbone.encode(batch)
        return {"action_logits": self.action_head(hidden)}

    def decode_waypoints(self, batch: dict, tokenizer) -> torch.Tensor:
        """Greedy decode → [B, T, 3] trajectory tensor (Δx, Δy, Δθ)."""
        logits = self.forward(batch)["action_logits"]    # [B, T, K]
        token_ids = logits.argmax(dim=-1).cpu().numpy()  # [B, T]
        trajs = np.stack([tokenizer.decode(token_ids[b]) for b in range(token_ids.shape[0])])
        return torch.tensor(trajs, dtype=torch.float32)


# ── builder functions ─────────────────────────────────────────────────────────

def build_dummy_policy(
    hidden_dim: int = 64,
    waypoint_count: int = 10,
    waypoint_dim: int = 3,
) -> VLADrivingPolicy:
    from vla_drive.models.backbone_vlm import DummyDrivingBackbone

    return VLADrivingPolicy(
        backbone=DummyDrivingBackbone(hidden_dim=hidden_dim),
        hidden_dim=hidden_dim,
        waypoint_count=waypoint_count,
        waypoint_dim=waypoint_dim,
    )


def build_reasoning_aux_policy(
    hidden_dim: int = 64,
    waypoint_count: int = 10,
    waypoint_dim: int = 3,
    num_reasoning_labels: int = 4,
) -> ReasoningAuxPolicy:
    from vla_drive.models.backbone_vlm import DummyDrivingBackbone

    return ReasoningAuxPolicy(
        backbone=DummyDrivingBackbone(hidden_dim=hidden_dim),
        hidden_dim=hidden_dim,
        waypoint_count=waypoint_count,
        waypoint_dim=waypoint_dim,
        num_reasoning_labels=num_reasoning_labels,
    )


def build_action_token_policy(
    num_tokens: int = 256,
    hidden_dim: int = 64,
    waypoint_count: int = 10,
) -> ActionTokenPolicy:
    from vla_drive.models.backbone_vlm import DummyDrivingBackbone

    return ActionTokenPolicy(
        backbone=DummyDrivingBackbone(hidden_dim=hidden_dim),
        hidden_dim=hidden_dim,
        waypoint_count=waypoint_count,
        num_tokens=num_tokens,
    )


def build_vlm_action_token_policy(
    model_path: str,
    num_tokens: int = 256,
    freeze: bool = True,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    waypoint_count: int = 10,
) -> ActionTokenPolicy:
    from vla_drive.models.backbone_vlm import VLMBackbone
    from vla_drive.training.lora import apply_lora

    backbone = VLMBackbone(model_name_or_path=model_path, freeze=freeze)
    backbone.load()
    hidden_dim: int = backbone.model.config.hidden_size

    if not freeze:
        backbone.model = apply_lora(backbone.model, rank=lora_rank, alpha=lora_alpha)

    return ActionTokenPolicy(
        backbone=backbone,
        hidden_dim=hidden_dim,
        waypoint_count=waypoint_count,
        num_tokens=num_tokens,
    )


def build_vlm_policy(
    model_path: str,
    freeze: bool = True,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    waypoint_count: int = 10,
    waypoint_dim: int = 3,
) -> VLADrivingPolicy:
    from vla_drive.models.backbone_vlm import VLMBackbone
    from vla_drive.training.lora import apply_lora

    backbone = VLMBackbone(model_name_or_path=model_path, freeze=freeze)
    backbone.load()
    hidden_dim: int = backbone.model.config.hidden_size  # 2048 for Qwen2.5-VL-3B

    if not freeze:
        backbone.model = apply_lora(backbone.model, rank=lora_rank, alpha=lora_alpha)

    return VLADrivingPolicy(
        backbone=backbone,
        hidden_dim=hidden_dim,
        waypoint_count=waypoint_count,
        waypoint_dim=waypoint_dim,
    )
