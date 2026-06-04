#!/usr/bin/env python
from __future__ import annotations

import argparse
import base64
import json
import socket
import struct
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vla_drive.evaluation.evaluator import _build_model_for_checkpoint, _predict_waypoints, _select_device
from vla_drive.evaluation.waypoint_control import waypoint_control_from_prediction


REASONING_LABELS = ("keep_lane", "turn_left", "turn_right", "slow_or_stop")


def _load_policy(checkpoint_path: Path, device: torch.device):
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    checkpoint_args = checkpoint.get("args", {})
    stage = checkpoint_args.get("stage", "dummy_overfit")
    waypoint_count = int(checkpoint_args.get("waypoint_count", 10))
    hidden_dim = int(checkpoint_args.get("hidden_dim", 64))
    model, tokenizer = _build_model_for_checkpoint(
        stage=stage,
        checkpoint_args=checkpoint_args,
        checkpoint_path=checkpoint_path,
        hidden_dim=hidden_dim,
        waypoint_count=waypoint_count,
        device=device,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, tokenizer, stage, checkpoint_args


def _image_tensor_from_request(request: dict, image_size: int) -> torch.Tensor:
    width = int(request["width"])
    height = int(request["height"])
    raw = base64.b64decode(request["rgb"])
    image = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
    if image_size > 0:
        image = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
    return torch.from_numpy(image).permute(2, 0, 1).contiguous().float() / 255.0


def _infer(request: dict, state: dict) -> dict:
    started = time.perf_counter()
    device = state["device"]
    image = _image_tensor_from_request(request, int(state["image_size"])).unsqueeze(0).to(device)
    speed = torch.tensor([float(request.get("ego_speed_mps", 0.0))], dtype=torch.float32, device=device)
    route_command = str(request.get("route_command", "lane_follow"))
    batch = {
        "images": image,
        "ego_speed_mps": speed,
        "route_commands": [route_command],
        "prompts": [
            "Drive with command=%s at speed=%.2f m/s and predict future ego-frame waypoints."
            % (route_command, float(speed.cpu().item()))
        ],
    }
    with torch.no_grad():
        waypoints = _predict_waypoints(
            state["model"],
            batch,
            stage=state["stage"],
            tokenizer=state["tokenizer"],
            device=device,
        )[0].detach().cpu().tolist()
        output = state["model"](batch)
        reasoning = None
        if "reasoning_logits" in output:
            label_id = int(output["reasoning_logits"].argmax(dim=-1).detach().cpu().item())
            if 0 <= label_id < len(REASONING_LABELS):
                reasoning = REASONING_LABELS[label_id]

    control = waypoint_control_from_prediction(
        waypoints=waypoints,
        current_speed_mps=float(request.get("ego_speed_mps", 0.0)),
        target_speed_mps=float(state["target_speed_mps"]),
        horizon_seconds=float(state["horizon_seconds"]),
        lookahead_min_m=float(state["lookahead_min_m"]),
        steer_gain=float(state["steer_gain"]),
        speed_gain=float(state["speed_gain"]),
        brake_gain=float(state["brake_gain"]),
    )
    return {
        "ok": True,
        "waypoints": waypoints,
        "control": control,
        "reasoning": reasoning,
        "latency_ms": (time.perf_counter() - started) * 1000.0,
    }


def _recv_json(conn: socket.socket) -> dict | None:
    header = _recv_exact(conn, 4)
    if not header:
        return None
    size = struct.unpack("!I", header)[0]
    payload = _recv_exact(conn, size)
    if payload is None:
        return None
    return json.loads(payload.decode("utf-8"))


def _send_json(conn: socket.socket, payload: dict) -> None:
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    conn.sendall(struct.pack("!I", len(encoded)) + encoded)


def _recv_exact(conn: socket.socket, size: int) -> bytes | None:
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = conn.recv(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def serve(args: argparse.Namespace) -> None:
    device = _select_device(args.device)
    model, tokenizer, stage, checkpoint_args = _load_policy(args.checkpoint_path, device)
    state = {
        "model": model,
        "tokenizer": tokenizer,
        "stage": stage,
        "checkpoint_args": checkpoint_args,
        "device": device,
        "image_size": args.image_size,
        "target_speed_mps": args.target_speed_mps,
        "horizon_seconds": args.horizon_seconds,
        "lookahead_min_m": args.lookahead_min_m,
        "steer_gain": args.steer_gain,
        "speed_gain": args.speed_gain,
        "brake_gain": args.brake_gain,
    }
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(1)
        print(
            json.dumps(
                {
                    "status": "POLICY_SERVER_READY",
                    "host": args.host,
                    "port": args.port,
                    "checkpoint": str(args.checkpoint_path),
                    "stage": stage,
                    "device": str(device),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        while True:
            conn, _ = server.accept()
            with conn:
                while True:
                    request = _recv_json(conn)
                    if request is None:
                        break
                    if request.get("type") == "shutdown":
                        _send_json(conn, {"ok": True})
                        return
                    try:
                        _send_json(conn, _infer(request, state))
                    except Exception as exc:
                        _send_json(conn, {"ok": False, "error": str(exc)})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve VLA checkpoint inference over a local TCP socket.")
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--image-size", type=int, default=64)
    parser.add_argument("--target-speed-mps", type=float, default=5.0)
    parser.add_argument("--horizon-seconds", type=float, default=5.0)
    parser.add_argument("--lookahead-min-m", type=float, default=2.0)
    parser.add_argument("--steer-gain", type=float, default=1.6)
    parser.add_argument("--speed-gain", type=float, default=0.35)
    parser.add_argument("--brake-gain", type=float, default=0.45)
    return parser.parse_args()


if __name__ == "__main__":
    serve(parse_args())
