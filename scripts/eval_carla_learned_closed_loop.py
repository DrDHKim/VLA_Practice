from __future__ import annotations

import argparse
import base64
import json
import math
import os
import queue
import socket
import struct
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vla_drive.evaluation.closed_loop_metrics import RouteEvaluation, aggregate_route_evaluations


def _add_carla_paths():
    carla_root = os.environ.get("CARLA_ROOT_WIN", r"C:\CARLA")
    python_api = os.path.join(carla_root, "PythonAPI", "carla")
    egg = os.path.join(python_api, "dist", "carla-0.9.15-py3.7-win-amd64.egg")
    for path in (egg, python_api):
        if path not in sys.path:
            sys.path.insert(0, path)


def _spawn_vehicle(world, route_index, spawn_start_index):
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


def _spawn_rgb_camera(world, vehicle, width, height, fov, fps):
    import carla

    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(width))
    bp.set_attribute("image_size_y", str(height))
    bp.set_attribute("fov", str(fov))
    bp.set_attribute("sensor_tick", str(1.0 / fps))
    if bp.has_attribute("enable_postprocess_effects"):
        bp.set_attribute("enable_postprocess_effects", "True")
    transform = carla.Transform(
        carla.Location(x=2.2, y=0.0, z=2.0),
        carla.Rotation(pitch=-8.0, yaw=0.0),
    )
    return world.spawn_actor(bp, transform, attach_to=vehicle)


def _speed_mps(vehicle):
    velocity = vehicle.get_velocity()
    return float(math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2))


def _accel_mps2(vehicle):
    accel = vehicle.get_acceleration()
    return float(math.sqrt(accel.x ** 2 + accel.y ** 2 + accel.z ** 2))


def _image_rgb_base64(image):
    raw = bytes(image.raw_data)
    rgb = bytearray(image.width * image.height * 3)
    j = 0
    for i in range(0, len(raw), 4):
        rgb[j] = raw[i + 2]
        rgb[j + 1] = raw[i + 1]
        rgb[j + 2] = raw[i]
        j += 3
    return base64.b64encode(bytes(rgb)).decode("ascii")


