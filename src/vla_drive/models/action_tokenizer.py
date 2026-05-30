from __future__ import annotations


class TrajectoryActionTokenizer:
    """TODO: AutoVLA-style discrete trajectory tokenization."""

    def fit(self, trajectories) -> None:
        raise NotImplementedError

    def encode(self, trajectory):
        raise NotImplementedError

    def decode(self, tokens):
        raise NotImplementedError

