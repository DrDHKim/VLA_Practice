from __future__ import annotations

from vla_drive.evaluation.waypoint_control import waypoint_control_from_prediction


def test_waypoint_control_steers_toward_right_lateral_waypoint() -> None:
    control = waypoint_control_from_prediction(
        [[3.0, 1.0, 0.0], [10.0, 2.0, 0.0]],
        current_speed_mps=1.0,
        target_speed_mps=5.0,
    )

    assert control["steer"] > 0.0
    assert control["throttle"] > 0.0
    assert control["brake"] == 0.0


def test_waypoint_control_brakes_for_near_zero_forward_progress() -> None:
    control = waypoint_control_from_prediction(
        [[0.1, 0.0, 0.0], [0.2, 0.0, 0.0]],
        current_speed_mps=4.0,
        target_speed_mps=5.0,
    )

    assert control["throttle"] == 0.0
    assert control["brake"] > 0.0
