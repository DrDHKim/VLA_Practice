#!/usr/bin/env python3
"""Render BEV route and control plots for a collected CARLA scene."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _load_records(scene_dir: Path) -> list[dict]:
    metadata_path = scene_dir / "metadata.jsonl"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.jsonl not found: {metadata_path}")
    records = []
    with metadata_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise RuntimeError(f"metadata is empty: {metadata_path}")
    return records


def _series(records: list[dict]):
    t = [float(r["observation"].get("timestamp", i)) for i, r in enumerate(records)]
    speed = [float(r["observation"].get("ego_speed_mps", 0.0)) for r in records]
    accel = [float(r["observation"].get("ego_accel_mps2", 0.0)) for r in records]
    steer = [float(r["target"].get("steer", 0.0)) for r in records]
    throttle = [float(r["target"].get("throttle", 0.0)) for r in records]
    brake = [float(r["target"].get("brake", 0.0)) for r in records]
    return t, speed, accel, steer, throttle, brake


def _positions(records: list[dict]) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for r in records:
        pos = r["observation"].get("ego_position")
        if pos is None:
            raise RuntimeError(
                "metadata has no observation.ego_position; rerun collection with the current script"
            )
        xs.append(float(pos["x"]))
        ys.append(float(pos["y"]))
    return xs, ys


def render_report(scene_dir: Path, out_dir: Path | None = None) -> tuple[Path, Path]:
    records = _load_records(scene_dir)
    out_dir = out_dir or scene_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    t, speed, accel, steer, throttle, brake = _series(records)
    xs, ys = _positions(records)

    bev_path = out_dir / "bev_route.png"
    fig, ax = plt.subplots(figsize=(7.5, 7.5), dpi=140)
    ax.plot(xs, ys, color="#1f77b4", linewidth=2.0, label="ego trajectory")
    ax.scatter(xs[0], ys[0], color="#2ca02c", s=70, label="start", zorder=3)
    ax.scatter(xs[-1], ys[-1], color="#d62728", s=70, label="end", zorder=3)
    step = max(1, len(xs) // 20)
    ax.quiver(
        xs[::step],
        ys[::step],
        [xs[min(i + 1, len(xs) - 1)] - xs[i] for i in range(0, len(xs), step)],
        [ys[min(i + 1, len(ys) - 1)] - ys[i] for i in range(0, len(ys), step)],
        angles="xy",
        scale_units="xy",
        scale=1,
        width=0.004,
        color="#444444",
        alpha=0.7,
    )
    ax.set_title("CARLA Scene BEV Route")
    ax.set_xlabel("world x (m)")
    ax.set_ylabel("world y (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(bev_path)
    plt.close(fig)

    controls_path = out_dir / "controls_timeseries.png"
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), dpi=140, sharex=True)
    axes[0].plot(t, speed, color="#1f77b4", label="speed")
    axes[0].set_ylabel("speed (m/s)")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(t, throttle, color="#2ca02c", label="throttle")
    axes[1].plot(t, brake, color="#d62728", label="brake")
    axes[1].set_ylabel("pedal")
    axes[1].set_ylim(-0.05, 1.05)
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    axes[2].plot(t, steer, color="#ff7f0e", label="steer")
    axes[2].plot(t, accel, color="#9467bd", alpha=0.65, label="accel")
    axes[2].set_ylabel("steer / accel")
    axes[2].set_xlabel("time (s)")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")

    fig.suptitle("CARLA Scene Controls")
    fig.tight_layout()
    fig.savefig(controls_path)
    plt.close(fig)

    print(f"REPORT_OK bev={bev_path} controls={controls_path}")
    return bev_path, controls_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render CARLA scene BEV/control report.")
    parser.add_argument("scene_dir_pos", nargs="?", type=Path, default=None)
    parser.add_argument("--scene-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    scene_dir = args.scene_dir or args.scene_dir_pos
    if scene_dir is None:
        parser.error("Provide SCENE_DIR as positional arg or --scene-dir")
    render_report(scene_dir, args.out_dir)


if __name__ == "__main__":
    main()
