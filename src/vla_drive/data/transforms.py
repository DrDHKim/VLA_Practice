from __future__ import annotations

from pathlib import Path

import cv2
import torch


def load_image_tensor(path: str | Path, image_size: int | None = None) -> torch.Tensor:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    if image_size is not None:
        image = cv2.resize(image, (int(image_size), int(image_size)), interpolation=cv2.INTER_AREA)
    tensor = torch.from_numpy(image).permute(2, 0, 1).contiguous().float()
    return tensor / 255.0


def build_image_transform(image_size: int | None = None):
    return lambda path: load_image_tensor(path, image_size=image_size)
