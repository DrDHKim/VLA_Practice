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
from vla_drive.simulation.carla_agent import CarlaVLAAgent
from vla_drive.simulation.pid_controller import PIDWaypointController
from vla_drive.simulation.route_planner import RoutePlanner


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


def _run_route(world, route_index: int, args) -> RouteEvaluation:
    import carla

    actors = []
    collision_events = queue.Queue()
    vehicle = _spawn_vehicle(world, route_index, args.spawn_start_index)
    actors.append(vehicle)
    collision_bp = world.get_blueprint_library().find("sensor.other.collision")
    collision_sensor = world.spawn_actor(collision_bp, carla.Transform(), attach_to=vehicle)
    actors.append(collision_sensor)
    collision_sensor.listen(collision_events.put)

    planner = RoutePlanner(
        world=world,
        route_length=args.route_length,
        waypoint_spacing_m=args.waypoint_spacing_m,
        lookahead_count=args.future_waypoint_count,
    )
    planner.build_from_spawn(vehicle.get_transform())
    controller = PIDWaypointController(
        target_speed_mps=args.target_speed_mps,
        steer_gain=args.steer_gain,
        speed_kp=args.speed_kp,
        brake_kp=args.brake_kp,
    )
    agent = CarlaVLAAgent(planner, controller)

    try:
        ticks = max(1, int(args.route_seconds * args.fps))
        for _ in range(ticks):
            control, _, _ = agent.run_step(vehicle)
            vehicle.apply_control(control)
            world.wait_for_tick(seconds=args.timeout)
        planner.update(vehicle.get_transform())
        collision_count = _queue_size(collision_events)
        return RouteEvaluation(
            route_id=f"route_{route_index:03d}",
            route_completion=planner.route_completion(),
            collision_count=collision_count,
        )
    finally:
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
    parser.add_argument("--steer-gain", type=float, default=1.2)
    parser.add_argument("--speed-kp", type=float, default=0.35)
    parser.add_argument("--brake-kp", type=float, default=0.25)
    parser.add_argument("--spawn-start-index", type=int, default=0)
    parser.add_argument("--route-length", type=int, default=80)
    parser.add_argument("--waypoint-spacing-m", type=float, default=2.0)
    parser.add_argument("--future-waypoint-count", type=int, default=8)
    parser.add_argument("--report-path", type=Path, default=Path("/private/tmp/vla_drive_carla/closed_loop_report.json"))
    args = parser.parse_args()

    _add_carla_paths()
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.load_world(args.town) if args.town else client.get_world()
    if args.weather and hasattr(carla.WeatherParameters, args.weather):
        world.set_weather(getattr(carla.WeatherParameters, args.weather))

    routes = [_run_route(world, idx, args) for idx in range(args.route_count)]
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
