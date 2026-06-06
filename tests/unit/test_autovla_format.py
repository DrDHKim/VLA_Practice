from __future__ import annotations

import numpy as np

from vla_drive.data.autovla_format import (
    action_special_tokens,
    build_instruction_example,
    build_reasoning_text,
    encode_action_text,
    parse_action_text,
)
from vla_drive.data.schemas import ActionTarget, DrivingSample, Observation
from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer


def _fitted_tokenizer(num_tokens: int = 8) -> TrajectoryActionTokenizer:
    rng = np.random.default_rng(0)
    trajs = [np.cumsum(rng.normal(scale=1.0, size=(10, 3)), axis=0).astype(np.float32) for _ in range(20)]
    tok = TrajectoryActionTokenizer(num_tokens=num_tokens)
    tok.fit(trajs)
    return tok


def test_action_token_text_roundtrip() -> None:
    text = encode_action_text([3, 1, 4, 1, 5])
    assert text == "<act_3><act_1><act_4><act_1><act_5>"
    assert parse_action_text("foo <act_3><act_1> bar <act_4>") == [3, 1, 4]
    assert len(action_special_tokens(256)) == 256
    assert action_special_tokens(3) == ["<act_0>", "<act_1>", "<act_2>"]


def test_reasoning_template_varies_with_state() -> None:
    stopped = build_reasoning_text("lane_follow", 0.0)
    cruising_turn = build_reasoning_text("turn_right", 5.0)
    braking = build_reasoning_text("lane_follow", 4.0, brake=0.9)
    assert "stopped" in stopped
    assert "turning right" in cruising_turn and "cruising" in cruising_turn
    assert "slowing down" in braking
    # explicit reasoning overrides template
    assert build_reasoning_text("lane_follow", 4.0, explicit="custom") == "custom"


def test_build_instruction_example_structure() -> None:
    tok = _fitted_tokenizer(num_tokens=8)
    waypoints = np.cumsum(np.full((10, 3), 0.3, dtype=np.float32), axis=0).tolist()
    sample = DrivingSample(
        observation=Observation(
            sample_id="scene_000_000001",
            timestamp=1.0,
            camera_front="F.png",
            camera_front_left="FL.png",
            camera_front_right="FR.png",
            route_command="turn_right",
            ego_speed_mps=4.0,
        ),
        target=ActionTarget(future_waypoints_ego=waypoints, brake=0.0),
    )
    ex = build_instruction_example(sample, tok, frames_per_camera=1)

    # 3 cameras, current frame only.
    assert ex["image_paths"] == ["F.png", "FL.png", "FR.png"]
    # prompt carries the command and speed.
    assert "turn_right" in ex["prompt"] and "4.0 m/s" in ex["prompt"]
    # completion = reasoning + 10 action tokens (one per waypoint).
    assert "Trajectory:" in ex["completion"]
    assert parse_action_text(ex["completion"]) == ex["action_token_ids"]
    assert len(ex["action_token_ids"]) == 10
    assert all(0 <= t < tok.num_tokens for t in ex["action_token_ids"])
