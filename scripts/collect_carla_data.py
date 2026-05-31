"""CARLA data collection script.

AutoVLA-aligned I/O:
- 3 cameras: front (0°), front-left (-60°), front-right (+60°)
- 4 temporal frames per camera @ 0.5 s intervals (fps=10 → every 5 frames)
- T=10 future waypoints as (Δx, Δy, Δθ) in ego frame, 0.5 s per step
- ego_accel_mps2 (scalar), ego_heading_rad (CARLA world yaw, radians)

Post-processing note: raw frames are buffered first, then JSONL is written
after the full episode so temporal look-ahead is always available.
Valid frame range: [HIST_STEP*3, total_frames - FUTURE_STEP*10)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import queue
import random
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vla_drive.simulation.carla_agent import CarlaVLAAgent
from vla_drive.simulation.carla_client import CarlaClient
from vla_drive.simulation.pid_controller import PIDWaypointController
from vla_drive.simulation.route_planner import RoutePlanner
from vla_drive.utils.io import JsonlWriter, ensure_dir


DEFAULT_CONFIG = REPO_ROOT / "src/vla_drive/configs/carla_rgb_waypoint.yaml"

# Temporal sampling: at fps=10, 0.5 s = 5 frames
HIST_STEP = 5    # frames between temporal history samples
FUTURE_STEP = 5  # frames between future waypoint steps
N_HISTORY = 3    # how many past temporal frames to include (t-0.5s, t-1s, t-1.5s)
N_FUTURE = 10    # planning horizon (T=10 → 5 s)


# ─────────────────────────── config helpers ──────────────────────────────────

def _load_config(path: Path) -> dict[str, Any]:
    try:
        import yaml
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return _load_simple_yaml(path)


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip() or line.lstrip().startswith("- "):
                continue
            indent = len(line) - len(line.lstrip(" "))
            key, _, value = line.strip().partition(":")
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if value.strip() == "":
                child: dict[str, Any] = {}
                parent[key] = child
                stack.append((indent, child))
            else:
                parent[key] = _parse_scalar(value.strip())
    return root


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value.strip('"').strip("'")


def _cfg(config: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


# ─────────────────────────── CARLA helpers ───────────────────────────────────

def _add_carla_paths() -> None:
    carla_root = os.environ.get("CARLA_ROOT_WIN", r"C:\CARLA")
    python_api = os.path.join(carla_root, "PythonAPI", "carla")
    egg = os.path.join(python_api, "dist", "carla-0.9.15-py3.7-win-amd64.egg")
    for path in (egg, python_api):
        if path not in sys.path:
            sys.path.insert(0, path)


def _spawn_vehicle(world: Any, preferred_filter: str) -> Any:
    blueprints = world.get_blueprint_library()
    vehicle_bp = random.choice(list(blueprints.filter(preferred_filter)))
    spawn_points = list(world.get_map().get_spawn_points())
    random.shuffle(spawn_points)
    for transform in spawn_points:
        vehicle = world.try_spawn_actor(vehicle_bp, transform)
        if vehicle is not None:
            return vehicle
    raise RuntimeError("Could not spawn ego vehicle")


def _spawn_rgb_camera(
    world: Any,
    vehicle: Any,
    width: int,
    height: int,
    fov: float,
    fps: float,
    x: float = 1.6,
    y: float = 0.0,
    z: float = 1.7,
    yaw: float = 0.0,
    pitch: float = -5.0,
) -> Any:
    import carla

    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(width))
    bp.set_attribute("image_size_y", str(height))
    bp.set_attribute("fov", str(fov))
    bp.set_attribute("sensor_tick", str(1.0 / fps))
    if bp.has_attribute("enable_postprocess_effects"):
        bp.set_attribute("enable_postprocess_effects", "True")
    if bp.has_attribute("gamma"):
        bp.set_attribute("gamma", "2.2")
    transform = carla.Transform(
        carla.Location(x=x, y=y, z=z),
        carla.Rotation(pitch=pitch, yaw=yaw),
    )
    return world.spawn_actor(bp, transform, attach_to=vehicle)


def _speed_mps(vehicle: Any) -> float:
    v = vehicle.get_velocity()
    return float(math.sqrt(v.x**2 + v.y**2 + v.z**2))


def _accel_mps2(vehicle: Any) -> float:
    a = vehicle.get_acceleration()
    return float(math.sqrt(a.x**2 + a.y**2 + a.z**2))


# ─────────────────────────── geometry ────────────────────────────────────────

def _world_to_ego_delta(
    ego_x: float, ego_y: float, ego_yaw_rad: float,
    fut_x: float, fut_y: float, fut_yaw_rad: float,
) -> tuple[float, float, float]:
    """Return (Δx, Δy, Δθ) of a future position in the current ego frame.

    CARLA world: X=forward, Y=right, yaw positive = clockwise from east.
    Ego frame: X=forward along vehicle heading, Y=right.
    """
    dx_w = fut_x - ego_x
    dy_w = fut_y - ego_y
    cos_y = math.cos(ego_yaw_rad)
    sin_y = math.sin(ego_yaw_rad)
    dx_ego = cos_y * dx_w + sin_y * dy_w
    dy_ego = -sin_y * dx_w + cos_y * dy_w
    dh = fut_yaw_rad - ego_yaw_rad
    dh = (dh + math.pi) % (2.0 * math.pi) - math.pi  # normalise to [-π, π]
    return dx_ego, dy_ego, dh


# ─────────────────────────── path helpers ────────────────────────────────────

def _normalize_output_root(path: Path) -> Path:
    if os.name == "nt" and not path.drive and str(path).startswith("\\"):
        return Path("Z:" + str(path))
    return path


def _metadata_path(path: Path) -> str:
    text = str(path)
    if os.name == "nt" and text.lower().startswith("z:\\"):
        return "/" + text[3:].replace("\\", "/")
    return text.replace("\\", "/")


def _drain_queue(q: queue.Queue[Any]) -> None:
    while True:
        try:
            q.get_nowait()
        except queue.Empty:
            return


# ─────────────────────────── main collect ────────────────────────────────────

def collect(config: dict[str, Any], output_root: Path | None = None) -> Path:
    _add_carla_paths()
    import carla  # noqa: F401 – imported inside Wine Python

    sim_cfg = config.get("simulation", {})
    collect_cfg = config.get("collection", {})
    data_cfg = config.get("data", {})

    out_root = _normalize_output_root(
        output_root or Path(str(data_cfg.get("root", "/Volumes/DATASET/vla_drive_carla/tiny")))
    )
    out_root = ensure_dir(out_root)
    frames_dir = ensure_dir(out_root / "images")
    metadata_path = out_root / "metadata.jsonl"

    fps = float(collect_cfg.get("fps", 10.0))
    seconds = float(collect_cfg.get("seconds", 30.0))
    warmup_seconds = float(collect_cfg.get("warmup_seconds", 2.0))
    frame_count = max(1, int(seconds * fps))
    fixed_delta_seconds = float(sim_cfg.get("fixed_delta_seconds", 1.0 / fps))
    timeout = float(sim_cfg.get("timeout_seconds", 120.0))

    carla_client = CarlaClient(
        host=str(sim_cfg.get("host", "127.0.0.1")),
        port=int(sim_cfg.get("port", 2000)),
        timeout_seconds=timeout,
        town=str(sim_cfg.get("town", "Town01")),
        weather=str(sim_cfg.get("weather", "ClearNoon")),
        synchronous_mode=bool(sim_cfg.get("synchronous_mode", True)),
        fixed_delta_seconds=fixed_delta_seconds,
    )
    world = carla_client.connect()

    front_q: queue.Queue[Any] = queue.Queue()
    fl_q: queue.Queue[Any] = queue.Queue()
    fr_q: queue.Queue[Any] = queue.Queue()

    try:
        vehicle = _spawn_vehicle(world, str(collect_cfg.get("vehicle_filter", "vehicle.tesla.model3")))
        carla_client.actors.append(vehicle)

        planner = RoutePlanner(
            world=world,
            route_length=int(collect_cfg.get("route_length", 60)),
            waypoint_spacing_m=float(collect_cfg.get("waypoint_spacing_m", 2.0)),
            lookahead_count=8,
        )
        planner.build_from_spawn(vehicle.get_transform())
        controller = PIDWaypointController(
            target_speed_mps=float(collect_cfg.get("target_speed_mps", 5.0))
        )
        agent = CarlaVLAAgent(planner, controller)

        img_w = int(collect_cfg.get("image_width", 320))
        img_h = int(collect_cfg.get("image_height", 180))
        fov = float(collect_cfg.get("fov", 90.0))

        cam_front = _spawn_rgb_camera(world, vehicle, img_w, img_h, fov, fps,
                                      x=1.6, y=0.0, z=1.7, yaw=0.0, pitch=-5.0)
        cam_fl = _spawn_rgb_camera(world, vehicle, img_w, img_h, fov, fps,
                                   x=1.3, y=-0.3, z=1.7, yaw=-60.0, pitch=-5.0)
        cam_fr = _spawn_rgb_camera(world, vehicle, img_w, img_h, fov, fps,
                                   x=1.3, y=0.3, z=1.7, yaw=60.0, pitch=-5.0)
        for cam in (cam_front, cam_fl, cam_fr):
            carla_client.actors.append(cam)
        cam_front.listen(front_q.put)
        cam_fl.listen(fl_q.put)
        cam_fr.listen(fr_q.put)

        # ── warmup ──────────────────────────────────────────────────────────
        warmup_ticks = max(1, int(warmup_seconds / fixed_delta_seconds))
        for _ in range(warmup_ticks):
            control, _, _ = agent.run_step(vehicle)
            vehicle.apply_control(control)
            carla_client.tick()
        for q in (front_q, fl_q, fr_q):
            _drain_queue(q)

        # ── raw frame buffer ─────────────────────────────────────────────────
        raw: list[dict[str, Any]] = []

        for idx in range(frame_count):
            control, _, command = agent.run_step(vehicle)
            vehicle.apply_control(control)
            frame_id = carla_client.tick()

            front_img = front_q.get(timeout=timeout)
            fl_img = fl_q.get(timeout=timeout)
            fr_img = fr_q.get(timeout=timeout)

            p_front = frames_dir / ("frame_%05d_front.png" % idx)
            p_fl = frames_dir / ("frame_%05d_fl.png" % idx)
            p_fr = frames_dir / ("frame_%05d_fr.png" % idx)
            front_img.save_to_disk(str(p_front))
            fl_img.save_to_disk(str(p_fl))
            fr_img.save_to_disk(str(p_fr))

            t = vehicle.get_transform()
            raw.append({
                "idx": idx,
                "frame_id": frame_id,
                "front": p_front,
                "fl": p_fl,
                "fr": p_fr,
                "x": t.location.x,
                "y": t.location.y,
                "yaw_rad": math.radians(t.rotation.yaw),
                "speed": _speed_mps(vehicle),
                "accel": _accel_mps2(vehicle),
                "command": command,
                "steer": float(control.steer),
                "throttle": float(control.throttle),
                "brake": float(control.brake),
            })

        # ── post-process: write JSONL for valid frames ───────────────────────
        min_idx = N_HISTORY * HIST_STEP               # need history
        max_idx = len(raw) - N_FUTURE * FUTURE_STEP   # need future

        written = 0
        with JsonlWriter(metadata_path) as writer:
            for i in range(min_idx, max_idx):
                f = raw[i]
                hist = [raw[i - j * HIST_STEP] for j in range(1, N_HISTORY + 1)]
                future_wps = []
                for step in range(1, N_FUTURE + 1):
                    fut = raw[i + step * FUTURE_STEP]
                    dx, dy, dh = _world_to_ego_delta(
                        f["x"], f["y"], f["yaw_rad"],
                        fut["x"], fut["y"], fut["yaw_rad"],
                    )
                    future_wps.append([round(dx, 4), round(dy, 4), round(dh, 5)])

                writer.write({
                    "observation": {
                        "sample_id": "carla_%06d" % i,
                        "frame_index": i,
                        "timestamp": round(i * fixed_delta_seconds, 4),
                        "camera_front": _metadata_path(f["front"]),
                        "camera_front_left": _metadata_path(f["fl"]),
                        "camera_front_right": _metadata_path(f["fr"]),
                        "camera_front_t1": _metadata_path(hist[0]["front"]),
                        "camera_front_left_t1": _metadata_path(hist[0]["fl"]),
                        "camera_front_right_t1": _metadata_path(hist[0]["fr"]),
                        "camera_front_t2": _metadata_path(hist[1]["front"]),
                        "camera_front_left_t2": _metadata_path(hist[1]["fl"]),
                        "camera_front_right_t2": _metadata_path(hist[1]["fr"]),
                        "camera_front_t3": _metadata_path(hist[2]["front"]),
                        "camera_front_left_t3": _metadata_path(hist[2]["fl"]),
                        "camera_front_right_t3": _metadata_path(hist[2]["fr"]),
                        "route_command": f["command"],
                        "ego_speed_mps": round(f["speed"], 4),
                        "ego_accel_mps2": round(f["accel"], 4),
                        "ego_heading_rad": round(f["yaw_rad"], 5),
                    },
                    "target": {
                        "future_waypoints_ego": future_wps,
                        "steer": round(f["steer"], 4),
                        "throttle": round(f["throttle"], 4),
                        "brake": round(f["brake"], 4),
                    },
                })
                written += 1

        print("CARLA_COLLECTION_OK")
        print("metadata=%s" % metadata_path)
        print("frames_raw=%d  frames_valid=%d" % (frame_count, written))
        return metadata_path

    finally:
        for q in (front_q, fl_q, fr_q):
            _drain_queue(q)
        carla_client.cleanup()
        time.sleep(0.5)


# ─────────────────────────── CLI ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Collect AutoVLA-aligned CARLA dataset.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--seconds", type=float, default=None)
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--image-width", type=int, default=None)
    parser.add_argument("--image-height", type=int, default=None)
    parser.add_argument("--target-speed-mps", type=float, default=None)
    parser.add_argument("--route-length", type=int, default=None)
    parser.add_argument("--town", type=str, default=None)
    parser.add_argument("--weather", type=str, default=None)
    parser.add_argument("--spawn-seed", type=int, default=None)
    args = parser.parse_args()

    config = _load_config(args.config)
    _apply_cli_overrides(config, args)
    metadata_path = collect(config, output_root=args.output_root)
    print(json.dumps({"metadata_path": str(metadata_path)}, sort_keys=True))


def _apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    sim_cfg = config.setdefault("simulation", {})
    collect_cfg = config.setdefault("collection", {})
    if args.seconds is not None:
        collect_cfg["seconds"] = args.seconds
    if args.fps is not None:
        collect_cfg["fps"] = args.fps
    if args.image_width is not None:
        collect_cfg["image_width"] = args.image_width
    if args.image_height is not None:
        collect_cfg["image_height"] = args.image_height
    if args.target_speed_mps is not None:
        collect_cfg["target_speed_mps"] = args.target_speed_mps
    if args.route_length is not None:
        collect_cfg["route_length"] = args.route_length
    if args.town is not None:
        sim_cfg["town"] = args.town
    if args.weather is not None:
        sim_cfg["weather"] = args.weather
    if args.spawn_seed is not None:
        random.seed(args.spawn_seed)


if __name__ == "__main__":
    main()
