from __future__ import annotations

from types import SimpleNamespace

from vla_drive.simulation.route_planner import _world_to_ego_xy


def test_world_to_ego_xy_uses_vehicle_heading() -> None:
    transform = SimpleNamespace(
        location=SimpleNamespace(x=10.0, y=10.0),
        rotation=SimpleNamespace(yaw=90.0),
    )
    x, y = _world_to_ego_xy(transform, 10.0, 14.0)
    assert round(x, 6) == 4.0
    assert round(y, 6) == 0.0
