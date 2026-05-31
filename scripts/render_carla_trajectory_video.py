from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def _load_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    args = parser.parse_args()

    records = _load_records(Path(args.metadata))
    if not records:
        raise SystemExit("No metadata records found")

    points = np.array(
        [[r["location"]["x"], r["location"]["y"]] for r in records],
        dtype=np.float32,
    )
    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    span = np.maximum(maxs - mins, 1.0)

    margin = 72
    draw_w = args.width - 2 * margin
    draw_h = args.height - 2 * margin

    def project(point: np.ndarray) -> tuple[int, int]:
        norm = (point - mins) / span
        x = margin + int(norm[0] * draw_w)
        y = args.height - margin - int(norm[1] * draw_h)
        return x, y

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        args.fps,
        (args.width, args.height),
    )
    if not writer.isOpened():
        raise SystemExit("Could not open video writer: %s" % out_path)

    try:
        projected = [project(point) for point in points]
        for idx, record in enumerate(records):
            frame = np.full((args.height, args.width, 3), (245, 245, 242), dtype=np.uint8)
            cv2.rectangle(frame, (margin, margin), (args.width - margin, args.height - margin), (210, 210, 205), 1)

            if idx > 0:
                cv2.polylines(frame, [np.array(projected[: idx + 1], dtype=np.int32)], False, (42, 92, 170), 3)

            x, y = projected[idx]
            cv2.circle(frame, projected[0], 7, (40, 140, 80), -1)
            cv2.circle(frame, projected[-1], 7, (60, 60, 60), 2)
            cv2.circle(frame, (x, y), 9, (20, 80, 220), -1)

            velocity = record["velocity"]
            speed = float((velocity["x"] ** 2 + velocity["y"] ** 2 + velocity["z"] ** 2) ** 0.5)
            distance = float(np.linalg.norm(points[idx] - points[0]))

            cv2.putText(frame, "CARLA smoke drive trajectory", (36, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (35, 35, 35), 2)
            cv2.putText(frame, "frame %03d / %03d" % (idx + 1, len(records)), (36, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (60, 60, 60), 2)
            cv2.putText(frame, "speed %.2f m/s" % speed, (36, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (60, 60, 60), 2)
            cv2.putText(frame, "displacement %.2f m" % distance, (36, 142), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (60, 60, 60), 2)
            cv2.putText(frame, "RGB sensor frames are black in current Wine run", (36, args.height - 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1)

            writer.write(frame)
    finally:
        writer.release()

    print("TRAJECTORY_VIDEO_OK %s" % out_path)


if __name__ == "__main__":
    main()
