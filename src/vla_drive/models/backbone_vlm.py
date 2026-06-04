from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Union

import torch
from torch import nn


class VLMBackbone(nn.Module):
    """Qwen2.5-VL wrapper — supports AutoVLA-style 12-image input.

    Input: batch["all_image_paths"]  — list[list[str]], shape [B, 12]
           (3 cameras × 4 temporal frames, camera-major order)
    Fallback: batch["image_paths"]   — list[str], shape [B] (single front frame)

    Output: mean-pooled last hidden state [B, hidden_dim] in float32.
    """

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
        result = super().to(*args, **kwargs)
        if self.model is not None:
            self.model = self.model.to(*args, **kwargs)
        return result

    def encode(self, batch: dict) -> torch.Tensor:
        """Return [B, hidden_dim] mean-pooled hidden state."""
        from PIL import Image

        prompts: list[str] = batch["prompts"]

        # Prefer 12-image multi-view paths; fall back to single front-image path.
        all_paths: list[list[str]] | None = batch.get("all_image_paths")
        if all_paths and len(all_paths[0]) > 1:
            # Multi-image path: each sample gets 12 images (3 cam × 4 frame)
            pil_per_sample = [
                [Image.open(p).convert("RGB") for p in paths]
                for paths in all_paths
            ]
            num_images_per_sample = len(pil_per_sample[0])
        else:
            # Single-image fallback
            image_paths: list[str] = batch["image_paths"]
            pil_per_sample = [[Image.open(p).convert("RGB")] for p in image_paths]
            num_images_per_sample = 1

        messages_batch = [
            [
                {
                    "role": "user",
                    "content": [{"type": "image"}] * num_images_per_sample
                    + [{"type": "text", "text": prompt}],
                }
            ]
            for prompt in prompts
        ]
        texts = [
            self.processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
            for msgs in messages_batch
        ]

        # Qwen2.5-VL processor expects a flat list of PIL images across the batch.
        flat_images = [img for imgs in pil_per_sample for img in imgs]

        inputs = self.processor(
            text=texts,
            images=flat_images,
            return_tensors="pt",
            padding=True,
        )

        device = next(iter(self.model.parameters())).device
        dtype = next(iter(self.model.parameters())).dtype
        inputs = {
            k: v.to(device=device, dtype=dtype) if (torch.is_tensor(v) and v.is_floating_point())
            else v.to(device=device) if torch.is_tensor(v)
            else v
            for k, v in inputs.items()
        }

        ctx = torch.no_grad() if self.freeze else contextlib.nullcontext()
        with ctx:
            outputs = self.model(**inputs, output_hidden_states=True, use_cache=False)

        last_hidden = outputs.hidden_states[-1]   # [B, seq_len, hidden_dim]
        return last_hidden.mean(dim=1).float()    # [B, hidden_dim]


def _select_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        return torch.bfloat16
    if torch.backends.mps.is_available():
        return torch.float16
    return torch.float32


class DummyDrivingBackbone(nn.Module):
    """Lightweight CNN backbone for smoke tests.

    Accepts [B, NUM_CAMERAS, NUM_FRAMES, C, H, W] or legacy [B, C, H, W].
    Front-camera current frame is used; remaining views/frames are ignored.
    Route command is injected as a compact one-hot feature so Mac-scale
    training remains command-conditioned without loading a full VLM backbone.
    """

    COMMAND_TO_INDEX = {
        "lane_follow": 0,
        "keep_lane": 0,
        "turn_left": 1,
        "left": 1,
        "turn_right": 2,
        "right": 2,
    }

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
            nn.Linear(36, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

    def encode(self, batch: dict) -> torch.Tensor:
        images = batch["images"].float()
        # Support both [B, NUM_CAMERAS, NUM_FRAMES, C, H, W] and legacy [B, C, H, W]
        if images.ndim == 6:
            images = images[:, 0, 0]  # front camera, current frame → [B, C, H, W]
        speed = batch.get("ego_speed_mps")
        if speed is None:
            speed = torch.zeros(images.shape[0], device=images.device, dtype=images.dtype)
        speed = speed.to(device=images.device, dtype=images.dtype).view(images.shape[0], 1)
        route_features = self._route_command_features(batch, images.shape[0], images.device, images.dtype)
        image_features = self.image_encoder(images)
        return self.proj(torch.cat([image_features, speed, route_features], dim=1))

    def _route_command_features(
        self,
        batch: dict,
        batch_size: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        route_commands = batch.get("route_commands")
        features = torch.zeros(batch_size, 3, device=device, dtype=dtype)
        if route_commands is None:
            return features
        for row_idx, command in enumerate(route_commands[:batch_size]):
            command_idx = self.COMMAND_TO_INDEX.get(str(command))
            if command_idx is not None:
                features[row_idx, command_idx] = 1.0
        return features
