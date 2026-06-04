#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text.replace("\\", "/"))
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _route_records(report: dict) -> list[dict]:
    rows: list[dict] = []
    for route in report.get("routes", []):
        route_id = route.get("route_id", "route")
        for record in route.get("control_records", []):
            row = dict(record)
            row["route_id"] = route_id
            row["route_completion"] = route.get("route_completion", 0.0)
            row["driving_score"] = route.get("driving_score", 0.0)
            row["failure_reason"] = route.get("failure_reason")
            rows.append(row)
    return rows


def _draw_text_block(image: np.ndarray, lines: list[tuple[str, tuple[int, int, int]]], x: int, y: int) -> None:
    for idx, (text, color) in enumerate(lines):
        yy = y + idx * 22
        cv2.putText(image, text, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, text, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 1, cv2.LINE_AA)


def _draw_bar(image: np.ndarray, label: str, value: float, x: int, y: int, width: int, color: tuple[int, int, int]) -> None:
    value = max(0.0, min(1.0, float(value)))
    cv2.putText(image, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.rectangle(image, (x, y), (x + width, y + 12), (60, 60, 60), 1)
    cv2.rectangle(image, (x, y), (x + int(width * value), y + 12), color, -1)


def _draw_waypoint_map(
    image: np.ndarray,
    route_waypoints: list[list[float]],
    pred_waypoints: list[list[float]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    cv2.rectangle(image, (x, y), (x + width, y + height), (22, 22, 22), -1)
    cv2.rectangle(image, (x, y), (x + width, y + height), (90, 90, 90), 1)
    cv2.putText(image, "route wp (green) / pred wp (cyan)", (x + 10, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

    origin = (x + width // 2, y + height - 26)
    cv2.circle(image, origin, 5, (255, 255, 255), -1)
    cv2.arrowedLine(image, origin, (origin[0], y + 35), (180, 180, 180), 1, tipLength=0.04)
    scale = min(width / 18.0, height / 24.0)

    def project(wp: list[float]) -> tuple[int, int]:
        forward = float(wp[0])
        lateral_right = float(wp[1])
        return int(origin[0] + lateral_right * scale), int(origin[1] - forward * scale)

    _draw_polyline(image, [project(wp) for wp in route_waypoints], (80, 220, 80))
    _draw_polyline(image, [project(wp) for wp in pred_waypoints], (255, 210, 40))


def _draw_polyline(image: np.ndarray, points: list[tuple[int, int]], color: tuple[int, int, int]) -> None:
    if len(points) >= 2:
        for p0, p1 in zip(points, points[1:]):
            cv2.line(image, p0, p1, color, 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(image, point, 3, color, -1, cv2.LINE_AA)


def _render_frame(frame: np.ndarray, record: dict, report: dict, index: int, total: int) -> np.ndarray:
    target_h = 720
    target_w = 1280
    frame = cv2.resize(frame, (800, 450), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    canvas[:] = (18, 18, 18)
    canvas[0:450, 0:800] = frame

    speed = float(record.get("speed_mps", 0.0))
    accel = float(record.get("accel_mps2", 0.0))
    steer = float(record.get("steer", 0.0))
    throttle = float(record.get("throttle", 0.0))
    brake = float(record.get("brake", 0.0))
    reasoning = record.get("reasoning") or "N/A"
    route_command = record.get("route_command") or report.get("route_command") or "N/A"
    head_outputs = record.get("head_outputs", {})
    pred_wp = record.get("pred_waypoints_ego", []) or head_outputs.get("waypoint_head", []) or []
    route_wp = record.get("route_waypoints_ego", []) or []

    lines = [
        (f"route={record.get('route_id')} tick={record.get('tick')} frame={index + 1}/{total}", (245, 245, 245)),
        (f"cmd={route_command}", (210, 230, 255)),
        (f"speed={speed:.3f} m/s  accel={accel:.3f} m/s2", (245, 245, 245)),
        (f"steer={steer:+.3f}  throttle={throttle:.3f}  brake={brake:.3f}", (245, 245, 245)),
        (f"reasoning_head={reasoning}", (120, 220, 255) if reasoning != "slow_or_stop" else (80, 120, 255)),
        (f"waypoint_head[0]={_fmt_wp(pred_wp, 0)}", (255, 230, 120)),
        (f"waypoint_head[-1]={_fmt_wp(pred_wp, -1)}", (255, 230, 120)),
        ("action_head=N/A for reasoning_aux", (170, 170, 170)),
        (f"route_completion={float(record.get('route_completion', 0.0)) * 100:.2f}%  driving_score={float(record.get('driving_score', 0.0)) * 100:.2f}%", (245, 245, 245)),
        (f"failure={record.get('failure_reason')}", (120, 120, 255)),
    ]
    _draw_text_block(canvas, lines, 820, 34)
    _draw_bar(canvas, "steer left/right magnitude", abs(steer), 820, 300, 390, (70, 170, 255))
    _draw_bar(canvas, "throttle", throttle, 820, 350, 390, (70, 210, 90))
    _draw_bar(canvas, "brake", brake, 820, 400, 390, (70, 70, 230))
    _draw_waypoint_map(canvas, route_wp, pred_wp, 20, 478, 780, 210)
    return canvas


def _fmt_wp(waypoints: list[list[float]], idx: int) -> str:
    if not waypoints:
        return "N/A"
    wp = waypoints[idx]
    return "(x={:.2f}, y={:.2f}, th={:.2f})".format(float(wp[0]), float(wp[1]), float(wp[2]) if len(wp) > 2 else 0.0)


def render(report_path: Path, video_path: Path, fps: float) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    records = _route_records(report)
    if not records:
        raise RuntimeError(f"No control records in report: {report_path}")

    video_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        float(fps),
        (1280, 720),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {video_path}")

    written = 0
    for idx, record in enumerate(records):
        frame_path = _resolve_path(record["frame_path"])
        frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if frame is None:
            raise FileNotFoundError(f"Could not read frame: {frame_path}")
        writer.write(_render_frame(frame, record, report, idx, len(records)))
        written += 1
    writer.release()
    summary = {
        "video_path": str(video_path),
        "frame_count": written,
        "fps": float(fps),
        "report_path": str(report_path),
    }
    sidecar = video_path.with_suffix(".json")
    sidecar.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print("RENDER_LEARNED_CLOSED_LOOP_VIDEO_OK")
    print(json.dumps(summary, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render learned CARLA closed-loop HUD video.")
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--video-path", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=5.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    render(args.report_path, args.video_path, args.fps)
