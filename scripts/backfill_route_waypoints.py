from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _add_carla_paths() -> None:
    carla_root = os.environ.get("CARLA_ROOT_WIN", r"C:\CARLA")
    python_api = os.path.join(carla_root, "PythonAPI", "carla")
    egg = os.path.join(python_api, "dist", "carla-0.9.15-py3.7-win-amd64.egg")
    for path in (egg, python_api):
        if path not in sys.path:
            sys.path.insert(0, path)


def _world_to_ego_delta(ego_x, ego_y, ego_yaw_rad, target_x, target_y, target_yaw_rad):
    dx_w = float(target_x) - float(ego_x)
    dy_w = float(target_y) - float(ego_y)
    cos_y = math.cos(float(ego_yaw_rad))
    sin_y = math.sin(float(ego_yaw_rad))
    dx_ego = cos_y * dx_w + sin_y * dy_w
    dy_ego = -sin_y * dx_w + cos_y * dy_w
    dh = float(target_yaw_rad) - float(ego_yaw_rad)
    dh = (dh + math.pi) % (2.0 * math.pi) - math.pi
    return [round(dx_ego, 4), round(dy_ego, 4), round(dh, 5)]


def _route_waypoints_ego(carla_map, carla_module, obs, count, spacing_m):
    ego_position = obs.get("ego_position") or {}
    ego_x = float(ego_position["x"])
    ego_y = float(ego_position["y"])
    ego_yaw_rad = float(obs.get("ego_heading_rad", 0.0))
    location = carla_module.Location(x=ego_x, y=ego_y, z=0.0)
    waypoint = carla_map.get_waypoint(location, project_to_road=True)
    route = []
    for _ in range(max(1, int(count))):
        next_waypoints = waypoint.next(float(spacing_m))
        if not next_waypoints:
            break
        waypoint = next_waypoints[0]
        route.append(
            _world_to_ego_delta(
                ego_x,
                ego_y,
                ego_yaw_rad,
                waypoint.transform.location.x,
                waypoint.transform.location.y,
                math.radians(waypoint.transform.rotation.yaw),
            )
        )
    while route and len(route) < count:
        route.append(route[-1])
    return route


def _metadata_path(path: Path) -> Path:
    if os.name == "nt" and not path.drive and str(path).startswith("\\"):
        return Path("Z:" + str(path))
    return path


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill observation.route_waypoints_ego in CARLA metadata.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--town", default="Town01")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--route-waypoint-count", type=int, default=10)
    parser.add_argument("--route-waypoint-spacing-m", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _add_carla_paths()
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.load_world(args.town) if args.town.lower() not in {"current", "none"} else client.get_world()
    carla_map = world.get_map()
    if args.town.lower() not in {"current", "none"} and args.town.lower() not in carla_map.name.lower():
        raise RuntimeError(f"CARLA map mismatch: requested town={args.town}, actual map={carla_map.name}")
    input_path = _metadata_path(args.input)
    output_path = _metadata_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = 0
    with input_path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            record = json.loads(line)
            obs = record.setdefault("observation", {})
            obs["route_waypoints_ego"] = _route_waypoints_ego(
                carla_map,
                carla,
                obs,
                count=args.route_waypoint_count,
                spacing_m=args.route_waypoint_spacing_m,
            )
            obs["route_waypoint_source"] = {
                "town": args.town,
                "map_name": carla_map.name,
                "spacing_m": float(args.route_waypoint_spacing_m),
                "count": int(args.route_waypoint_count),
            }
            dst.write(json.dumps(record, sort_keys=True) + "\n")
            rows += 1

    print("BACKFILL_ROUTE_WAYPOINTS_OK")
    print(json.dumps({"rows": rows, "input": str(args.input), "output": str(args.output), "map_name": carla_map.name}, sort_keys=True))


if __name__ == "__main__":
    main()
