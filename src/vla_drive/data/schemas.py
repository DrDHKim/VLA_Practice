from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Observation:
    sample_id: str
    timestamp: float

    # ── Current frame, 3 cameras ──────────────────────
    camera_front: Path
    camera_front_left: Optional[Path] = None
    camera_front_right: Optional[Path] = None

    # ── Temporal frames: t-0.5s (t1), t-1.0s (t2), t-1.5s (t3) per camera ──
    # At fps=10, each step = 5 frames back.
    camera_front_t1: Optional[Path] = None
    camera_front_t2: Optional[Path] = None
    camera_front_t3: Optional[Path] = None
    camera_front_left_t1: Optional[Path] = None
    camera_front_left_t2: Optional[Path] = None
    camera_front_left_t3: Optional[Path] = None
    camera_front_right_t1: Optional[Path] = None
    camera_front_right_t2: Optional[Path] = None
    camera_front_right_t3: Optional[Path] = None

    # ── Navigation & ego state ────────────────────────────────────────────────
    route_command: str = "keep_lane"
    ego_speed_mps: float = 0.0
    ego_accel_mps2: Optional[float] = None   # scalar magnitude
    ego_heading_rad: Optional[float] = None  # yaw in CARLA world frame (radians)
    ego_yaw_rate_radps: Optional[float] = None  # yaw rate (angular velocity)


@dataclass(frozen=True)
class ActionTarget:
    # [T, 3]: each row = (Δx, Δy, Δθ) in ego frame, 0.5 s per step, T=10 → 5 s horizon
    future_waypoints_ego: list[list[float]]
    steer: Optional[float] = None
    throttle: Optional[float] = None
    brake: Optional[float] = None
    reasoning: Optional[str] = None


@dataclass(frozen=True)
class DrivingSample:
    observation: Observation
    target: ActionTarget
