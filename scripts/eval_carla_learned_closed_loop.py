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
from vla_drive.simulation.route_command import (
    route_command_from_road_option,
    route_command_from_yaw_delta,
)


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


def _spawn_rgb_camera(world, vehicle, width, height, fov, fps, x=2.2, y=0.0, yaw_deg=0.0):
    import carla

    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(width))
    bp.set_attribute("image_size_y", str(height))
    bp.set_attribute("fov", str(fov))
    bp.set_attribute("sensor_tick", str(1.0 / fps))
    if bp.has_attribute("enable_postprocess_effects"):
        bp.set_attribute("enable_postprocess_effects", "True")
    transform = carla.Transform(
        carla.Location(x=float(x), y=float(y), z=2.0),
        carla.Rotation(pitch=-8.0, yaw=float(yaw_deg)),
    )
    return world.spawn_actor(bp, transform, attach_to=vehicle)


def _spawn_chase_camera(world, vehicle, width, height, fov, fps, back_m, height_m, pitch_deg):
    """Third-person chase camera (behind + above, looking forward at the car).

    Used only for the HUD video — the model keeps its own front camera so its
    input matches training.
    """
    import carla

    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(width))
    bp.set_attribute("image_size_y", str(height))
    bp.set_attribute("fov", str(fov))
    bp.set_attribute("sensor_tick", str(1.0 / fps))
    if bp.has_attribute("enable_postprocess_effects"):
        bp.set_attribute("enable_postprocess_effects", "True")
    transform = carla.Transform(
        carla.Location(x=-abs(float(back_m)), y=0.0, z=abs(float(height_m))),
        carla.Rotation(pitch=float(pitch_deg), yaw=0.0),
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


def _world_xy_to_ego_delta(ego_transform, world_x, world_y, world_yaw_rad):
    ego_location = ego_transform.location
    ego_yaw = math.radians(float(ego_transform.rotation.yaw))
    dx_w = float(world_x) - float(ego_location.x)
    dy_w = float(world_y) - float(ego_location.y)
    cos_y = math.cos(ego_yaw)
    sin_y = math.sin(ego_yaw)
    dx_ego = cos_y * dx_w + sin_y * dy_w
    dy_ego = -sin_y * dx_w + cos_y * dy_w
    dh = (float(world_yaw_rad) - ego_yaw + math.pi) % (2.0 * math.pi) - math.pi
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


def _route_command_from_waypoints(route_waypoints, fallback_command, threshold_rad):
    if not route_waypoints:
        return fallback_command
    heading_delta = float(route_waypoints[-1][2])
    return route_command_from_yaw_delta(heading_delta, threshold_rad=threshold_rad)


def _plan_route_waypoints(world_map, start_location, goal_location, sampling_resolution_m, max_expansions=400000):
    """Pure-Python start→goal route over CARLA's lane graph (no numpy/networkx).

    Dijkstra over the waypoint successor graph (``waypoint.next`` plus legal lane
    changes). Returns a list of ``carla.Waypoint`` from start toward goal, or an
    empty list if no path is found within ``max_expansions``.
    """
    import heapq
    import itertools

    import carla

    resolution = max(0.5, float(sampling_resolution_m))
    start_wp = world_map.get_waypoint(start_location, project_to_road=True)
    goal_wp = world_map.get_waypoint(goal_location, project_to_road=True)
    if start_wp is None or goal_wp is None:
        return []

    def key_of(wp):
        return (wp.road_id, wp.section_id, wp.lane_id, int(round(wp.s / resolution)))

    goal_key = key_of(goal_wp)
    goal_loc = goal_wp.transform.location
    arrival = resolution * 2.0

    counter = itertools.count()
    start_key = key_of(start_wp)
    frontier = [(0.0, next(counter), start_wp)]
    came_from = {start_key: (None, start_wp)}
    best_cost = {start_key: 0.0}
    found_key = None
    expansions = 0

    while frontier and expansions < max_expansions:
        cost, _, wp = heapq.heappop(frontier)
        key = key_of(wp)
        if cost > best_cost.get(key, float("inf")):
            continue
        if key == goal_key or wp.transform.location.distance(goal_loc) <= arrival:
            found_key = key
            break
        expansions += 1

        neighbors = [(nxt, resolution) for nxt in wp.next(resolution)]
        lane_change = wp.lane_change
        if lane_change in (carla.LaneChange.Left, carla.LaneChange.Both):
            left = wp.get_left_lane()
            if left is not None and left.lane_type == carla.LaneType.Driving:
                neighbors.append((left, resolution))
        if lane_change in (carla.LaneChange.Right, carla.LaneChange.Both):
            right = wp.get_right_lane()
            if right is not None and right.lane_type == carla.LaneType.Driving:
                neighbors.append((right, resolution))

        for nxt, step in neighbors:
            nkey = key_of(nxt)
            ncost = cost + float(step)
            if ncost < best_cost.get(nkey, float("inf")):
                best_cost[nkey] = ncost
                came_from[nkey] = (key, nxt)
                heapq.heappush(frontier, (ncost, next(counter), nxt))

    if found_key is None:
        return []

    path = []
    key = found_key
    while key is not None:
        parent_key, wp = came_from[key]
        path.append(wp)
        key = parent_key
    path.reverse()
    return path


class _GlobalRoutePlan:
    """Global start→goal route used to feed route waypoints + commands.

    Holds a list of ``(carla.Waypoint, road_option)`` pairs and a cursor that
    advances to the nearest route waypoint each tick. ``road_option`` is a CARLA
    ``RoadOption`` when the route comes from CARLA's GlobalRoutePlanner, or
    ``None`` for the pure-Python fallback (commands then come from yaw delta).
    """

    def __init__(self, route, fallback_command):
        self._route = route
        self._fallback_command = fallback_command
        self._cursor = 0

    @classmethod
    def build(cls, world_map, start_location, goal_location, sampling_resolution_m, fallback_command):
        # Prefer CARLA's GlobalRoutePlanner (RoadOption-based commands); it needs
        # numpy + networkx, which may be absent in the CARLA client interpreter.
        try:
            from agents.navigation.global_route_planner import GlobalRoutePlanner

            planner = GlobalRoutePlanner(world_map, float(sampling_resolution_m))
            route = planner.trace_route(start_location, goal_location)
            if route:
                return cls(route, fallback_command)
        except Exception as exc:  # noqa: BLE001 - fall back to pure-Python planner
            print(
                json.dumps(
                    {"status": "GLOBAL_ROUTE_PLANNER_FALLBACK", "error": str(exc)},
                    sort_keys=True,
                ),
                flush=True,
            )

        path = _plan_route_waypoints(world_map, start_location, goal_location, sampling_resolution_m)
        if not path:
            raise RuntimeError("could not plan a route from start to goal")
        return cls([(wp, None) for wp in path], fallback_command)

    def __len__(self):
        return len(self._route)

    def update(self, ego_transform):
        location = ego_transform.location
        best_idx = self._cursor
        best_dist = float("inf")
        window = min(len(self._route), self._cursor + 30)
        for idx in range(self._cursor, window):
            dist = location.distance(self._route[idx][0].transform.location)
            if dist < best_dist:
                best_idx = idx
                best_dist = dist
        self._cursor = best_idx
        return best_dist

    def upcoming_waypoints_ego(self, ego_transform, count, spacing_m):
        """Resample the route polyline at a fixed arc-length spacing.

        Training built route_waypoints_ego with ``waypoint.next(spacing)`` →
        regular ~spacing_m steps. The Dijkstra route nodes are irregular, so we
        interpolate along cumulative distance to reproduce the same regular
        spacing the model was trained on (mismatched spacing makes the model
        misjudge turn distance and turn too early/late).
        """
        import bisect

        count = int(count)
        spacing = max(0.5, float(spacing_m))
        points = [self._route[i][0].transform.location for i in range(self._cursor, len(self._route))]
        if len(points) < 2:
            return []

        cumulative = [0.0]
        for p0, p1 in zip(points, points[1:]):
            cumulative.append(cumulative[-1] + p0.distance(p1))
        total = cumulative[-1]

        result = []
        distance = spacing
        while len(result) < count and distance <= total:
            seg = min(bisect.bisect_right(cumulative, distance) - 1, len(points) - 2)
            seg_len = cumulative[seg + 1] - cumulative[seg]
            t = 0.0 if seg_len <= 1e-6 else (distance - cumulative[seg]) / seg_len
            p0, p1 = points[seg], points[seg + 1]
            world_x = p0.x + t * (p1.x - p0.x)
            world_y = p0.y + t * (p1.y - p0.y)
            seg_yaw = math.atan2(p1.y - p0.y, p1.x - p0.x)
            result.append(_world_xy_to_ego_delta(ego_transform, world_x, world_y, seg_yaw))
            distance += spacing
        while result and len(result) < count:
            result.append(result[-1])
        return result

    def command(self, lookahead_m, threshold_rad=0.35):
        if self._cursor >= len(self._route):
            return self._fallback_command
        # RoadOption path (CARLA GlobalRoutePlanner): scan ahead for a turn.
        if self._route[self._cursor][1] is not None:
            distance = 0.0
            prev_location = self._route[self._cursor][0].transform.location
            for idx in range(self._cursor, len(self._route)):
                waypoint, road_option = self._route[idx]
                location = waypoint.transform.location
                distance += prev_location.distance(location)
                command = route_command_from_road_option(road_option, fallback=self._fallback_command)
                if command != "lane_follow":
                    return command
                if distance >= float(lookahead_m):
                    break
                prev_location = location
            return "lane_follow"
        # Fallback path: derive command from yaw delta over the lookahead.
        current = self._route[self._cursor][0].transform
        distance = 0.0
        prev_location = current.location
        target = current
        for idx in range(self._cursor + 1, len(self._route)):
            target = self._route[idx][0].transform
            distance += prev_location.distance(target.location)
            prev_location = target.location
            if distance >= float(lookahead_m):
                break
        delta_yaw = math.radians(float(target.rotation.yaw) - float(current.rotation.yaw))
        delta_yaw = (delta_yaw + math.pi) % (2.0 * math.pi) - math.pi
        return route_command_from_yaw_delta(delta_yaw, threshold_rad=threshold_rad)

    def completion(self):
        if len(self._route) <= 1:
            return 0.0
        return min(1.0, max(0.0, self._cursor / float(len(self._route) - 1)))

    def goal_location(self):
        return self._route[-1][0].transform.location


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


def _image_payload(image):
    return {
        "width": int(image.width),
        "height": int(image.height),
        "rgb": _image_rgb_base64(image),
    }


def _policy_request(conn, images, speed_mps, route_command, route_waypoints):
    front_image = images[0]
    request = {
        "type": "infer",
        "width": int(front_image.width),
        "height": int(front_image.height),
        "rgb": _image_rgb_base64(front_image),
        "images": [_image_payload(image) for image in images],
        "ego_speed_mps": float(speed_mps),
        "route_command": route_command,
        "route_waypoints_ego": route_waypoints,
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


def _advance_world(world, args):
    if bool(args.synchronous_mode):
        world.tick(seconds=args.timeout)
    else:
        world.wait_for_tick(seconds=args.timeout)


def _metadata_path(path):
    if os.name == "nt" and not path.drive and str(path).startswith("\\"):
        return Path("Z:" + str(path))
    return path


def _run_route(client, world, policy_conn, route_index, args):
    import carla

    actors = []
    collision_events = queue.Queue()
    image_events = {
        "front": queue.Queue(maxsize=2),
        "front_left": queue.Queue(maxsize=2),
        "front_right": queue.Queue(maxsize=2),
    }
    chase_events = queue.Queue(maxsize=2)
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

        global_plan = None
        if int(args.spawn_goal_index) >= 0:
            spawn_points = world_map.get_spawn_points()
            goal_index = int(args.spawn_goal_index) % len(spawn_points)
            goal_location = spawn_points[goal_index].location
            try:
                global_plan = _GlobalRoutePlan.build(
                    world_map,
                    vehicle.get_transform().location,
                    goal_location,
                    args.route_sampling_resolution_m,
                    args.route_command,
                )
                print(
                    json.dumps(
                        {
                            "status": "GLOBAL_ROUTE_READY",
                            "route_index": route_index,
                            "goal_spawn_index": goal_index,
                            "route_waypoints": len(global_plan),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001 - fall back to lane-follow routing
                print(
                    json.dumps({"status": "GLOBAL_ROUTE_FAILED", "error": str(exc)}, sort_keys=True),
                    flush=True,
                )
                global_plan = None

        collision_bp = world.get_blueprint_library().find("sensor.other.collision")
        collision_sensor = world.spawn_actor(collision_bp, carla.Transform(), attach_to=vehicle)
        actors.append(collision_sensor)
        collision_sensor.listen(collision_events.put)

        cameras = [
            ("front", 2.2, 0.0, 0.0),
            ("front_left", 2.0, -0.45, -55.0),
            ("front_right", 2.0, 0.45, 55.0),
        ]
        for camera_name, camera_x, camera_y, yaw_deg in cameras:
            camera = _spawn_rgb_camera(
                world,
                vehicle,
                args.camera_width,
                args.camera_height,
                args.camera_fov,
                args.fps,
                x=camera_x,
                y=camera_y,
                yaw_deg=yaw_deg,
            )
            actors.append(camera)
            event_queue = image_events[camera_name]

            def _on_image(image, target_queue=event_queue):
                while target_queue.full():
                    try:
                        target_queue.get_nowait()
                    except queue.Empty:
                        break
                target_queue.put(image)

            camera.listen(_on_image)

        def _get_model_images():
            return [
                image_events["front"].get(timeout=args.timeout),
                image_events["front_left"].get(timeout=args.timeout),
                image_events["front_right"].get(timeout=args.timeout),
            ]

        def _clear_model_images():
            for event_queue in image_events.values():
                while True:
                    try:
                        event_queue.get_nowait()
                    except queue.Empty:
                        break

        def _get_front_image():
            try:
                return image_events["front"].get(timeout=args.timeout)
            except queue.Empty:
                return None

        chase_camera = None
        if bool(args.chase_camera):
            chase_camera = _spawn_chase_camera(
                world, vehicle,
                args.chase_camera_width, args.chase_camera_height, args.camera_fov, args.fps,
                args.chase_back_m, args.chase_height_m, args.chase_pitch_deg,
            )
            actors.append(chase_camera)

            def _on_chase(image):
                while chase_events.full():
                    try:
                        chase_events.get_nowait()
                    except queue.Empty:
                        break
                chase_events.put(image)

            chase_camera.listen(_on_chase)

        def _display_image(front_image):
            # HUD 영상엔 체이스 카메라 프레임을 쓰고, 없으면 전방 프레임으로 폴백.
            if chase_camera is None:
                return front_image
            try:
                return chase_events.get_nowait()
            except queue.Empty:
                return front_image

        warmup_ticks = max(0, int(round(float(args.warmup_seconds) * float(args.fps))))
        warmup_ticks_used = 0
        warmup_control = carla.VehicleControl(
            throttle=float(args.warmup_throttle),
            steer=float(args.warmup_steer),
            brake=float(args.warmup_brake),
        )
        for warmup_idx in range(warmup_ticks):
            vehicle.apply_control(warmup_control)
            _advance_world(world, args)
            warmup_ticks_used += 1
            # warm-up 구간도 영상에 포함되도록 프레임/제어 기록을 남긴다.
            try:
                image = _get_front_image()
                if image is None:
                    raise queue.Empty
                frame_path = _save_image(_display_image(image), frames_dir / ("warmup_%04d.png" % warmup_idx))
                control_records.append(
                    {
                        "tick": warmup_idx,
                        "phase": "warmup",
                        "frame_path": frame_path,
                        "speed_mps": _speed_mps(vehicle),
                        "accel_mps2": _accel_mps2(vehicle),
                        "steer": float(warmup_control.steer),
                        "throttle": float(warmup_control.throttle),
                        "brake": float(warmup_control.brake),
                        "route_command": None,
                        "route_waypoints_used": False,
                        "reasoning": None,
                        "pred_waypoints_ego": [],
                        "route_waypoints_ego": [],
                        "head_outputs": {
                            "waypoint_head": [],
                            "reasoning_head": None,
                            "action_head": None,
                        },
                    }
                )
            except queue.Empty:
                pass
            if args.warmup_target_speed_mps > 0.0 and _speed_mps(vehicle) >= args.warmup_target_speed_mps:
                break
        _clear_model_images()
        for stale_queue in (chase_events,):
            while True:
                try:
                    stale_queue.get_nowait()
                except queue.Empty:
                    break
        post_warmup_speed_mps = _speed_mps(vehicle)
        start_location = vehicle.get_transform().location
        ticks = max(1, int(args.route_seconds * args.fps))
        reached_goal = False
        last_control = carla.VehicleControl(throttle=0.0, steer=0.0, brake=0.0)
        for tick_idx in range(ticks):
            _advance_world(world, args)
            try:
                model_images = _get_model_images()
                image = model_images[0]
                speed = _speed_mps(vehicle)
                accel = _accel_mps2(vehicle)
                ego_transform = vehicle.get_transform()
                if global_plan is not None:
                    global_plan.update(ego_transform)
                    route_waypoints = global_plan.upcoming_waypoints_ego(
                        ego_transform,
                        args.route_waypoint_count,
                        args.route_waypoint_spacing_m,
                    )
                    route_command = global_plan.command(
                        args.route_command_lookahead_m,
                        threshold_rad=args.route_command_yaw_threshold_rad,
                    )
                else:
                    route_waypoints = _route_waypoints_ego(
                        world_map,
                        ego_transform,
                        args.route_waypoint_count,
                        args.route_waypoint_spacing_m,
                    )
                    route_command = _route_command_from_waypoints(
                        route_waypoints,
                        fallback_command=args.route_command,
                        threshold_rad=args.route_command_yaw_threshold_rad,
                    )
                response = _policy_request(policy_conn, model_images, speed, route_command, route_waypoints)
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
                frame_path = _save_image(_display_image(image), frames_dir / ("tick_%04d.png" % tick_idx))
                control_records.append(
                    {
                        "tick": tick_idx,
                        "phase": "policy",
                        "frame_path": frame_path,
                        "speed_mps": speed,
                        "accel_mps2": accel,
                        "steer": float(last_control.steer),
                        "throttle": float(last_control.throttle),
                        "brake": float(last_control.brake),
                        "route_command": route_command,
                        "route_waypoints_used": bool(response.get("route_waypoints_used", False)),
                        "reasoning": reasoning,
                        "completion": response.get("completion"),
                        "action_token_ids": response.get("action_token_ids", []),
                        "policy_type": response.get("policy_type"),
                        "pred_waypoints_ego": response.get("waypoints", []),
                        "route_waypoints_ego": route_waypoints,
                        "head_outputs": {
                            "waypoint_head": response.get("waypoints", []),
                            "reasoning_head": reasoning,
                            "action_head": response.get("action_token_ids", []),
                        },
                    }
                )
            except queue.Empty:
                pass
            vehicle.apply_control(last_control)
            ego_location = vehicle.get_transform().location
            max_distance_m = max(max_distance_m, start_location.distance(ego_location))
            if global_plan is not None and ego_location.distance(global_plan.goal_location()) <= float(args.arrival_distance_m):
                reached_goal = True
                break

        collision_count = _queue_size(collision_events)
        if global_plan is not None:
            route_completion = 1.0 if reached_goal else global_plan.completion()
        else:
            route_completion = min(1.0, max_distance_m / max(1e-3, args.route_completion_distance_m))
        route = RouteEvaluation(
            route_id="route_%03d" % route_index,
            route_completion=route_completion,
            collision_count=collision_count,
        )
        record = route.to_dict()
        record["max_distance_m"] = max_distance_m
        record["reached_goal"] = reached_goal
        record["uses_global_route"] = global_plan is not None
        record["mean_policy_latency_ms"] = _mean(inference_latencies)
        record["mean_policy_roundtrip_ms"] = _mean(roundtrip_latencies)
        record["reasoning_counts"] = reasoning_counts
        record["warmup_max_seconds"] = float(args.warmup_seconds)
        record["warmup_seconds"] = float(warmup_ticks_used) / max(1e-6, float(args.fps))
        record["warmup_ticks"] = int(warmup_ticks_used)
        record["warmup_target_speed_mps"] = float(args.warmup_target_speed_mps)
        record["warmup_throttle"] = float(args.warmup_throttle)
        record["post_warmup_speed_mps"] = post_warmup_speed_mps
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
    parser.add_argument("--synchronous-mode", type=int, default=1)
    parser.add_argument("--fixed-delta-seconds", type=float, default=0.2)
    parser.add_argument("--spawn-start-index", type=int, default=0)
    parser.add_argument(
        "--spawn-goal-index",
        type=int,
        default=-1,
        help="Destination spawn-point index. When >=0, CARLA's GlobalRoutePlanner "
        "builds the start->goal route and drives route waypoints + commands from it.",
    )
    parser.add_argument("--route-sampling-resolution-m", type=float, default=2.0)
    parser.add_argument("--route-command-lookahead-m", type=float, default=12.0)
    parser.add_argument("--arrival-distance-m", type=float, default=5.0)
    parser.add_argument("--route-completion-distance-m", type=float, default=40.0)
    parser.add_argument("--route-command", default="lane_follow")
    parser.add_argument("--route-command-yaw-threshold-rad", type=float, default=0.35)
    parser.add_argument("--camera-width", type=int, default=320)
    parser.add_argument("--camera-height", type=int, default=180)
    parser.add_argument("--camera-fov", type=float, default=90.0)
    # HUD 영상용 3인칭 체이스 카메라 (모델 입력은 위 전방 카메라 유지).
    parser.add_argument("--chase-camera", type=int, default=1, help="1=체이스 뷰로 HUD 녹화, 0=전방 카메라 녹화")
    parser.add_argument("--chase-camera-width", type=int, default=640)
    parser.add_argument("--chase-camera-height", type=int, default=360)
    parser.add_argument("--chase-back-m", type=float, default=7.0)
    parser.add_argument("--chase-height-m", type=float, default=3.5)
    parser.add_argument("--chase-pitch-deg", type=float, default=-15.0)
    parser.add_argument("--warmup-seconds", type=float, default=0.0)
    parser.add_argument("--warmup-target-speed-mps", type=float, default=0.0)
    parser.add_argument("--warmup-throttle", type=float, default=0.0)
    parser.add_argument("--warmup-steer", type=float, default=0.0)
    parser.add_argument("--warmup-brake", type=float, default=0.0)
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
    # 이미 실행 중인 CARLA가 요청한 맵이면 load_world를 호출하지 않는다.
    # CrossOver에서 같은 맵을 재로드하면 맵 스트리밍이 타임아웃(fatal)으로 죽는다.
    world = client.get_world()
    requested_town = args.town if (args.town and args.town.lower() not in {"current", "none"}) else None
    if requested_town is not None:
        current_map = world.get_map().name
        current_town = current_map.rsplit("/", 1)[-1]
        if current_town.lower() == requested_town.lower():
            print(json.dumps({"status": "REUSING_WORLD", "map": current_map}, sort_keys=True), flush=True)
        else:
            print(
                json.dumps(
                    {"status": "LOADING_WORLD", "from_map": current_map, "to_town": requested_town},
                    sort_keys=True,
                ),
                flush=True,
            )
            world = client.load_world(requested_town)
    if args.weather and hasattr(carla.WeatherParameters, args.weather):
        world.set_weather(getattr(carla.WeatherParameters, args.weather))

    original_settings = world.get_settings()
    if bool(args.synchronous_mode):
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = float(args.fixed_delta_seconds)
        world.apply_settings(settings)
    try:
        with socket.create_connection((args.policy_host, args.policy_port), timeout=args.timeout) as policy_conn:
            route_records = [
                _run_route(client, world, policy_conn, route_index, args)
                for route_index in range(args.route_count)
            ]
    finally:
        if bool(args.synchronous_mode):
            world.apply_settings(original_settings)
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
        "route_command_source": "global_path_yaw_delta",
        "route_command_yaw_threshold_rad": float(args.route_command_yaw_threshold_rad),
        "synchronous_mode": bool(args.synchronous_mode),
        "fixed_delta_seconds": float(args.fixed_delta_seconds),
        "warmup": {
            "max_seconds": float(args.warmup_seconds),
            "target_speed_mps": float(args.warmup_target_speed_mps),
            "throttle": float(args.warmup_throttle),
            "steer": float(args.warmup_steer),
            "brake": float(args.warmup_brake),
        },
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
