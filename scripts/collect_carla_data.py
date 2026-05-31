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


def _load_config(path: Path) -> dict[str, Any]:
    try:
        import yaml

        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return _load_simple_yaml(path)


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    """Parse the small project config subset when PyYAML is unavailable in Wine."""
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
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"').strip("'")


def _cfg(config: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


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


def _spawn_rgb_camera(world: Any, vehicle: Any, width: int, height: int, fov: float, fps: float) -> Any:
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
    transform = carla.Transform(carla.Location(x=1.6, z=1.7), carla.Rotation(pitch=-5.0))
    return world.spawn_actor(bp, transform, attach_to=vehicle)


def _speed_mps(vehicle: Any) -> float:
    velocity = vehicle.get_velocity()
    return float(math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2))


def _control_dict(control: Any) -> dict[str, float]:
    return {
        "steer": float(control.steer),
        "throttle": float(control.throttle),
        "brake": float(control.brake),
    }


def _make_sample(
    sample_id: str,
    timestamp: float,
    image_path: Path,
    route_command: str,
    ego_speed_mps: float,
    future_waypoints_ego: list[list[float]],
    control: Any,
) -> dict[str, Any]:
    return {
        "observation": {
            "sample_id": sample_id,
            "timestamp": timestamp,
            "camera_front": _metadata_path(image_path),
            "route_command": route_command,
            "ego_speed_mps": ego_speed_mps,
        },
        "target": {
            "future_waypoints_ego": future_waypoints_ego,
            **_control_dict(control),
        },
    }


def collect(config: dict[str, Any], output_root: Path | None = None) -> Path:
    _add_carla_paths()
    import carla

    sim_cfg = config.get("simulation", {})
    collect_cfg = config.get("collection", {})
    data_cfg = config.get("data", {})

    out_root = _normalize_output_root(output_root or Path(str(data_cfg.get("root", "/private/tmp/vla_drive_carla/tiny"))))
    out_root = ensure_dir(out_root)
    frames_dir = ensure_dir(out_root / "images")
    metadata_path = out_root / "metadata.jsonl"

    fps = float(collect_cfg.get("fps", 10.0))
    seconds = float(collect_cfg.get("seconds", 30.0))
    warmup_seconds = float(collect_cfg.get("warmup_seconds", 2.0))
    frame_count = max(1, int(seconds * fps))
    fixed_delta_seconds = float(sim_cfg.get("fixed_delta_seconds", 1.0 / fps))

    carla_client = CarlaClient(
        host=str(sim_cfg.get("host", "127.0.0.1")),
        port=int(sim_cfg.get("port", 2000)),
        timeout_seconds=float(sim_cfg.get("timeout_seconds", 30.0)),
        town=str(sim_cfg.get("town", "Town01")),
        weather=str(sim_cfg.get("weather", "ClearNoon")),
        synchronous_mode=bool(sim_cfg.get("synchronous_mode", True)),
        fixed_delta_seconds=fixed_delta_seconds,
    )
    world = carla_client.connect()
    image_queue: queue.Queue[Any] = queue.Queue()

    try:
        vehicle = _spawn_vehicle(world, str(collect_cfg.get("vehicle_filter", "vehicle.tesla.model3")))
        carla_client.actors.append(vehicle)

        planner = RoutePlanner(
            world=world,
            route_length=int(collect_cfg.get("route_length", 60)),
            waypoint_spacing_m=float(collect_cfg.get("waypoint_spacing_m", 2.0)),
            lookahead_count=int(collect_cfg.get("future_waypoint_count", 8)),
        )
        planner.build_from_spawn(vehicle.get_transform())
        controller = PIDWaypointController(target_speed_mps=float(collect_cfg.get("target_speed_mps", 5.0)))
        agent = CarlaVLAAgent(planner, controller)

        camera = _spawn_rgb_camera(
            world,
            vehicle,
            width=int(collect_cfg.get("image_width", 640)),
            height=int(collect_cfg.get("image_height", 360)),
            fov=float(collect_cfg.get("fov", 90.0)),
            fps=fps,
        )
        carla_client.actors.append(camera)
        camera.listen(image_queue.put)

        warmup_ticks = max(1, int(warmup_seconds / fixed_delta_seconds))
        for _ in range(warmup_ticks):
            control, _, _ = agent.run_step(vehicle)
            vehicle.apply_control(control)
            carla_client.tick()
        _drain_queue(image_queue)

        with JsonlWriter(metadata_path) as writer:
            for index in range(frame_count):
                control, future_waypoints, command = agent.run_step(vehicle)
                vehicle.apply_control(control)
                frame_id = carla_client.tick()
                image = image_queue.get(timeout=float(sim_cfg.get("timeout_seconds", 30.0)))
                image_path = frames_dir / ("frame_%05d.png" % index)
                image.save_to_disk(str(image_path))
                writer.write(
                    _make_sample(
                        sample_id="carla_%06d" % index,
                        timestamp=float(frame_id) * fixed_delta_seconds,
                        image_path=image_path,
                        route_command=command,
                        ego_speed_mps=_speed_mps(vehicle),
                        future_waypoints_ego=future_waypoints,
                        control=control,
                    )
                )

        print("CARLA_COLLECTION_OK")
        print("metadata=%s" % metadata_path)
        print("frames=%d" % frame_count)
        return metadata_path
    finally:
        try:
            _drain_queue(image_queue)
        finally:
            carla_client.cleanup()
            time.sleep(0.5)


def _drain_queue(image_queue: queue.Queue[Any]) -> None:
    while True:
        try:
            image_queue.get_nowait()
        except queue.Empty:
            return


def _normalize_output_root(path: Path) -> Path:
    if os.name == "nt" and not path.drive and str(path).startswith("\\"):
        return Path("Z:" + str(path))
    return path


def _metadata_path(path: Path) -> str:
    text = str(path)
    if os.name == "nt" and text.lower().startswith("z:\\"):
        return "/" + text[3:].replace("\\", "/")
    return text.replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a tiny CARLA RGB waypoint dataset.")
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
