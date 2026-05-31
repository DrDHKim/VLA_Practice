from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class TrajectoryActionTokenizer:
    """AutoVLA-style discrete trajectory tokenizer.

    Codebook is fit on per-step deltas (Δx, Δy, Δθ) via K-means.
    - Δx, Δy  : positional displacement in ego frame (metres)
    - Δθ      : heading change (radians, normalised to [-π, π])

    K=256 default for Mac smoke; target K=2048 (AutoVLA spec).

    Input trajectories must be [T, 3] arrays of absolute ego-frame waypoints
    (x, y, θ) or [T, 2] arrays of (x, y) — Δθ is then treated as 0.
    """

    DELTA_DIM = 3  # (Δx, Δy, Δθ)

    def __init__(self, num_tokens: int = 256) -> None:
        self.num_tokens = num_tokens
        self.codebook: np.ndarray | None = None  # [K, 3]

    # ── public API ────────────────────────────────────────────────────────────

    def fit(self, trajectories: list[np.ndarray]) -> None:
        """Fit codebook from a list of [T, 2] or [T, 3] trajectory arrays."""
        from sklearn.cluster import KMeans

        deltas = self._collect_deltas(trajectories)
        k = min(self.num_tokens, len(deltas))
        if k < self.num_tokens:
            import warnings
            warnings.warn(
                f"Only {len(deltas)} delta samples; reducing K {self.num_tokens}→{k}.",
                stacklevel=2,
            )
            self.num_tokens = k
        km = KMeans(n_clusters=k, random_state=42, n_init="auto")
        km.fit(deltas)
        self.codebook = km.cluster_centers_.astype(np.float32)  # [K, 3]

    def encode(self, trajectory: np.ndarray) -> np.ndarray:
        """Map [T, 2|3] absolute trajectory → [T] token index array."""
        self._check_fitted()
        traj = np.asarray(trajectory, dtype=np.float32)
        deltas = self._to_deltas(traj)
        return self._nearest(deltas)

    def decode(self, tokens: np.ndarray | list[int]) -> np.ndarray:
        """Map [T] token indices → [T, 3] absolute trajectory in ego frame."""
        self._check_fitted()
        tokens = np.asarray(tokens, dtype=np.int64)
        deltas = self.codebook[tokens]           # [T, 3]
        result = np.cumsum(deltas, axis=0)       # [T, 3] cumulative (x, y, θ)
        result[:, 2] = _normalise_angle(result[:, 2])
        return result

    def decode_xy(self, tokens: np.ndarray | list[int]) -> np.ndarray:
        """Convenience: decode and return only [T, 2] (x, y) positions."""
        return self.decode(tokens)[:, :2]

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._check_fitted()
        path.write_text(
            json.dumps({"num_tokens": self.num_tokens, "codebook": self.codebook.tolist()}),
            encoding="utf-8",
        )

    def load(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.num_tokens = int(data["num_tokens"])
        self.codebook = np.array(data["codebook"], dtype=np.float32)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_deltas(trajectory: np.ndarray) -> np.ndarray:
        """[T, 2|3] absolute positions → [T, 3] per-step deltas."""
        traj3 = _ensure_3d(trajectory)
        origin = np.zeros((1, 3), dtype=np.float32)
        padded = np.concatenate([origin, traj3], axis=0)  # [T+1, 3]
        deltas = np.diff(padded, axis=0)                   # [T, 3]
        deltas[:, 2] = _normalise_angle(deltas[:, 2])
        return deltas

    @classmethod
    def _collect_deltas(cls, trajectories: list[np.ndarray]) -> np.ndarray:
        parts = [cls._to_deltas(np.asarray(t, dtype=np.float32)) for t in trajectories]
        return np.concatenate(parts, axis=0)  # [N*T, 3]

    def _nearest(self, deltas: np.ndarray) -> np.ndarray:
        """Assign each [T, 3] delta row to nearest codebook entry."""
        diff = deltas[:, None, :] - self.codebook[None, :, :]  # [T, K, 3]
        dist2 = (diff ** 2).sum(axis=-1)                        # [T, K]
        return dist2.argmin(axis=-1).astype(np.int64)           # [T]

    def _check_fitted(self) -> None:
        if self.codebook is None:
            raise RuntimeError("Tokenizer not fitted. Call fit() or load() first.")


# ── module-level helpers ──────────────────────────────────────────────────────

def _normalise_angle(angles: np.ndarray) -> np.ndarray:
    return (angles + np.pi) % (2.0 * np.pi) - np.pi


def _ensure_3d(traj: np.ndarray) -> np.ndarray:
    """Pad [T, 2] → [T, 3] with Δθ=0; leave [T, 3] unchanged."""
    if traj.ndim == 2 and traj.shape[1] == 2:
        zeros = np.zeros((traj.shape[0], 1), dtype=np.float32)
        return np.concatenate([traj, zeros], axis=1)
    return traj
