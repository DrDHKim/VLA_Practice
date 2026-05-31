from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class TrajectoryActionTokenizer:
    """AutoVLA-style discrete trajectory tokenization via K-means on step deltas.

    Each timestep t is assigned one action token representing (∆x, ∆y)
    movement from the previous position.  The codebook is fit on the
    empirical delta distribution from training trajectories.

    Usage:
        tokenizer = TrajectoryActionTokenizer(num_tokens=256)
        tokenizer.fit(list_of_traj_arrays)   # each [T, 2], abs ego coords
        token_ids = tokenizer.encode(traj)   # [T] integer array
        traj_hat  = tokenizer.decode(token_ids)  # [T, 2] abs ego coords
        tokenizer.save("checkpoints/tokenizer.json")
        tokenizer.load("checkpoints/tokenizer.json")
    """

    def __init__(self, num_tokens: int = 256) -> None:
        self.num_tokens = num_tokens
        self.codebook: np.ndarray | None = None  # [K, 2]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, trajectories: list[np.ndarray]) -> None:
        """Fit codebook from a list of [T, 2] trajectory arrays."""
        from sklearn.cluster import KMeans

        deltas = self._collect_deltas(trajectories)
        k = min(self.num_tokens, len(deltas))
        if k < self.num_tokens:
            import warnings
            warnings.warn(
                f"Only {len(deltas)} delta samples available; reducing K from {self.num_tokens} to {k}.",
                stacklevel=2,
            )
            self.num_tokens = k
        km = KMeans(n_clusters=k, random_state=42, n_init="auto")
        km.fit(deltas)
        self.codebook = km.cluster_centers_.astype(np.float32)

    def encode(self, trajectory: np.ndarray) -> np.ndarray:
        """Map [T, 2] absolute trajectory → [T] token index array."""
        self._check_fitted()
        deltas = self._to_deltas(np.asarray(trajectory, dtype=np.float32))
        return self._nearest(deltas)

    def decode(self, tokens: np.ndarray | list[int]) -> np.ndarray:
        """Map [T] token indices → [T, 2] absolute trajectory (ego frame)."""
        self._check_fitted()
        tokens = np.asarray(tokens, dtype=np.int64)
        deltas = self.codebook[tokens]           # [T, 2]
        return np.cumsum(deltas, axis=0)         # integrate to absolute positions

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._check_fitted()
        data = {
            "num_tokens": self.num_tokens,
            "codebook": self.codebook.tolist(),
        }
        path.write_text(json.dumps(data), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.num_tokens = int(data["num_tokens"])
        self.codebook = np.array(data["codebook"], dtype=np.float32)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_deltas(trajectory: np.ndarray) -> np.ndarray:
        """[T, 2] absolute positions → [T, 2] per-step deltas.

        delta_t = pos_t - pos_{t-1}, with pos_0 = origin [0, 0].
        """
        origin = np.zeros((1, 2), dtype=np.float32)
        padded = np.concatenate([origin, trajectory], axis=0)  # [T+1, 2]
        return np.diff(padded, axis=0)                          # [T, 2]

    @staticmethod
    def _collect_deltas(trajectories: list[np.ndarray]) -> np.ndarray:
        parts = [TrajectoryActionTokenizer._to_deltas(np.asarray(t, dtype=np.float32)) for t in trajectories]
        return np.concatenate(parts, axis=0)  # [N*T, 2]

    def _nearest(self, deltas: np.ndarray) -> np.ndarray:
        """Assign each delta row to its nearest codebook entry."""
        # deltas: [T, 2], codebook: [K, 2]
        # squared distances: [T, K]
        diff = deltas[:, None, :] - self.codebook[None, :, :]  # [T, K, 2]
        dist2 = (diff ** 2).sum(axis=-1)                        # [T, K]
        return dist2.argmin(axis=-1).astype(np.int64)           # [T]

    def _check_fitted(self) -> None:
        if self.codebook is None:
            raise RuntimeError("Tokenizer not fitted. Call fit() or load() first.")
