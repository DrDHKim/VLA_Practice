from __future__ import annotations

import math


def waypoint_control_from_prediction(
    waypoints: list[list[float]],
    current_speed_mps: float,
    target_speed_mps: float = 5.0,
    horizon_seconds: float = 5.0,
    lookahead_min_m: float = 2.0,
    steer_gain: float = 1.6,
    speed_gain: float = 0.35,
    brake_gain: float = 0.45,
) -> dict[str, float]:
    """Convert predicted ego-frame waypoints to a CARLA VehicleControl dict.

    This is an evaluation-only adapter. Positive ego-frame y means right, which
    matches CARLA's positive steer direction.
    """
    if not waypoints:
        return {"steer": 0.0, "throttle": 0.0, "brake": 1.0}

    lookahead = _select_lookahead(waypoints, lookahead_min_m)
    x = float(lookahead[0])
    y = float(lookahead[1])
    angle = math.atan2(y, max(0.5, x))
    steer = _clamp(float(steer_gain) * angle, -1.0, 1.0)

    final_x = max(0.0, float(waypoints[-1][0]))
    desired_speed = min(float(target_speed_mps), final_x / max(0.1, float(horizon_seconds)))
    speed_error = desired_speed - max(0.0, float(current_speed_mps))
    throttle = _clamp(float(speed_gain) * speed_error, 0.0, 1.0)
    brake = _clamp(float(brake_gain) * -speed_error, 0.0, 1.0)
    if desired_speed < 0.2 and current_speed_mps > 0.2:
        brake = max(brake, 0.35)
    return {"steer": steer, "throttle": throttle, "brake": brake}


def _select_lookahead(waypoints: list[list[float]], lookahead_min_m: float) -> list[float]:
    for waypoint in waypoints:
        if float(waypoint[0]) >= lookahead_min_m:
            return waypoint
    return waypoints[-1]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
