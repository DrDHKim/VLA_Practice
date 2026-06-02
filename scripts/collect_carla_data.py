"""CARLA data collection script.

Driving stack: CARLA Traffic Manager autopilot only.

AutoVLA-aligned I/O:
- 3 cameras: front (0°), front-left (-60°), front-right (+60°)
- 4 temporal frames per camera @ 0.5 s intervals (fps=10 → every 5 frames)
- T=10 future waypoints as (Δx, Δy, Δθ) in ego frame, 0.5 s per step
- ego_accel_mps2 (scalar), ego_heading_rad (CARLA world yaw, radians)
- route_command: derived in post-process from future yaw delta
  (lookahead ~2 s). Positive Δyaw in CARLA's left-handed frame = right turn.

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

from vla_drive.simulation.carla_client import CarlaClient
from vla_drive.utils.io import JsonlWriter, ensure_dir


DEFAULT_CONFIG = REPO_ROOT / "src/vla_drive/configs/carla_rgb_waypoint.yaml"

# Temporal sampling: at fps=10, 0.5 s = 5 frames
HIST_STEP = 5    # frames between temporal history samples
FUTURE_STEP = 5  # frames between future waypoint steps
N_HISTORY = 3    # how many past temporal frames to include (t-0.5s, t-1s, t-1.5s)
N_FUTURE = 10    # planning horizon (T=10 → 5 s)

# Route command labelling: look ~2 s ahead and compare yaw delta.
CMD_LOOKAHEAD_FRAMES = 20  # 2 s @ fps=10
CMD_YAW_THRESHOLD_RAD = 0.35


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


def _build_fixed_route(world: Any, spawn_transform: Any, route_length: int, spacing_m: float) -> list[Any]:
    from vla_drive.simulation.route_planner import RoutePlanner

    planner = RoutePlanner(
        world=world,
        route_length=route_length,
        waypoint_spacing_m=spacing_m,
        lookahead_count=N_FUTURE,
    )
    route = planner.build_from_spawn(spawn_transform)
    if len(route) < 2:
        raise RuntimeError("Could not build fixed route from spawn point")
    return route

def _spawn_rgb_camera(
    world: Any,
    vehicle: Any,
    width: int,
    height: int,
    fov: float,
    fps: float,
    x: float = 2.2,
    y: float = 0.0,
    z: float = 2.0,
    yaw: float = 0.0,
    pitch: float = -8.0,
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


def _command_from_yaw_delta(dh: float) -> str:
    """CARLA yaw is left-handed; +Δyaw means the vehicle turned right."""
    if dh > CMD_YAW_THRESHOLD_RAD:
        return "turn_right"
    if dh < -CMD_YAW_THRESHOLD_RAD:
        return "turn_left"
    return "lane_follow"


# ─────────────────────────── path helpers ────────────────────────────────────

def _normalize_output_root(path: Path) -> Path:
    if os.name == "nt" and not path.drive and str(path).startswith("\\"):
        return Path("Z:" + str(path))
    return path


def _metadata_path(path: Path) -> str:
    text = str(path)
    normalized = text.replace("\\", "/")
    if os.name == "nt":
        lower = normalized.lower()
        if lower.startswith("z:/"):
            return "/" + normalized[3:]
        if lower.startswith("d:/"):
            return "/Volumes/DATASET/" + normalized[3:]
        if lower.startswith("y:/"):
            return "/Users/donghyunkim/" + normalized[3:]
    return normalized


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
    scene_id = out_root.name

    fps = float(collect_cfg.get("fps", 10.0))
    seconds = float(collect_cfg.get("seconds", 30.0))
    warmup_seconds = float(collect_cfg.get("warmup_seconds", 2.0))
    frame_count = max(1, int(seconds * fps))
    fixed_delta_seconds = float(sim_cfg.get("fixed_delta_seconds", 1.0 / fps))
    sample_interval_seconds = 1.0 / fps
    timeout = float(sim_cfg.get("timeout_seconds", 120.0))
    tm_port = int(sim_cfg.get("tm_port", 8000))
    synchronous_mode = bool(sim_cfg.get("synchronous_mode", True))
    driving_stack = _normalize_driving_stack(str(collect_cfg.get("driving_stack", "traffic_manager")))
    min_motion_speed_mps = float(collect_cfg.get("min_motion_speed_mps", 0.2))
    min_sample_speed_mps = float(collect_cfg.get("min_sample_speed_mps", 0.0))
    max_sample_brake = float(collect_cfg.get("max_sample_brake", 1.0))

    carla_client = CarlaClient(
        host=str(sim_cfg.get("host", "127.0.0.1")),
        port=int(sim_cfg.get("port", 2000)),
        timeout_seconds=timeout,
        town=str(sim_cfg.get("town", "Town01")),
        weather=str(sim_cfg.get("weather", "ClearNoon")),
        synchronous_mode=synchronous_mode,
        fixed_delta_seconds=fixed_delta_seconds,
    )
    world = carla_client.connect()
    print(
        "world settings: sync=%s fixed_delta=%s timeout=%.1f fps=%.1f frames=%d"
        % (synchronous_mode, fixed_delta_seconds if synchronous_mode else None, timeout, fps, frame_count),
        flush=True,
    )
    ticks_per_sample = 1
    actual_sample_interval_seconds = sample_interval_seconds
    if synchronous_mode:
        ticks_per_sample = max(1, int(round(sample_interval_seconds / fixed_delta_seconds)))
        actual_interval = ticks_per_sample * fixed_delta_seconds
        actual_sample_interval_seconds = actual_interval
        if abs(actual_interval - sample_interval_seconds) > 1e-6:
            print(
                "warning: sync sample interval %.4fs is approximated by %d ticks = %.4fs"
                % (sample_interval_seconds, ticks_per_sample, actual_interval),
                flush=True,
            )
        print("sync sampling: ticks_per_sample=%d" % ticks_per_sample, flush=True)

    tm = None
    actual_tm_port = tm_port
    if driving_stack == "traffic_manager":
        tm = carla_client.client.get_trafficmanager(tm_port)
        # Traffic Manager sync mode must match world sync mode. If TM is sync while
        # the world is async, autopilot can silently produce zero controls.
        tm.set_synchronous_mode(synchronous_mode)
        tm.set_global_distance_to_leading_vehicle(2.5)
        actual_tm_port = int(tm.get_port())
        print("traffic_manager port: requested=%d actual=%d" % (tm_port, actual_tm_port), flush=True)

    front_q: queue.Queue[Any] = queue.Queue()
    fl_q: queue.Queue[Any] = queue.Queue()
    fr_q: queue.Queue[Any] = queue.Queue()

    try:
        vehicle = _spawn_vehicle(world, str(collect_cfg.get("vehicle_filter", "vehicle.tesla.model3")))
        carla_client.actors.append(vehicle)

        target_speed_mps = float(collect_cfg.get("target_speed_mps", 6.0))
        target_speed_kmh = target_speed_mps * 3.6
        route_length = int(collect_cfg.get("route_length", 120))
        waypoint_spacing_m = float(collect_cfg.get("waypoint_spacing_m", 2.0))

        if driving_stack == "traffic_manager":
            speed_control = str(collect_cfg.get("speed_control", "percentage"))
            assumed_speed_limit_kmh = float(collect_cfg.get("assumed_speed_limit_kmh", 30.0))
            use_fixed_path = bool(collect_cfg.get("use_fixed_path", False))

            if speed_control == "none":
                pass
            elif speed_control == "desired":
                if hasattr(tm, "set_desired_speed"):
                    tm.set_desired_speed(vehicle, target_speed_kmh)
                else:
                    tm.vehicle_percentage_speed_difference(vehicle, 0.0)
            else:
                pct_slower = max(
                    -100.0,
                    min(95.0, (1.0 - target_speed_kmh / assumed_speed_limit_kmh) * 100.0),
                )
                tm.vehicle_percentage_speed_difference(vehicle, pct_slower)

            if use_fixed_path and hasattr(tm, "set_path"):
                import carla

                fixed_route = _build_fixed_route(world, vehicle.get_transform(), route_length, waypoint_spacing_m)
                tm.set_path(vehicle, [carla.Location(x=wp.transform.location.x, y=wp.transform.location.y, z=wp.transform.location.z) for wp in fixed_route])
            tm.auto_lane_change(vehicle, bool(collect_cfg.get("auto_lane_change", False)))
            tm.ignore_lights_percentage(vehicle, float(collect_cfg.get("ignore_lights_percentage", 100.0)))
            if hasattr(tm, "ignore_signs_percentage"):
                tm.ignore_signs_percentage(vehicle, float(collect_cfg.get("ignore_signs_percentage", 100.0)))
            if hasattr(tm, "ignore_vehicles_percentage"):
                tm.ignore_vehicles_percentage(vehicle, float(collect_cfg.get("ignore_vehicles_percentage", 100.0)))
            tm.distance_to_leading_vehicle(vehicle, float(collect_cfg.get("distance_to_leading_vehicle_m", 3.0)))
            vehicle.set_autopilot(True, actual_tm_port)
            print(
                "traffic manager autopilot ON  vehicle=%d  target_speed=%.1f km/h  tm_port=%d  fixed_path=%s"
                % (int(vehicle.id), target_speed_kmh, actual_tm_port, use_fixed_path),
                flush=True,
            )
        else:
            raise ValueError("unknown driving_stack: %s" % driving_stack)

        img_w = int(collect_cfg.get("image_width", 320))
        img_h = int(collect_cfg.get("image_height", 180))
        fov = float(collect_cfg.get("fov", 90.0))

        cam_front = _spawn_rgb_camera(world, vehicle, img_w, img_h, fov, fps,
                                      x=2.2, y=0.0, z=2.0, yaw=0.0, pitch=-8.0)
        cam_fl = _spawn_rgb_camera(world, vehicle, img_w, img_h, fov, fps,
                                   x=2.0, y=-0.45, z=2.0, yaw=-55.0, pitch=-8.0)
        cam_fr = _spawn_rgb_camera(world, vehicle, img_w, img_h, fov, fps,
                                   x=2.0, y=0.45, z=2.0, yaw=55.0, pitch=-8.0)
        for cam in (cam_front, cam_fl, cam_fr):
            carla_client.actors.append(cam)
        cam_front.listen(front_q.put)
        cam_fl.listen(fl_q.put)
        cam_fr.listen(fr_q.put)

        # ── warmup ──────────────────────────────────────────────────────────
        warmup_ticks = max(1, int(warmup_seconds / fixed_delta_seconds))
        for _ in range(warmup_ticks):
            carla_client.tick()
        for q in (front_q, fl_q, fr_q):
            _drain_queue(q)

        warmup_ctrl = vehicle.get_control()
        warmup_speed = _speed_mps(vehicle)
        print(
            "post-warmup  spd=%.2f m/s  thr=%.2f  steer=%+.2f  brake=%.2f"
            % (warmup_speed, float(warmup_ctrl.throttle),
               float(warmup_ctrl.steer), float(warmup_ctrl.brake)),
            flush=True,
        )
        if warmup_speed < min_motion_speed_mps and abs(float(warmup_ctrl.throttle)) < 1e-3:
            raise RuntimeError(
                "autopilot did not move after warmup: "
                "speed=%.3f m/s throttle=%.3f tm_sync=%s world_sync=%s"
                % (
                    warmup_speed,
                    float(warmup_ctrl.throttle),
                    synchronous_mode,
                    synchronous_mode,
                )
            )

        # ── raw frame buffer ─────────────────────────────────────────────────
        raw: list[dict[str, Any]] = []

        for idx in range(frame_count):
            frame_id = -1
            for _ in range(ticks_per_sample):
                frame_id = carla_client.tick()
            if idx == 0 or (idx + 1) % max(1, int(fps)) == 0:
                print("tick idx=%d frame_id=%d" % (idx, frame_id), flush=True)

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
            control = vehicle.get_control()
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
                "steer": float(control.steer),
                "throttle": float(control.throttle),
                "brake": float(control.brake),
            })

        if raw:
            mean_speed = sum(float(row["speed"]) for row in raw) / len(raw)
            max_speed = max(float(row["speed"]) for row in raw)
            print("speed_mean=%.3f  speed_max=%.3f" % (mean_speed, max_speed), flush=True)
            if max_speed < min_motion_speed_mps:
                raise RuntimeError(
                    "collection rejected because vehicle never moved: "
                    "speed_max=%.3f m/s" % max_speed
                )

        # ── post-process: write JSONL for valid frames ───────────────────────
        min_idx = N_HISTORY * HIST_STEP               # need history
        max_idx = len(raw) - N_FUTURE * FUTURE_STEP   # need future

        written = 0
        skipped_low_quality = 0
        with JsonlWriter(metadata_path) as writer:
            for i in range(min_idx, max_idx):
                f = raw[i]
                if float(f["speed"]) < min_sample_speed_mps or float(f["brake"]) > max_sample_brake:
                    skipped_low_quality += 1
                    continue
                hist = [raw[i - j * HIST_STEP] for j in range(1, N_HISTORY + 1)]
                future_wps = []
                for step in range(1, N_FUTURE + 1):
                    fut = raw[i + step * FUTURE_STEP]
                    dx, dy, dh = _world_to_ego_delta(
                        f["x"], f["y"], f["yaw_rad"],
                        fut["x"], fut["y"], fut["yaw_rad"],
                    )
                    future_wps.append([round(dx, 4), round(dy, 4), round(dh, 5)])

                cmd_idx = min(len(raw) - 1, i + CMD_LOOKAHEAD_FRAMES)
                _, _, cmd_dh = _world_to_ego_delta(
                    f["x"], f["y"], f["yaw_rad"],
                    raw[cmd_idx]["x"], raw[cmd_idx]["y"], raw[cmd_idx]["yaw_rad"],
                )
                route_command = _command_from_yaw_delta(cmd_dh)

                writer.write({
                    "observation": {
                        "sample_id": "%s_%06d" % (scene_id, i),
                        "frame_index": i,
                        "timestamp": round(i * actual_sample_interval_seconds, 4),
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
                        "route_command": route_command,
                        "ego_position": {
                            "x": round(f["x"], 4),
                            "y": round(f["y"], 4),
                        },
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

        print("CARLA_COLLECTION_OK", flush=True)
        print("metadata=%s" % metadata_path, flush=True)
        print(
            "frames_raw=%d  frames_valid=%d  frames_skipped_low_quality=%d"
            % (frame_count, written, skipped_low_quality),
            flush=True,
        )
        return metadata_path

    finally:
        for q in (front_q, fl_q, fr_q):
            _drain_queue(q)
        try:
            if tm is not None and synchronous_mode:
                tm.set_synchronous_mode(False)
        except Exception:
            pass
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
    parser.add_argument("--speed-control", choices=["none", "desired", "percentage"], default=None)
    parser.add_argument("--route-length", type=int, default=None)
    parser.add_argument("--town", type=str, default=None)
    parser.add_argument("--weather", type=str, default=None)
    parser.add_argument("--spawn-seed", type=int, default=None)
    parser.add_argument("--driving-stack", choices=["autopilot", "traffic_manager"], default=None)
    parser.add_argument("--synchronous-mode", choices=["true", "false"], default=None)
    parser.add_argument("--fixed-delta-seconds", type=float, default=None)
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
    if args.speed_control is not None:
        collect_cfg["speed_control"] = args.speed_control
    if args.route_length is not None:
        collect_cfg["route_length"] = args.route_length
    if args.town is not None:
        sim_cfg["town"] = args.town
    if args.weather is not None:
        sim_cfg["weather"] = args.weather
    if args.synchronous_mode is not None:
        sim_cfg["synchronous_mode"] = args.synchronous_mode == "true"
    if args.fixed_delta_seconds is not None:
        sim_cfg["fixed_delta_seconds"] = args.fixed_delta_seconds
    if args.spawn_seed is not None:
        random.seed(args.spawn_seed)
    if args.driving_stack is not None:
        collect_cfg["driving_stack"] = _normalize_driving_stack(args.driving_stack)


def _normalize_driving_stack(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "autopilot":
        return "traffic_manager"
    return normalized


if __name__ == "__main__":
    main()
