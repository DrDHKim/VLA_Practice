from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


RouteCommandLookaheadMode = str


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw_rad: float


def route_command_from_yaw_delta(delta_yaw_rad: float, threshold_rad: float = 0.35) -> str:
    """Map CARLA yaw delta to a high-level route command.

    CARLA yaw is left-handed in this project convention: positive yaw delta
    corresponds to a right turn.
    """
    if delta_yaw_rad > threshold_rad:
        return "turn_right"
    if delta_yaw_rad < -threshold_rad:
        return "turn_left"
    return "lane_follow"


ROAD_OPTION_TO_COMMAND = {
    "LEFT": "turn_left",
    "RIGHT": "turn_right",
    "STRAIGHT": "lane_follow",
    "LANEFOLLOW": "lane_follow",
    "CHANGELANELEFT": "lane_follow",
    "CHANGELANERIGHT": "lane_follow",
    "VOID": "lane_follow",
}


def route_command_from_road_option(road_option: Any, fallback: str = "lane_follow") -> str:
    """Map a CARLA agents ``RoadOption`` to this project's route command vocabulary.

    Accepts the enum member, its name string, or its integer value. The model
    only distinguishes {lane_follow, turn_left, turn_right}, so STRAIGHT and the
    lane-change options collapse to ``lane_follow``.
    """
    name = getattr(road_option, "name", None)
    if name is None:
        name = str(road_option)
    return ROAD_OPTION_TO_COMMAND.get(name.upper(), fallback)


def route_command_from_poses(
    poses: Sequence[Any],
    current_index: int = 0,
    lookahead_mode: RouteCommandLookaheadMode = "meters",
    lookahead_frames: int = 20,
    lookahead_meters: float = 30.0,
    threshold_rad: float = 0.35,
) -> str:
    """Generate a route command from a future pose sequence.

    `poses` may contain Pose2D objects, dicts with x/y/yaw_rad, or CARLA-like
    waypoints/transforms. In meters mode, the future pose is selected by path
    distance along the sequence; in frames mode, it is selected by index offset.
    """
    if len(poses) < 2:
        return "lane_follow"
    current_index = max(0, min(int(current_index), len(poses) - 1))
    lookahead_index = select_lookahead_index(
        poses,
        current_index=current_index,
        mode=lookahead_mode,
        frames=lookahead_frames,
        meters=lookahead_meters,
    )
    if lookahead_index <= current_index:
        return "lane_follow"

    current = coerce_pose2d(poses[current_index])
    future = coerce_pose2d(poses[lookahead_index])
    delta_yaw = normalize_angle(future.yaw_rad - current.yaw_rad)
    return route_command_from_yaw_delta(delta_yaw, threshold_rad=threshold_rad)


def select_lookahead_index(
    poses: Sequence[Any],
    current_index: int = 0,
    mode: RouteCommandLookaheadMode = "meters",
    frames: int = 20,
    meters: float = 30.0,
) -> int:
    if not poses:
        return 0
    current_index = max(0, min(int(current_index), len(poses) - 1))
    if mode == "frames":
        return min(len(poses) - 1, current_index + max(1, int(frames)))
    if mode != "meters":
        raise ValueError(f"Unsupported route command lookahead mode: {mode}")

    target_meters = max(0.0, float(meters))
    distance = 0.0
    prev = coerce_pose2d(poses[current_index])
    for idx in range(current_index + 1, len(poses)):
        current = coerce_pose2d(poses[idx])
        distance += math.hypot(current.x - prev.x, current.y - prev.y)
        if distance >= target_meters:
            return idx
        prev = current
    return len(poses) - 1


def coerce_pose2d(value: Any) -> Pose2D:
    if isinstance(value, Pose2D):
        return value
    if isinstance(value, dict):
        return Pose2D(
            x=float(value["x"]),
            y=float(value["y"]),
            yaw_rad=float(value["yaw_rad"]),
        )
    if hasattr(value, "transform"):
        transform = value.transform
        return _pose_from_transform(transform)
    if hasattr(value, "location") and hasattr(value, "rotation"):
        return _pose_from_transform(value)
    raise TypeError(f"Cannot coerce value to Pose2D: {type(value)!r}")


def normalize_angle(angle_rad: float) -> float:
    return (float(angle_rad) + math.pi) % (2.0 * math.pi) - math.pi


def _pose_from_transform(transform: Any) -> Pose2D:
    return Pose2D(
        x=float(transform.location.x),
        y=float(transform.location.y),
        yaw_rad=math.radians(float(transform.rotation.yaw)),
    )
