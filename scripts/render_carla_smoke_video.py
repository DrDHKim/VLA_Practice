from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", default="outputs/carla_smoke/latest/frames")
    parser.add_argument("--out", default="outputs/carla_smoke/latest/smoke_drive.mp4")
    parser.add_argument("--fps", type=float, default=10.0)
    args = parser.parse_args()

    frames_dir = Path(args.frames_dir)
    frame_paths = sorted(frames_dir.glob("frame_*.png"))
    if not frame_paths:
        raise SystemExit("No frames found under %s" % frames_dir)

    first = cv2.imread(str(frame_paths[0]))
    if first is None:
        raise SystemExit("Could not read first frame: %s" % frame_paths[0])

    height, width = first.shape[:2]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        args.fps,
        (width, height),
    )
    if not writer.isOpened():
        raise SystemExit("Could not open video writer: %s" % out_path)

    try:
        for frame_path in frame_paths:
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise SystemExit("Could not read frame: %s" % frame_path)
            writer.write(frame)
    finally:
        writer.release()

    print("VIDEO_OK %s" % out_path)


if __name__ == "__main__":
    main()
