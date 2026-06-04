from __future__ import annotations

import argparse
import json
import os
import queue
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vla_drive.evaluation.closed_loop_metrics import RouteEvaluation, aggregate_route_evaluations


def _add_carla_paths() -> None:
    carla_root = os.environ.get("CARLA_ROOT_WIN", r"C:\CARLA")
    python_api = os.path.join(carla_root, "PythonAPI", "carla")
    egg = os.path.join(python_api, "dist", "carla-0.9.15-py3.7-win-amd64.egg")
    for path in (egg, python_api):
        if path not in sys.path:
            sys.path.insert(0, path)


def _spawn_vehicle(world, route_index: int, spawn_start_index: int):
    blueprints = world.get_blueprint_library()
    vehicle_bp = blueprints.find("vehicle.tesla.model3")
    spawn_points = world.get_map().get_spawn_points()
    if not spawn_points:
        raise RuntimeError("No spawn points in map")
    for offset in range(len(spawn_points)):
        transform = spawn_points[(spawn_start_index + route_index + offset) % len(spawn_points)]
        vehicle = world.try_spawn_actor(vehicle_bp, transform)
        if vehicle is not None:
            return vehicle
    raise RuntimeError("Could not spawn vehicle")


def _run_route(client, world, route_index: int, args) -> RouteEvaluation:
    import carla

    actors = []
    collision_events = queue.Queue()
    vehicle = None
    try:
        vehicle = _spawn_vehicle(world, route_index, args.spawn_start_index)
        actors.append(vehicle)
        collision_bp = world.get_blueprint_library().find("sensor.other.collision")
        collision_sensor = world.spawn_actor(collision_bp, carla.Transform(), attach_to=vehicle)
        actors.append(collision_sensor)
        collision_sensor.listen(collision_events.put)

        traffic_manager = client.get_trafficmanager(args.tm_port)
        traffic_manager.set_synchronous_mode(False)
        traffic_manager.set_global_distance_to_leading_vehicle(args.distance_to_leading_vehicle_m)
        if hasattr(traffic_manager, "set_desired_speed"):
            traffic_manager.set_desired_speed(vehicle, args.target_speed_mps * 3.6)
        else:
            traffic_manager.vehicle_percentage_speed_difference(vehicle, args.speed_percentage_difference)
        traffic_manager.auto_lane_change(vehicle, args.auto_lane_change)
        traffic_manager.ignore_lights_percentage(vehicle, args.ignore_lights_percentage)
        if hasattr(traffic_manager, "ignore_signs_percentage"):
            traffic_manager.ignore_signs_percentage(vehicle, args.ignore_signs_percentage)
        if hasattr(traffic_manager, "ignore_vehicles_percentage"):
            traffic_manager.ignore_vehicles_percentage(vehicle, args.ignore_vehicles_percentage)
        vehicle.set_autopilot(True, traffic_manager.get_port())

        start_location = vehicle.get_transform().location
        max_distance_m = 0.0
        ticks = max(1, int(args.route_seconds * args.fps))
        for _ in range(ticks):
            world.wait_for_tick(seconds=args.timeout)
            max_distance_m = max(max_distance_m, start_location.distance(vehicle.get_transform().location))
        collision_count = _queue_size(collision_events)
        return RouteEvaluation(
            route_id=f"route_{route_index:03d}",
            route_completion=min(1.0, max_distance_m / max(1e-3, args.route_completion_distance_m)),
            collision_count=collision_count,
        )
    finally:
        if vehicle is not None:
            try:
                vehicle.set_autopilot(False)
            except Exception:
                pass
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception:
                pass


def _queue_size(events: queue.Queue) -> int:
    count = 0
    while True:
        try:
            events.get_nowait()
            count += 1
        except queue.Empty:
            return count


def _metadata_path(path: Path) -> Path:
    if os.name == "nt" and not path.drive and str(path).startswith("\\"):
        return Path("Z:" + str(path))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tiny CARLA closed-loop route evaluation.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--town", default="Town01")
    parser.add_argument("--weather", default="ClearNoon")
    parser.add_argument("--route-count", type=int, default=5)
    parser.add_argument("--route-seconds", type=float, default=8.0)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--target-speed-mps", type=float, default=5.0)
    parser.add_argument("--tm-port", type=int, default=8000)
    parser.add_argument("--speed-percentage-difference", type=float, default=0.0)
    parser.add_argument("--auto-lane-change", action="store_true")
    parser.add_argument("--ignore-lights-percentage", type=float, default=100.0)
    parser.add_argument("--ignore-signs-percentage", type=float, default=100.0)
    parser.add_argument("--ignore-vehicles-percentage", type=float, default=100.0)
    parser.add_argument("--distance-to-leading-vehicle-m", type=float, default=3.0)
    parser.add_argument("--route-completion-distance-m", type=float, default=40.0)
    parser.add_argument("--spawn-start-index", type=int, default=0)
    parser.add_argument("--report-path", type=Path, default=Path("/Volumes/DATASET/vla_drive_carla/closed_loop_report.json"))
    args = parser.parse_args()

    _add_carla_paths()
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.load_world(args.town) if args.town else client.get_world()
    if args.weather and hasattr(carla.WeatherParameters, args.weather):
        world.set_weather(getattr(carla.WeatherParameters, args.weather))

    routes = [_run_route(client, world, idx, args) for idx in range(args.route_count)]
    report = {
        "routes": [route.to_dict() for route in routes],
        "aggregate": aggregate_route_evaluations(routes),
    }
    report_path = _metadata_path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("EVAL_CARLA_CLOSED_LOOP_OK")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
