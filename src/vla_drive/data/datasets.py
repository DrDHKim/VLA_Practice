from __future__ import annotations

import json
from pathlib import Path

from torch.utils.data import Dataset

from vla_drive.data.schemas import ActionTarget, DrivingSample, Observation

# Temporal camera key suffixes stored in JSONL
_CAM_NAMES = ("front", "front_left", "front_right")
_TEMPORAL_SUFFIXES = ("", "_t1", "_t2", "_t3")  # "" = current frame


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

        def _p(key: str) -> Path | None:
            v = obs.get(key)
            return self._resolve_path(v) if v else None

        return DrivingSample(
            observation=Observation(
                sample_id=obs["sample_id"],
                timestamp=float(obs["timestamp"]),
                camera_front=self._resolve_path(obs["camera_front"]),
                camera_front_left=_p("camera_front_left"),
                camera_front_right=_p("camera_front_right"),
                camera_front_t1=_p("camera_front_t1"),
                camera_front_t2=_p("camera_front_t2"),
                camera_front_t3=_p("camera_front_t3"),
                camera_front_left_t1=_p("camera_front_left_t1"),
                camera_front_left_t2=_p("camera_front_left_t2"),
                camera_front_left_t3=_p("camera_front_left_t3"),
                camera_front_right_t1=_p("camera_front_right_t1"),
                camera_front_right_t2=_p("camera_front_right_t2"),
                camera_front_right_t3=_p("camera_front_right_t3"),
                route_command=obs.get("route_command", "keep_lane"),
                ego_speed_mps=float(obs.get("ego_speed_mps", 0.0)),
                ego_accel_mps2=obs.get("ego_accel_mps2"),
                ego_heading_rad=obs.get("ego_heading_rad"),
                ego_yaw_rate_radps=obs.get("ego_yaw_rate_radps"),  # Added for OpenDriveVLA
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
