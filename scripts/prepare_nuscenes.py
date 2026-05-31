from __future__ import annotations

import argparse
import json
import math
import tarfile
from pathlib import Path
from typing import Any


def main() -> None:
    args = parse_args()
    converter = NuScenesMiniConverter(
        input_tar=args.input_tar,
        output_root=args.output_root,
        max_samples=args.max_samples,
        future_steps=args.future_steps,
        sample_stride=args.sample_stride,
    )
    summary = converter.convert()
    print("NUSCENES_CONVERT_OK")
    print(json.dumps(summary, sort_keys=True))


class NuScenesMiniConverter:
    def __init__(
        self,
        input_tar: Path,
        output_root: Path,
        max_samples: int,
        future_steps: int,
        sample_stride: int,
    ) -> None:
        self.input_tar = input_tar
        self.output_root = output_root
        self.max_samples = max_samples
        self.future_steps = future_steps
        self.sample_stride = sample_stride

    def convert(self) -> dict[str, Any]:
        if not self.input_tar.exists():
            raise FileNotFoundError(f"nuScenes mini archive not found: {self.input_tar}")
        if self.max_samples <= 0:
            raise ValueError("--max-samples must be positive")
        if self.future_steps <= 0:
            raise ValueError("--future-steps must be positive")
        if self.sample_stride <= 0:
            raise ValueError("--sample-stride must be positive")

        images_dir = self.output_root / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(self.input_tar, "r:gz") as archive:
            samples = _load_json(archive, "v1.0-mini/sample.json")
            sample_data = _load_json(archive, "v1.0-mini/sample_data.json")
            ego_poses = _load_json(archive, "v1.0-mini/ego_pose.json")
            calibrated_sensors = _load_json(archive, "v1.0-mini/calibrated_sensor.json")
            sensors = _load_json(archive, "v1.0-mini/sensor.json")
            scenes = _load_json(archive, "v1.0-mini/scene.json")

            records = self._build_records(
                archive=archive,
                samples=samples,
                sample_data=sample_data,
                ego_poses=ego_poses,
                calibrated_sensors=calibrated_sensors,
                sensors=sensors,
                scenes=scenes,
                images_dir=images_dir,
            )

        metadata_path = self.output_root / "metadata.jsonl"
        with metadata_path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, sort_keys=True) + "\n")

        summary = {
            "source": "nuscenes-mini",
            "input_tar": str(self.input_tar),
            "metadata_path": str(metadata_path),
            "output_root": str(self.output_root),
            "sample_count": len(records),
            "future_steps": self.future_steps,
            "sample_stride": self.sample_stride,
            "limit": "mini subset only; full conversion deferred until Mac resource envelope justifies 5090",
        }
        (self.output_root / "conversion_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return summary

    def _build_records(
        self,
        archive: tarfile.TarFile,
        samples: list[dict[str, Any]],
        sample_data: list[dict[str, Any]],
        ego_poses: list[dict[str, Any]],
        calibrated_sensors: list[dict[str, Any]],
        sensors: list[dict[str, Any]],
        scenes: list[dict[str, Any]],
        images_dir: Path,
    ) -> list[dict[str, Any]]:
        sample_by_token = {sample["token"]: sample for sample in samples}
        pose_by_token = {pose["token"]: pose for pose in ego_poses}
        scene_by_token = {scene["token"]: scene for scene in scenes}
        sensor_by_token = {sensor["token"]: sensor for sensor in sensors}
        calibrated_by_token = {sensor["token"]: sensor for sensor in calibrated_sensors}

        front_data_by_sample: dict[str, dict[str, Any]] = {}
        for item in sample_data:
            calibrated = calibrated_by_token[item["calibrated_sensor_token"]]
            sensor = sensor_by_token[calibrated["sensor_token"]]
            if sensor["channel"] == "CAM_FRONT" and item.get("is_key_frame", False):
                front_data_by_sample[item["sample_token"]] = item

        ordered = sorted(samples, key=lambda sample: sample["timestamp"])
        records: list[dict[str, Any]] = []
        for sample in ordered[:: self.sample_stride]:
            if len(records) >= self.max_samples:
                break
            front_data = front_data_by_sample.get(sample["token"])
            if front_data is None:
                continue
            future = self._future_samples(sample, sample_by_token)
            if len(future) < self.future_steps:
                continue

            current_pose = pose_by_token[front_data["ego_pose_token"]]
            future_poses = [pose_by_token[front_data_by_sample[item["token"]]["ego_pose_token"]] for item in future]
            waypoints = _ego_frame_waypoints(current_pose=current_pose, future_poses=future_poses)
            speed_mps = _ego_speed_mps(current_pose=current_pose, next_pose=future_poses[0])
            route_command = _route_command(waypoints)
            reasoning = _reasoning_text(route_command=route_command, speed_mps=speed_mps)
            image_path = _extract_member(archive, front_data["filename"], images_dir)
            scene = scene_by_token.get(sample["scene_token"], {})

            records.append(
                {
                    "observation": {
                        "sample_id": f"nuscenes_{sample['token']}",
                        "timestamp": sample["timestamp"] / 1_000_000.0,
                        "camera_front": str(image_path.relative_to(self.output_root)),
                        "route_command": route_command,
                        "ego_speed_mps": speed_mps,
                    },
                    "target": {
                        "future_waypoints_ego": waypoints,
                        "steer": None,
                        "throttle": None,
                        "brake": None,
                        "reasoning": reasoning,
                    },
                    "source": {
                        "dataset": "nuscenes-mini",
                        "scene_name": scene.get("name"),
                        "sample_token": sample["token"],
                        "image_filename": front_data["filename"],
                    },
                }
            )
        if not records:
            raise RuntimeError("No convertible CAM_FRONT records found in nuScenes mini archive")
        return records

    def _future_samples(self, sample: dict[str, Any], sample_by_token: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        token = sample.get("next", "")
        while token and len(result) < self.future_steps:
            next_sample = sample_by_token[token]
            result.append(next_sample)
            token = next_sample.get("next", "")
        return result


def _load_json(archive: tarfile.TarFile, member_name: str) -> list[dict[str, Any]]:
    member = archive.extractfile(member_name)
    if member is None:
        raise FileNotFoundError(f"{member_name} not found in archive")
    return json.loads(member.read().decode("utf-8"))


def _extract_member(archive: tarfile.TarFile, member_name: str, output_dir: Path) -> Path:
    source = archive.extractfile(member_name)
    if source is None:
        raise FileNotFoundError(f"{member_name} not found in archive")
    output_path = output_dir / Path(member_name).name
    if not output_path.exists():
        output_path.write_bytes(source.read())
    return output_path


def _ego_frame_waypoints(current_pose: dict[str, Any], future_poses: list[dict[str, Any]]) -> list[list[float]]:
    cx, cy = current_pose["translation"][:2]
    yaw = _yaw_from_quaternion(current_pose["rotation"])
    cos_yaw = math.cos(-yaw)
    sin_yaw = math.sin(-yaw)
    waypoints = []
    for pose in future_poses:
        dx = float(pose["translation"][0]) - float(cx)
        dy = float(pose["translation"][1]) - float(cy)
        ego_x = cos_yaw * dx - sin_yaw * dy
        ego_y = sin_yaw * dx + cos_yaw * dy
        waypoints.append([round(ego_x, 4), round(ego_y, 4)])
    return waypoints


def _ego_speed_mps(current_pose: dict[str, Any], next_pose: dict[str, Any]) -> float:
    dt = (float(next_pose["timestamp"]) - float(current_pose["timestamp"])) / 1_000_000.0
    if dt <= 0:
        return 0.0
    dx = float(next_pose["translation"][0]) - float(current_pose["translation"][0])
    dy = float(next_pose["translation"][1]) - float(current_pose["translation"][1])
    return round(math.hypot(dx, dy) / dt, 4)


def _yaw_from_quaternion(rotation: list[float]) -> float:
    w, x, y, z = [float(value) for value in rotation]
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def _route_command(waypoints: list[list[float]]) -> str:
    lateral = waypoints[-1][1]
    if lateral > 1.5:
        return "turn_left"
    if lateral < -1.5:
        return "turn_right"
    return "lane_follow"


def _reasoning_text(route_command: str, speed_mps: float) -> str:
    if speed_mps < 0.5:
        return "slow_or_stop"
    if route_command == "turn_left":
        return "turn_left"
    if route_command == "turn_right":
        return "turn_right"
    return "keep_lane"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert nuScenes mini into vla_drive DrivingSample JSONL.")
    parser.add_argument("--input-tar", type=Path, default=Path("data/offline/datasets/nuscenes/v1.0-mini.tgz"))
    parser.add_argument("--output-root", type=Path, default=Path("/private/tmp/vla_drive_nuscenes_mini"))
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--future-steps", type=int, default=8)
    parser.add_argument("--sample-stride", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    main()
