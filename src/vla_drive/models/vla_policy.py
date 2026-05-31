from __future__ import annotations

from torch import nn

from vla_drive.models.waypoint_head import WaypointHead


class VLADrivingPolicy(nn.Module):
    def __init__(self, backbone, hidden_dim: int, waypoint_count: int) -> None:
        super().__init__()
        self.backbone = backbone
        self.waypoint_head = WaypointHead(hidden_dim, waypoint_count)

    def forward(self, batch):
        hidden = self.backbone.encode(batch)
        return {"future_waypoints_ego": self.waypoint_head(hidden)}


def build_dummy_policy(hidden_dim: int = 64, waypoint_count: int = 8) -> VLADrivingPolicy:
    from vla_drive.models.backbone_vlm import DummyDrivingBackbone

    return VLADrivingPolicy(
        backbone=DummyDrivingBackbone(hidden_dim=hidden_dim),
        hidden_dim=hidden_dim,
        waypoint_count=waypoint_count,
    )


def build_vlm_policy(
    model_path: str,
    freeze: bool = True,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    waypoint_count: int = 8,
) -> VLADrivingPolicy:
    """Build a VLADrivingPolicy backed by a real VLM (Qwen2.5-VL).

    frozen_vlm stage: freeze=True  → only WaypointHead trains.
    lora_vlm stage:   freeze=False → LoRA adapters + WaypointHead train.
    """
    from vla_drive.models.backbone_vlm import VLMBackbone
    from vla_drive.training.lora import apply_lora

    backbone = VLMBackbone(model_name_or_path=model_path, freeze=freeze)
    backbone.load()

    hidden_dim: int = backbone.model.config.hidden_size  # 2048 for Qwen2.5-VL-3B

    if not freeze:
        backbone.model = apply_lora(backbone.model, rank=lora_rank, alpha=lora_alpha)

    return VLADrivingPolicy(backbone=backbone, hidden_dim=hidden_dim, waypoint_count=waypoint_count)