def _save_image(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save_to_disk(str(_metadata_path(path)))
    return str(path).replace("\\", "/")


def _world_to_ego_delta(ego_transform, target_transform):
    ego_location = ego_transform.location
    target_location = target_transform.location
    ego_yaw = math.radians(float(ego_transform.rotation.yaw))
    target_yaw = math.radians(float(target_transform.rotation.yaw))
    dx_w = float(target_location.x - ego_location.x)
    dy_w = float(target_location.y - ego_location.y)
    cos_y = math.cos(ego_yaw)
    sin_y = math.sin(ego_yaw)
    dx_ego = cos_y * dx_w + sin_y * dy_w
    dy_ego = -sin_y * dx_w + cos_y * dy_w
    dh = target_yaw - ego_yaw
    dh = (dh + math.pi) % (2.0 * math.pi) - math.pi
    return [dx_ego, dy_ego, dh]


def _route_waypoints_ego(world_map, ego_transform, count, spacing_m):
    route = []
    waypoint = world_map.get_waypoint(ego_transform.location)
    for _ in range(max(1, int(count))):
        next_waypoints = waypoint.next(float(spacing_m))
        if not next_waypoints:
            break
        waypoint = next_waypoints[0]
        route.append(_world_to_ego_delta(ego_transform, waypoint.transform))
    return route


def _recv_exact(conn, size):
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = conn.recv(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _send_json(conn, payload):
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    conn.sendall(struct.pack("!I", len(encoded)) + encoded)


def _recv_json(conn):
    header = _recv_exact(conn, 4)
    if not header:
        return None
    size = struct.unpack("!I", header)[0]
    payload = _recv_exact(conn, size)
    if payload is None:
        return None
    return json.loads(payload.decode("utf-8"))


def _policy_request(conn, image, speed_mps, route_command):
    request = {
        "type": "infer",
        "width": int(image.width),
        "height": int(image.height),
        "rgb": _image_rgb_base64(image),
        "ego_speed_mps": float(speed_mps),
        "route_command": route_command,
    }
    started = time.time()
    _send_json(conn, request)
    response = _recv_json(conn)
    elapsed_ms = (time.time() - started) * 1000.0
    if response is None:
        raise RuntimeError("policy inference server closed the connection")
    if not response.get("ok", False):
        raise RuntimeError("policy inference failed: %s" % response.get("error"))
    response["roundtrip_ms"] = elapsed_ms
    return response


def _queue_size(events):
    count = 0
    while True:
        try:
            events.get_nowait()
            count += 1
        except queue.Empty:
            return count


def _metadata_path(path):
    if os.name == "nt" and not path.drive and str(path).startswith("\\"):
        return Path("Z:" + str(path))
    return path


def _run_route(client, world, policy_conn, route_index, args):
    import carla

    actors = []
    collision_events = queue.Queue()
    image_events = queue.Queue(maxsize=2)
    vehicle = None
    max_distance_m = 0.0
    inference_latencies = []
    roundtrip_latencies = []
    reasoning_counts = {}
    control_records = []
    frames_dir = args.artifact_dir / ("route_%03d_frames" % route_index)
    world_map = world.get_map()
    try:
        vehicle = _spawn_vehicle(world, route_index, args.spawn_start_index)
        actors.append(vehicle)
        collision_bp = world.get_blueprint_library().find("sensor.other.collision")
        collision_sensor = world.spawn_actor(collision_bp, carla.Transform(), attach_to=vehicle)
        actors.append(collision_sensor)
        collision_sensor.listen(collision_events.put)

        camera = _spawn_rgb_camera(world, vehicle, args.camera_width, args.camera_height, args.camera_fov, args.fps)
        actors.append(camera)

        def _on_image(image):
            while image_events.full():
                try:
                    image_events.get_nowait()
                except queue.Empty:
                    break
            image_events.put(image)

        camera.listen(_on_image)
        start_location = vehicle.get_transform().location
        ticks = max(1, int(args.route_seconds * args.fps))
        last_control = carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0)
        for tick_idx in range(ticks):
            world.wait_for_tick(seconds=args.timeout)
            try:
                image = image_events.get(timeout=args.timeout)
                speed = _speed_mps(vehicle)
                accel = _accel_mps2(vehicle)
                ego_transform = vehicle.get_transform()
                route_waypoints = _route_waypoints_ego(
                    world_map,
                    ego_transform,
                    args.route_waypoint_count,
                    args.route_waypoint_spacing_m,
                )
                response = _policy_request(policy_conn, image, speed, args.route_command)
                control = response["control"]
                last_control = carla.VehicleControl(
                    throttle=float(control.get("throttle", 0.0)),
                    steer=float(control.get("steer", 0.0)),
                    brake=float(control.get("brake", 0.0)),
                )
                inference_latencies.append(float(response.get("latency_ms", 0.0)))
                roundtrip_latencies.append(float(response.get("roundtrip_ms", 0.0)))
                reasoning = response.get("reasoning")
                if reasoning:
                    reasoning_counts[reasoning] = reasoning_counts.get(reasoning, 0) + 1
                frame_path = _save_image(image, frames_dir / ("tick_%04d.png" % tick_idx))
                control_records.append(
                    {
                        "tick": tick_idx,
                        "frame_path": frame_path,
                        "speed_mps": speed,
                        "accel_mps2": accel,
                        "steer": float(last_control.steer),
                        "throttle": float(last_control.throttle),
                        "brake": float(last_control.brake),
                        "route_command": args.route_command,
                        "reasoning": reasoning,
                        "pred_waypoints_ego": response.get("waypoints", []),
                        "route_waypoints_ego": route_waypoints,
                        "head_outputs": {
                            "waypoint_head": response.get("waypoints", []),
                            "reasoning_head": reasoning,
                            "action_head": None,
                        },
                    }
                )
            except queue.Empty:
                pass
            vehicle.apply_control(last_control)
            max_distance_m = max(max_distance_m, start_location.distance(vehicle.get_transform().location))

        collision_count = _queue_size(collision_events)
        route = RouteEvaluation(
            route_id="route_%03d" % route_index,
            route_completion=min(1.0, max_distance_m / max(1e-3, args.route_completion_distance_m)),
            collision_count=collision_count,
        )
        record = route.to_dict()
        record["max_distance_m"] = max_distance_m
        record["mean_policy_latency_ms"] = _mean(inference_latencies)
        record["mean_policy_roundtrip_ms"] = _mean(roundtrip_latencies)
        record["reasoning_counts"] = reasoning_counts
        record["control_records"] = control_records
        return record
    finally:
        if vehicle is not None:
            try:
                vehicle.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0))
            except Exception:
                pass
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception:
                pass


