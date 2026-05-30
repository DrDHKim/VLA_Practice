from __future__ import annotations

import torch

from vla_drive.evaluation.open_loop_metrics import average_displacement_error, final_displacement_error


def test_open_loop_metrics_zero_for_identical_waypoints() -> None:
    target = torch.zeros(2, 8, 2)
    pred = torch.zeros(2, 8, 2)
    assert average_displacement_error(pred, target).item() == 0.0
    assert final_displacement_error(pred, target).item() == 0.0

