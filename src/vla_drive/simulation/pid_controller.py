from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class VehicleControl:
    steer: float
    throttle: float
    brake: float


class PIDWaypointController:
    """Simple pure-pursuit lateral controller plus proportional speed control."""

    def __init__(
        self,
        target_speed_mps: float = 6.0,
        steer_gain: float = 1.2,
        speed_kp: float = 0.35,
        brake_kp: float = 0.25,
    ) -> None:
        self.target_speed_mps = target_speed_mps
        self.steer_gain = steer_gain
        self.speed_kp = speed_kp
        self.brake_kp = brake_kp

    def control(self, waypoints, current_speed_mps: float) -> VehicleControl:
        if not waypoints:
            return VehicleControl(steer=0.0, throttle=0.0, brake=1.0)

        target = waypoints[min(2, len(waypoints) - 1)]
        x = float(target[0])
        y = float(target[1])
        heading_error = math.atan2(y, max(1e-3, x))
        steer = _clamp(self.steer_gain * heading_error, -1.0, 1.0)

        speed_error = float(self.target_speed_mps) - float(current_speed_mps)
        if speed_error >= 0.0:
            throttle = _clamp(self.speed_kp * speed_error, 0.0, 0.75)
            brake = 0.0
        else:
            throttle = 0.0
            brake = _clamp(self.brake_kp * -speed_error, 0.0, 1.0)

        return VehicleControl(steer=steer, throttle=throttle, brake=brake)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
