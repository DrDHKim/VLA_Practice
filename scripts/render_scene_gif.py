#!/usr/bin/env python3
"""Render a full-scene preview GIF for a CARLA collection scene.

Each GIF frame:
  [FL cam] | [Front cam + waypoint mini-map] | [FR cam]
  ─────────────────────── HUD strip ──────────────────

Usage:
  .conda/bin/python scripts/render_scene_gif.py --scene-dir <path>
  .conda/bin/python scripts/render_scene_gif.py <scene_dir>
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ── palette ───────────────────────────────────────────────────────────────────
C_WHITE  = (255, 255, 255)
C_GRAY   = (160, 160, 160)
C_CYAN   = (0,   220, 220)
C_YELLOW = (255, 220,  50)
C_GREEN  = (80,  220,  80)
C_RED    = (220,  80,  80)
C_ORANGE = (255, 165,   0)
C_HUD_BG = (18,  18,  18)
C_DIV    = (60,  60,  60)

HUD_H    = 52   # pixel height of bottom HUD strip
MINI_W   = 112  # waypoint mini-map width in pixels
MINI_H   = 92   # waypoint mini-map height in pixels
MINI_SCALE = 3.5  # px per metre


# ── fonts ─────────────────────────────────────────────────────────────────────
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Monaco.dfont",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


FONT_SM = _font(12)
FONT_MD = _font(14)


def _tw(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


# ── image helpers ─────────────────────────────────────────────────────────────
def _load(path: str, w: int, h: int) -> Image.Image:
    try:
        img = Image.open(path).convert("RGB")
        if img.size != (w, h):
            img = img.resize((w, h), Image.LANCZOS)
        return img
    except Exception:
        placeholder = Image.new("RGB", (w, h), (35, 35, 35))
        draw = ImageDraw.Draw(placeholder)
        draw.text((6, h // 2 - 8), "no image", fill=(120, 120, 120), font=FONT_SM)
        return placeholder


def _label(img: Image.Image, text: str) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    bb = draw.textbbox((0, 0), text, font=FONT_SM)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    draw.rectangle([(4, 4), (4 + tw + 8, 4 + th + 6)], fill=(0, 0, 0))
    draw.text((8, 7), text, fill=C_WHITE, font=FONT_SM)
    return out


# ── waypoint mini-map ─────────────────────────────────────────────────────────
def _minimap(waypoints: list[list[float]]) -> Image.Image:
    """MINI_W × MINI_H RGBA overlay showing future ego-frame trajectory."""
    img = Image.new("RGBA", (MINI_W, MINI_H), (18, 18, 18, 210))
    draw = ImageDraw.Draw(img)

    ex = MINI_W // 2
    ey = MINI_H - 12

    # faint distance rings (every 5 m)
    for d_m in range(5, 30, 5):
        r_px = int(d_m * MINI_SCALE)
        draw.ellipse(
            [(ex - r_px, ey - r_px), (ex + r_px, ey + r_px)],
            outline=(55, 55, 55, 180), width=1,
        )
        if d_m <= 20:
            draw.text((ex + 3, ey - r_px), f"{d_m}m", fill=(70, 70, 70, 200), font=FONT_SM)

    # ego arrow (pointing up = forward)
    draw.line([(ex, 4), (ex, ey + 8)], fill=(90, 90, 90, 180), width=1)
    draw.line([(ex - 12, ey), (ex + 12, ey)], fill=(70, 70, 70, 160), width=1)
    draw.text((ex + 5, 4), "fwd", fill=(95, 95, 95, 220), font=FONT_SM)
    draw.text((MINI_W - 34, ey + 2), "right", fill=(95, 95, 95, 220), font=FONT_SM)

    draw.polygon(
        [(ex, ey - 7), (ex - 4, ey + 4), (ex + 4, ey + 4)],
        fill=(80, 220, 80, 255),
    )

    n = len(waypoints)
    pts: list[tuple[int, int]] = []
    for i, wp in enumerate(waypoints):
        dx_m, dy_m = wp[0], wp[1]
        # ego frame: Δx = forward → up in image, Δy = right → right
        px = ex + int(dy_m * MINI_SCALE)
        py = ey - int(dx_m * MINI_SCALE)
        pts.append((px, py))
        ratio = i / max(1, n - 1)
        r = int(80 + 175 * ratio)
        g = int(220 - 140 * ratio)
        draw.ellipse([(px - 2, py - 2), (px + 2, py + 2)], fill=(r, g, 80, 255))

    if len(pts) >= 2:
        for a, b in zip(pts[:-1], pts[1:]):
            draw.line([a, b], fill=(200, 200, 100, 180), width=1)

    return img


# ── HUD strip ─────────────────────────────────────────────────────────────────
def _hud(record: dict, total_w: int, frame_pos: int, total_frames: int) -> Image.Image:
    img = Image.new("RGB", (total_w, HUD_H), C_HUD_BG)
    draw = ImageDraw.Draw(img)

    obs = record.get("observation", {})
    tgt = record.get("target", {})

    f_idx    = obs.get("frame_index", frame_pos)
    t_sec    = obs.get("timestamp", 0.0)
    cmd      = obs.get("route_command", "—")
    speed    = obs.get("ego_speed_mps", 0.0)
    accel    = obs.get("ego_accel_mps2", 0.0)
    steer    = tgt.get("steer", 0.0)
    throttle = tgt.get("throttle", 0.0)
    brake    = tgt.get("brake", 0.0)

    # ── row 1 ──
    x = 10
    base = f"frame {f_idx:4d}/{total_frames - 1}  t={t_sec:.2f}s  cmd(2s): "
    draw.text((x, 6), base, fill=C_GRAY, font=FONT_MD)
    x += _tw(draw, base, FONT_MD)

    draw.text((x, 6), cmd, fill=C_YELLOW, font=FONT_MD)
    x += _tw(draw, cmd, FONT_MD) + 18

    spd_txt = f"spd: {speed:.1f} m/s  acc: {accel:+.2f} m/s²"
    draw.text((x, 6), spd_txt, fill=C_CYAN, font=FONT_MD)

    # ── row 2: controls ──
    steer_col    = C_ORANGE if abs(steer) > 0.1 else (180, 180, 180)
    throttle_col = C_GREEN  if throttle > 0.05 else (180, 180, 180)
    brake_col    = C_RED    if brake > 0.05 else (180, 180, 180)

    items = [
        ("steer:",    f"{steer:+.3f}", steer_col),
        ("throttle:", f"{throttle:.3f}", throttle_col),
        ("brake:",    f"{brake:.3f}", brake_col),
    ]
    x = 10
    for lbl, val, col in items:
        draw.text((x, 30), lbl, fill=C_GRAY, font=FONT_MD)
        x += _tw(draw, lbl, FONT_MD) + 4
        draw.text((x, 30), val, fill=col, font=FONT_MD)
        x += _tw(draw, val, FONT_MD) + 28

    return img


# ── main render ───────────────────────────────────────────────────────────────
def render_gif(
    scene_dir: Path,
    out_path: Path,
    gif_fps: float = 5.0,
    stride: int = 2,
    cam_width: int = 320,
    max_frames: int | None = None,
    open_after: bool = False,
) -> Path:
    metadata_path = scene_dir / "metadata.jsonl"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.jsonl not found: {metadata_path}")

    records: list[dict] = []
    with metadata_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        raise RuntimeError("metadata.jsonl is empty")

    selected = records[::stride]
    if max_frames:
        selected = selected[:max_frames]
    total = len(records)

    # derive camera height from first available image
    first_front = records[0]["observation"].get("camera_front", "")
    try:
        probe = Image.open(first_front)
        orig_w, orig_h = probe.size
        probe.close()
    except Exception:
        orig_w, orig_h = 320, 180
    cam_h = round(cam_width * orig_h / orig_w)

    total_w = cam_width * 3
    print(f"scene: {scene_dir.name}  records={total}  selected={len(selected)}  "
          f"cam={cam_width}×{cam_h}  gif={total_w}×{cam_h + HUD_H}")

    frames_pil: list[Image.Image] = []

    for i, rec in enumerate(selected):
        obs = rec["observation"]

        front_path = obs.get("camera_front", "")
        fl_path    = obs.get("camera_front_left") or front_path
        fr_path    = obs.get("camera_front_right") or front_path

        front_img = _load(front_path, cam_width, cam_h)
        fl_img    = _load(fl_path,    cam_width, cam_h)
        fr_img    = _load(fr_path,    cam_width, cam_h)

        # waypoint mini-map overlay on front image (top-right corner)
        wps = rec.get("target", {}).get("future_waypoints_ego", [])
        if wps:
            mini = _minimap(wps)
            front_rgba = front_img.convert("RGBA")
            front_rgba.paste(mini, (cam_width - MINI_W - 5, 5), mini)
            front_img = front_rgba.convert("RGB")

        # camera labels
        fl_img    = _label(fl_img,    "FL")
        front_img = _label(front_img, "Front")
        fr_img    = _label(fr_img,    "FR")

        # camera strip with thin dividers
        cam_strip = Image.new("RGB", (total_w, cam_h), C_DIV)
        cam_strip.paste(fl_img,    (0,              0))
        cam_strip.paste(front_img, (cam_width,      0))
        cam_strip.paste(fr_img,    (cam_width * 2,  0))

        # HUD
        hud = _hud(rec, total_w, i * stride, total)

        # assemble
        frame = Image.new("RGB", (total_w, cam_h + HUD_H))
        frame.paste(cam_strip, (0, 0))
        frame.paste(hud, (0, cam_h))
        frames_pil.append(frame)

        if (i + 1) % 50 == 0 or (i + 1) == len(selected):
            print(f"  rendered {i + 1}/{len(selected)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration_ms = max(20, round(1000.0 / gif_fps))

    frames_pil[0].save(
        str(out_path),
        format="GIF",
        save_all=True,
        append_images=frames_pil[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )

    size_mb = out_path.stat().st_size / 1e6
    print(f"GIF_OK {out_path}  ({size_mb:.1f} MB  {len(frames_pil)} frames @ {gif_fps} fps)")

    if open_after:
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Safari", str(out_path)])
        else:
            subprocess.run(["xdg-open", str(out_path)])

    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render scene preview GIF: all 3 cameras + waypoint mini-map + HUD.",
    )
    parser.add_argument(
        "scene_dir_pos", nargs="?", type=Path, default=None,
        metavar="SCENE_DIR", help="Positional scene folder (alternative to --scene-dir)",
    )
    parser.add_argument("--scene-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None,
                        help="Output path (default: <scene_dir>/scene.gif)")
    parser.add_argument("--gif-fps", type=float, default=5.0,
                        help="GIF playback speed in fps (default: 5.0)")
    parser.add_argument("--stride", type=int, default=2,
                        help="Render every Nth JSONL record (default: 2)")
    parser.add_argument("--cam-width", type=int, default=320,
                        help="Width of each camera image in pixels (default: 320)")
    parser.add_argument("--max-frames", type=int, default=None,
                        help="Cap on number of GIF frames to render")
    parser.add_argument("--open", action="store_true", dest="open_after",
                        help="Open GIF in Safari after rendering (macOS)")
    args = parser.parse_args()

    scene_dir = args.scene_dir or args.scene_dir_pos
    if scene_dir is None:
        parser.error("Provide SCENE_DIR as positional arg or --scene-dir")

    out_path = args.out or (scene_dir / "scene.gif")
    render_gif(
        scene_dir=scene_dir,
        out_path=out_path,
        gif_fps=args.gif_fps,
        stride=args.stride,
        cam_width=args.cam_width,
        max_frames=args.max_frames,
        open_after=args.open_after,
    )


if __name__ == "__main__":
    main()

