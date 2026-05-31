from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import time


def _add_carla_paths() -> None:
    carla_root = os.environ.get("CARLA_ROOT_WIN", r"C:\CARLA")
    egg = os.path.join(
        carla_root,
        "PythonAPI",
        "carla",
        "dist",
        "carla-0.9.15-py3.7-win-amd64.egg",
    )
    agents = os.path.join(carla_root, "PythonAPI", "carla")
    for path in (egg, agents):
        if path not in sys.path:
            sys.path.insert(0, path)


def _stats(raw_data):
    if not raw_data:
        return {"count": 0, "min": None, "max": None, "mean": None, "nonzero": 0}
    total = 0
    nonzero = 0
    min_value = 255
    max_value = 0
    for value in raw_data:
        if not isinstance(value, int):
            value = ord(value)
        total += value
        if value:
            nonzero += 1
        if value < min_value:
            min_value = value
        if value > max_value:
            max_value = value
    return {
        "count": len(raw_data),
        "min": min_value,
        "max": max_value,
        "mean": total / float(len(raw_data)),
        "nonzero": nonzero,
    }


def _spawn_vehicle(world):
    blueprints = world.get_blueprint_library()
    vehicle_bp = blueprints.find("vehicle.tesla.model3")
    for transform in world.get_map().get_spawn_points():
        vehicle = world.try_spawn_actor(vehicle_bp, transform)
        if vehicle is not None:
            return vehicle
    raise RuntimeError("Could not spawn vehicle")


def _set_if_available(blueprint, name, value):
    if blueprint.has_attribute(name):
        blueprint.set_attribute(name, str(value))


def _spawn_camera(world, vehicle, sensor_type, width, height, fps, attrs):
    import carla

    bp = world.get_blueprint_library().find(sensor_type)
    bp.set_attribute("image_size_x", str(width))
    bp.set_attribute("image_size_y", str(height))
    bp.set_attribute("sensor_tick", str(1.0 / fps))
    bp.set_attribute("fov", "90")
    for name, value in attrs.items():
        _set_if_available(bp, name, value)
    transform = carla.Transform(carla.Location(x=1.6, z=1.7), carla.Rotation(pitch=-5.0))
    return world.spawn_actor(bp, transform, attach_to=vehicle)


def _save_image(image, path, converter):
    import carla

    if converter == "cityscapes":
        image.save_to_disk(path, carla.ColorConverter.CityScapesPalette)
    elif converter == "log_depth":
        image.save_to_disk(path, carla.ColorConverter.LogarithmicDepth)
    elif converter == "depth":
        image.save_to_disk(path, carla.ColorConverter.Depth)
    else:
        image.save_to_disk(path)


def _run_one(world, vehicle, args, sensor_type, converter, attrs, label):
    import carla

    out_dir = os.path.join(args.out_dir, label)
    os.makedirs(out_dir, exist_ok=True)
    image_queue = queue.Queue()
    camera = _spawn_camera(world, vehicle, sensor_type, args.width, args.height, args.fps, attrs)
    try:
        camera.listen(image_queue.put)
        deadline = time.time() + args.warmup_seconds
        while time.time() < deadline:
            vehicle.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0))
            world.wait_for_tick(seconds=args.timeout)
        while True:
            try:
                image_queue.get_nowait()
            except queue.Empty:
                break

        image = None
        for _ in range(args.skip_frames + 1):
            world.wait_for_tick(seconds=args.timeout)
            image = image_queue.get(timeout=args.timeout)
        if image is None:
            raise RuntimeError("No image")

        image_path = os.path.join(out_dir, "frame.png")
        _save_image(image, image_path, converter)
        record = {
            "label": label,
            "sensor_type": sensor_type,
            "converter": converter,
            "attrs": attrs,
            "frame": int(image.frame),
            "width": int(image.width),
            "height": int(image.height),
            "raw_stats": _stats(image.raw_data),
            "image_path": image_path,
        }
        print(json.dumps(record, sort_keys=True))
        return record
    finally:
        camera.stop()
        camera.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--warmup-seconds", type=float, default=3.0)
    parser.add_argument("--skip-frames", type=int, default=3)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    _add_carla_paths()
    import carla

    os.makedirs(args.out_dir, exist_ok=True)
    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    world = client.get_world()
    settings = world.get_settings()
    settings.no_rendering_mode = False
    settings.synchronous_mode = False
    world.apply_settings(settings)
    world.set_weather(carla.WeatherParameters.ClearNoon)

    vehicle = _spawn_vehicle(world)
    try:
        cases = [
            (
                "rgb_default",
                "sensor.camera.rgb",
                "raw",
                {},
            ),
            (
                "rgb_no_postprocess",
                "sensor.camera.rgb",
                "raw",
                {"enable_postprocess_effects": "False", "gamma": "2.2"},
            ),
            (
                "rgb_manual_exposure",
                "sensor.camera.rgb",
                "raw",
                {
                    "enable_postprocess_effects": "True",
                    "exposure_mode": "manual",
                    "shutter_speed": "200.0",
                    "iso": "400.0",
                    "gamma": "2.2",
                },
            ),
            ("depth_log", "sensor.camera.depth", "log_depth", {}),
            ("semantic_cityscapes", "sensor.camera.semantic_segmentation", "cityscapes", {}),
        ]
        records = []
        for label, sensor_type, converter, attrs in cases:
            records.append(_run_one(world, vehicle, args, sensor_type, converter, attrs, label))
        with open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, sort_keys=True)
    finally:
        vehicle.destroy()


if __name__ == "__main__":
    main()
