from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Union

import torch
from torch import nn


class VLMBackbone(nn.Module):
    """Thin wrapper around Qwen2.5-VL for image+text → pooled hidden state."""

    def __init__(self, model_name_or_path: Union[str, Path], freeze: bool = True) -> None:
        super().__init__()
        self.model_name_or_path = str(model_name_or_path)
        self.freeze = freeze
        self.model = None
        self.processor = None

    def load(self) -> None:
        from transformers import AutoModelForImageTextToText, AutoProcessor

        dtype = _select_dtype()
        self.processor = AutoProcessor.from_pretrained(self.model_name_or_path, use_fast=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_name_or_path,
            dtype=dtype,
            device_map=None,
            attn_implementation="eager",
        )
        if self.freeze:
            for param in self.model.parameters():
                param.requires_grad_(False)
        self.model.eval() if self.freeze else self.model.train()

    def to(self, *args, **kwargs):
        # propagate device/dtype change to inner model
        result = super().to(*args, **kwargs)
        if self.model is not None:
            self.model = self.model.to(*args, **kwargs)
        return result

    def encode(self, batch: dict) -> torch.Tensor:
        """Return mean-pooled last-layer hidden state [B, hidden_dim]."""
        from PIL import Image

        image_paths: list[str] = batch["image_paths"]
        prompts: list[str] = batch["prompts"]

        pil_images = [Image.open(p).convert("RGB") for p in image_paths]

        messages_batch = [
            [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
            for prompt in prompts
        ]
        texts = [
            self.processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
            for msgs in messages_batch
        ]

        inputs = self.processor(
            text=texts,
            images=pil_images,
            return_tensors="pt",
            padding=True,
        )

        device = next(iter(self.model.parameters())).device
        dtype = next(iter(self.model.parameters())).dtype
        inputs = {
            k: v.to(device=device, dtype=dtype) if (torch.is_tensor(v) and v.is_floating_point()) else
               v.to(device=device) if torch.is_tensor(v) else v
            for k, v in inputs.items()
        }

        ctx = torch.no_grad() if self.freeze else contextlib.nullcontext()
        with ctx:
            outputs = self.model(**inputs, output_hidden_states=True, use_cache=False)

        last_hidden = outputs.hidden_states[-1]  # [B, seq_len, hidden_dim]
        return last_hidden.mean(dim=1).float()   # [B, hidden_dim] in float32


def _select_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        return torch.bfloat16
    if torch.backends.mps.is_available():
        return torch.float16
    return torch.float32


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
