from __future__ import annotations

import numpy as np

from vla_drive.data.autovla_format import build_completion
from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer
from vla_drive.models.autovla_generate import decode_trajectory_from_text


def _fitted_tokenizer(num_tokens: int = 16) -> TrajectoryActionTokenizer:
    rng = np.random.default_rng(1)
    trajs = [np.cumsum(rng.normal(scale=1.0, size=(10, 3)), axis=0).astype(np.float32) for _ in range(40)]
    tok = TrajectoryActionTokenizer(num_tokens=num_tokens)
    tok.fit(trajs)
    return tok


def test_decode_trajectory_from_generated_text() -> None:
    tok = _fitted_tokenizer()
    token_ids = [3, 3, 5, 7, 2, 9, 1, 0, 4, 6]
    text = build_completion("Cruising; keep lane.", token_ids)  # "...Trajectory: <act_3>..."
    traj = decode_trajectory_from_text(text, tok)
    assert traj.shape == (10, 3)
    # matches direct tokenizer.decode of the same ids
    expected = tok.decode(np.asarray(token_ids))
    assert np.allclose(traj, expected)


def test_decode_empty_when_no_action_tokens() -> None:
    tok = _fitted_tokenizer()
    traj = decode_trajectory_from_text("just reasoning, no tokens", tok)
    assert traj.shape == (0, 3)
