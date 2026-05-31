from __future__ import annotations

import numpy as np
import pytest
import torch

from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer
from vla_drive.models.vla_policy import build_action_token_policy
from vla_drive.training.losses import action_token_loss


def _make_trajectories(n: int = 20, T: int = 8) -> list[np.ndarray]:
    rng = np.random.default_rng(0)
    trajs = []
    for _ in range(n):
        deltas = rng.normal(loc=[1.0, 0.0, 0.0], scale=[0.3, 0.1, 0.05], size=(T, 3)).astype(np.float32)
        trajs.append(np.cumsum(deltas, axis=0))
    return trajs


def test_fit_encode_decode_roundtrip() -> None:
    trajs = _make_trajectories(30, T=8)
    tok = TrajectoryActionTokenizer(num_tokens=16)
    tok.fit(trajs)

    traj = trajs[0]
    tokens = tok.encode(traj)
    assert tokens.shape == (8,)
    assert tokens.dtype == np.int64
    assert tokens.min() >= 0 and tokens.max() < 16

    recovered = tok.decode(tokens)
    assert recovered.shape == (8, 3)
    assert np.abs(recovered - traj).mean() < 1.0


def test_save_load_roundtrip(tmp_path) -> None:
    trajs = _make_trajectories(20, T=8)
    tok = TrajectoryActionTokenizer(num_tokens=16)
    tok.fit(trajs)

    path = tmp_path / "tokenizer.json"
    tok.save(path)

    tok2 = TrajectoryActionTokenizer()
    tok2.load(path)

    assert tok2.num_tokens == 16
    np.testing.assert_allclose(tok2.codebook, tok.codebook, rtol=1e-5)

    traj = trajs[0]
    np.testing.assert_array_equal(tok.encode(traj), tok2.encode(traj))


def test_action_token_loss_shape() -> None:
    B, T, K = 4, 8, 16
    logits = torch.randn(B, T, K)
    targets = torch.randint(0, K, (B, T))
    loss = action_token_loss(logits, targets)
    assert loss.ndim == 0   # scalar
    assert loss.item() > 0


def test_action_token_policy_forward_backward() -> None:
    policy = build_action_token_policy(num_tokens=16, hidden_dim=32, waypoint_count=8)
    batch = {
        "images": torch.zeros(2, 3, 32, 32),
        "ego_speed_mps": torch.tensor([1.0, 2.0]),
    }
    output = policy(batch)
    logits = output["action_logits"]
    assert logits.shape == (2, 8, 16)

    targets = torch.zeros(2, 8, dtype=torch.long)
    loss = action_token_loss(logits, targets)
    loss.backward()
    assert loss.item() >= 0.0
    assert any(p.grad is not None for p in policy.parameters())


def test_decode_waypoints() -> None:
    trajs = _make_trajectories(20, T=8)
    tok = TrajectoryActionTokenizer(num_tokens=16)
    tok.fit(trajs)

    policy = build_action_token_policy(num_tokens=16, hidden_dim=32, waypoint_count=8)
    batch = {
        "images": torch.zeros(2, 3, 32, 32),
        "ego_speed_mps": torch.tensor([1.0, 2.0]),
    }
    waypoints = policy.decode_waypoints(batch, tok)
    assert waypoints.shape == (2, 8, 3)