def _mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def main():
    parser = argparse.ArgumentParser(description="Run CARLA closed-loop evaluation with a learned waypoint policy.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--town", default="Town01")
    parser.add_argument("--weather", default="ClearNoon")
    parser.add_argument("--route-count", type=int, default=1)
    parser.add_argument("--route-seconds", type=float, default=8.0)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--spawn-start-index", type=int, default=0)
    parser.add_argument("--route-completion-distance-m", type=float, default=40.0)
    parser.add_argument("--route-command", default="lane_follow")
    parser.add_argument("--camera-width", type=int, default=320)
    parser.add_argument("--camera-height", type=int, default=180)
    parser.add_argument("--camera-fov", type=float, default=90.0)
    parser.add_argument("--policy-host", default="127.0.0.1")
    parser.add_argument("--policy-port", type=int, default=8765)
    parser.add_argument("--checkpoint-path", default="")
    parser.add_argument("--report-path", type=Path, default=Path("outputs/reports/learned_closed_loop.json"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("outputs/reports/learned_closed_loop_artifacts"))
    parser.add_argument("--route-waypoint-count", type=int, default=10)
    parser.add_argument("--route-waypoint-spacing-m", type=float, default=2.0)
    args = parser.parse_args()

    _add_carla_paths()
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    if args.town and args.town.lower() not in {"current", "none"}:
        world = client.load_world(args.town)
    else:
        world = client.get_world()
    if args.weather and hasattr(carla.WeatherParameters, args.weather):
        world.set_weather(getattr(carla.WeatherParameters, args.weather))

    with socket.create_connection((args.policy_host, args.policy_port), timeout=args.timeout) as policy_conn:
        route_records = [
            _run_route(client, world, policy_conn, route_index, args)
            for route_index in range(args.route_count)
        ]
    route_evals = [
        RouteEvaluation(
            route_id=record["route_id"],
            route_completion=float(record["route_completion"]),
            collision_count=int(record["collision_count"]),
            red_light_count=int(record.get("red_light_count", 0)),
            offroad_count=int(record.get("offroad_count", 0)),
        )
        for record in route_records
    ]
    report = {
        "policy": "learned_waypoint_policy",
        "checkpoint_path": args.checkpoint_path,
        "town_arg": args.town,
        "map_name": world.get_map().name,
        "route_command": args.route_command,
        "routes": route_records,
        "aggregate": aggregate_route_evaluations(route_evals),
        "latency": {
            "mean_policy_latency_ms": _mean([r["mean_policy_latency_ms"] for r in route_records]),
            "mean_policy_roundtrip_ms": _mean([r["mean_policy_roundtrip_ms"] for r in route_records]),
        },
    }
    report_path = _metadata_path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("EVAL_CARLA_LEARNED_CLOSED_LOOP_OK")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
