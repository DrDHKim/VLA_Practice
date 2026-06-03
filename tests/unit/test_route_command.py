from __future__ import annotations

import math
from types import SimpleNamespace

from vla_drive.simulation.route_command import Pose2D, route_command_from_poses, select_lookahead_index
from vla_drive.simulation.route_planner import RoutePlanner


def test_route_command_uses_carla_left_handed_yaw_sign() -> None:
    poses = [
        Pose2D(x=0.0, y=0.0, yaw_rad=0.0),
        Pose2D(x=10.0, y=0.0, yaw_rad=0.4),
    ]
    assert route_command_from_poses(poses, lookahead_mode="frames", lookahead_frames=1) == "turn_right"

    poses = [
        Pose2D(x=0.0, y=0.0, yaw_rad=0.0),
        Pose2D(x=10.0, y=0.0, yaw_rad=-0.4),
    ]
    assert route_command_from_poses(poses, lookahead_mode="frames", lookahead_frames=1) == "turn_left"


def test_route_command_can_select_lookahead_by_meters() -> None:
    poses = [
        Pose2D(x=0.0, y=0.0, yaw_rad=0.0),
        Pose2D(x=3.0, y=0.0, yaw_rad=0.0),
        Pose2D(x=6.0, y=0.0, yaw_rad=0.0),
        Pose2D(x=10.0, y=0.0, yaw_rad=0.4),
    ]
    assert select_lookahead_index(poses, mode="meters", meters=10.0) == 3
    assert route_command_from_poses(poses, lookahead_mode="meters", lookahead_meters=10.0) == "turn_right"


def test_route_command_can_select_lookahead_by_frames() -> None:
    poses = [
        Pose2D(x=0.0, y=0.0, yaw_rad=0.0),
        Pose2D(x=1.0, y=0.0, yaw_rad=0.0),
        Pose2D(x=2.0, y=0.0, yaw_rad=0.4),
    ]
    assert select_lookahead_index(poses, mode="frames", frames=2) == 2
    assert route_command_from_poses(poses, lookahead_mode="frames", lookahead_frames=2) == "turn_right"


def test_route_planner_next_command_uses_shared_route_command_logic() -> None:
    planner = RoutePlanner(command_lookahead_mode="meters", command_lookahead_meters=30.0)
    planner._route = [
        _waypoint(0.0, 0.0, 0.0),
        _waypoint(15.0, 0.0, 0.0),
        _waypoint(30.0, 0.0, math.degrees(0.4)),
    ]
    planner._cursor = 0
    assert planner.next_command() == "turn_right"


def _waypoint(x: float, y: float, yaw_deg: float):
    return SimpleNamespace(
        transform=SimpleNamespace(
            location=SimpleNamespace(x=x, y=y),
            rotation=SimpleNamespace(yaw=yaw_deg),
        )
    )
