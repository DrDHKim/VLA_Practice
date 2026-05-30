from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Observation:
    sample_id: str
    timestamp: float
    camera_front: Path
    route_command: str
    ego_speed_mps: float
    camera_left: Optional[Path] = None
    camera_right: Optional[Path] = None
    camera_rear: Optional[Path] = None
    ego_accel_mps2: Optional[float] = None
    ego_yaw_rate: Optional[float] = None


@dataclass(frozen=True)
class ActionTarget:
    future_waypoints_ego: list[list[float]]
    steer: Optional[float] = None
    throttle: Optional[float] = None
    brake: Optional[float] = None
    reasoning: Optional[str] = None


@dataclass(frozen=True)
class DrivingSample:
    observation: Observation
    target: ActionTarget

