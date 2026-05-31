from __future__ import annotations

import json
from pathlib import Path

from torch.utils.data import Dataset

from vla_drive.data.schemas import ActionTarget, DrivingSample, Observation


class JsonlDrivingDataset(Dataset):
    """Common JSONL dataset for CARLA and converted nuScenes samples."""

    def __init__(self, metadata_path: str | Path, data_root: str | Path | None = None) -> None:
        self.metadata_path = Path(metadata_path)
        self.data_root = Path(data_root) if data_root is not None else self.metadata_path.parent
        with self.metadata_path.open("r", encoding="utf-8") as f:
            self.records = [json.loads(line) for line in f if line.strip()]

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> DrivingSample:
        record = self.records[index]
        obs = record["observation"]
        target = record["target"]
        return DrivingSample(
            observation=Observation(
                sample_id=obs["sample_id"],
                timestamp=float(obs["timestamp"]),
                camera_front=self._resolve_path(obs["camera_front"]),
                route_command=obs["route_command"],
                ego_speed_mps=float(obs["ego_speed_mps"]),
                camera_left=self._resolve_path(obs["camera_left"]) if obs.get("camera_left") else None,
                camera_right=self._resolve_path(obs["camera_right"]) if obs.get("camera_right") else None,
                camera_rear=self._resolve_path(obs["camera_rear"]) if obs.get("camera_rear") else None,
                ego_accel_mps2=obs.get("ego_accel_mps2"),
                ego_yaw_rate=obs.get("ego_yaw_rate"),
            ),
            target=ActionTarget(
                future_waypoints_ego=target["future_waypoints_ego"],
                steer=target.get("steer"),
                throttle=target.get("throttle"),
                brake=target.get("brake"),
                reasoning=target.get("reasoning"),
            ),
        )

    def _resolve_path(self, path: str | Path) -> Path:
        image_path = Path(path)
        if image_path.is_absolute():
            return image_path
        return (self.data_root / image_path).resolve()
