from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleControl:
    steer: float
    throttle: float
    brake: float


class PIDWaypointController:
    """Minimal controller interface; implement lateral/longitudinal PID in M1."""

    def __init__(self, target_speed_mps: float = 6.0) -> None:
        self.target_speed_mps = target_speed_mps

    def control(self, waypoints, current_speed_mps: float) -> VehicleControl:
        raise NotImplementedError

