from __future__ import annotations

import torch
from torch import nn


class VLMBackbone(nn.Module):
    """Thin wrapper around Qwen2.5-VL/LLaVA-style models."""

    def __init__(self, model_name: str, freeze: bool = True) -> None:
        super().__init__()
        self.model_name = model_name
        self.freeze = freeze
        self.model = None
        self.processor = None

    def load(self) -> None:
        """TODO: load transformers model and processor."""
        raise NotImplementedError

    def encode(self, batch):
        """TODO: return pooled hidden state for waypoint/action heads."""
        raise NotImplementedError


class DummyDrivingBackbone(nn.Module):
    """Small image/speed encoder for smoke tests before attaching a VLM."""

    def __init__(self, hidden_dim: int = 64) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim
        self.image_encoder = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, stride=2, padding=1),
            nn.GELU(),
            nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
            nn.GELU(),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
        )
        self.proj = nn.Sequential(
            nn.Linear(33, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

    def encode(self, batch: dict[str, torch.Tensor]) -> torch.Tensor:
        images = batch["images"].float()
        speed = batch.get("ego_speed_mps")
        if speed is None:
            speed = torch.zeros(images.shape[0], device=images.device, dtype=images.dtype)
        speed = speed.to(device=images.device, dtype=images.dtype).view(images.shape[0], 1)
        image_features = self.image_encoder(images)
        return self.proj(torch.cat([image_features, speed], dim=1))
