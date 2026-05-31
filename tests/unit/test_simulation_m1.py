from __future__ import annotations

from types import SimpleNamespace

from vla_drive.simulation.pid_controller import PIDWaypointController
from vla_drive.simulation.route_planner import _world_to_ego_xy


def test_pid_controller_steers_toward_left_waypoint() -> None:
    controller = PIDWaypointController(target_speed_mps=5.0)
    control = controller.control([[5.0, 0.0], [8.0, 2.0], [10.0, 3.0]], current_speed_mps=1.0)
    assert control.steer > 0.0
    assert control.throttle > 0.0
    assert control.brake == 0.0


def test_pid_controller_brakes_when_too_fast() -> None:
    controller = PIDWaypointController(target_speed_mps=5.0)
    control = controller.control([[10.0, 0.0]], current_speed_mps=12.0)
    assert control.throttle == 0.0
    assert control.brake > 0.0


def test_world_to_ego_xy_uses_vehicle_heading() -> None:
    transform = SimpleNamespace(
        location=SimpleNamespace(x=10.0, y=10.0),
        rotation=SimpleNamespace(yaw=90.0),
    )
    x, y = _world_to_ego_xy(transform, 10.0, 14.0)
    assert round(x, 6) == 4.0
    assert round(y, 6) == 0.0
