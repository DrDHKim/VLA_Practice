from __future__ import annotations

import json

import cv2
import numpy as np
from torch.utils.data import DataLoader

from vla_drive.data.collate import driving_collate_fn
from vla_drive.data.datasets import JsonlDrivingDataset


def test_jsonl_dataset_resolves_relative_image_paths_and_collates(tmp_path) -> None:
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    for idx in range(2):
        image = np.full((12, 16, 3), fill_value=idx * 40 + 20, dtype=np.uint8)
        cv2.imwrite(str(image_dir / f"frame_{idx:05d}.png"), image)

    metadata_path = tmp_path / "metadata.jsonl"
    records = []
    for idx in range(2):
        records.append(
            {
                "observation": {
                    "sample_id": f"sample_{idx}",
                    "timestamp": float(idx),
                    "camera_front": f"images/frame_{idx:05d}.png",
                    "route_command": "lane_follow",
                    "route_waypoints_ego": [[float(t + 1), 0.5, 0.0] for t in range(8)],
                    "ego_speed_mps": 3.0 + idx,
                },
                "target": {
                    "future_waypoints_ego": [[float(t), 0.0] for t in range(8)],
                    "steer": 0.1,
                    "throttle": 0.2,
                    "brake": 0.0,
                },
            }
        )
    with metadata_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    dataset = JsonlDrivingDataset(metadata_path)
    assert len(dataset) == 2
    assert dataset[0].observation.camera_front.exists()

    loader = DataLoader(dataset, batch_size=2, collate_fn=lambda batch: driving_collate_fn(batch, image_size=8))
    batch = next(iter(loader))
    assert tuple(batch["images"].shape) == (2, 3, 4, 3, 8, 8)
    assert tuple(batch["future_waypoints_ego"].shape) == (2, 8, 3)
    assert tuple(batch["route_waypoints_ego"].shape) == (2, 8, 3)
    assert float(batch["route_waypoints_ego"][0, 0, 0]) == 1.0
    assert tuple(batch["controls"].shape) == (2, 3)
    assert batch["prompts"][0].startswith("Drive with command=lane_follow")
