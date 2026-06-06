"""AutoVLA-style instruction formatting.

Converts a DrivingSample into a generation-SFT example whose completion is a
short reasoning sentence followed by discrete action tokens (the trajectory).
The VLM (LoRA) is trained to *generate* this completion, unlike the regression
heads used elsewhere.

Action tokens are written as self-delimiting special tokens ``<act_i>`` so they
can be added to the LM vocabulary and parsed back at inference with a regex.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np

from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer

# Camera-major order, current frame first (matches data.collate._CAM_KEYS).
_CAM_KEYS = (
    ("camera_front", "camera_front_t1", "camera_front_t2", "camera_front_t3"),
    ("camera_front_left", "camera_front_left_t1", "camera_front_left_t2", "camera_front_left_t3"),
    ("camera_front_right", "camera_front_right_t1", "camera_front_right_t2", "camera_front_right_t3"),
)

ACTION_TOKEN_TEMPLATE = "<act_{}>"
_ACTION_TOKEN_RE = re.compile(r"<act_(\d+)>")
TRAJECTORY_MARKER = "Trajectory:"

_COMMAND_PHRASE = {
    "turn_left": "turning left at the intersection",
    "left": "turning left at the intersection",
    "turn_right": "turning right at the intersection",
    "right": "turning right at the intersection",
    "lane_follow": "following the current lane",
    "keep_lane": "following the current lane",
    "straight": "going straight",
}


def action_special_tokens(num_tokens: int) -> list[str]:
    """The ``<act_i>`` strings to register as special tokens in the LM tokenizer."""
    return [ACTION_TOKEN_TEMPLATE.format(i) for i in range(int(num_tokens))]


def encode_action_text(token_ids: Any) -> str:
    """[T] token ids → ``<act_a><act_b>...`` string."""
    return "".join(ACTION_TOKEN_TEMPLATE.format(int(t)) for t in token_ids)


def parse_action_text(text: str) -> list[int]:
    """Inverse of encode_action_text: pull ordered ``<act_i>`` ids from text."""
    return [int(m) for m in _ACTION_TOKEN_RE.findall(text)]


def build_reasoning_text(
    command: str,
    speed_mps: float,
    brake: float | None = None,
    explicit: str | None = None,
) -> str:
    """Template chain-of-thought sentence (PoC: synthesized from metadata).

    Real AutoVLA distills reasoning from a teacher VLM; this deterministic
    template is a stand-in so the generation pipeline can be validated.
    """
    if explicit:
        return str(explicit)
    command_phrase = _COMMAND_PHRASE.get(str(command).lower(), "following the current lane")
    speed = float(speed_mps)
    if speed < 0.5:
        speed_phrase = "the ego vehicle is stopped"
    elif speed < 3.0:
        speed_phrase = f"the ego vehicle is moving slowly at {speed:.1f} m/s"
    else:
        speed_phrase = f"the ego vehicle is cruising at {speed:.1f} m/s"
    intent = "slowing down" if (brake is not None and float(brake) > 0.3) else "maintaining a safe speed"
    return f"{speed_phrase.capitalize()}; {command_phrase} while {intent}."


def build_user_prompt(command: str, speed_mps: float, num_images: int) -> str:
    """Text instruction shown to the model alongside the camera image(s)."""
    view_word = "view" if num_images == 1 else "views"
    return (
        f"You are driving a car. Navigation command: {command}. "
        f"Current speed: {float(speed_mps):.1f} m/s. "
        f"Using the {num_images} camera {view_word}, briefly reason about the scene, "
        f"then output the future driving trajectory as action tokens."
    )


def current_frame_image_paths(observation: Any, frames_per_camera: int = 1) -> list[str]:
    """Camera-major image paths: 3 cameras × frames_per_camera (current first)."""
    frames_per_camera = max(1, min(int(frames_per_camera), len(_CAM_KEYS[0])))
    paths: list[str] = []
    for cam_row in _CAM_KEYS:
        for key in cam_row[:frames_per_camera]:
            value = getattr(observation, key, None)
            paths.append(str(value if value is not None else observation.camera_front))
    return paths


def build_completion(reasoning_text: str, action_token_ids: Any) -> str:
    """Assistant target text: reasoning sentence + action token sequence."""
    return f"{reasoning_text} {TRAJECTORY_MARKER} {encode_action_text(action_token_ids)}"


def build_instruction_example(
    sample: Any,
    tokenizer: TrajectoryActionTokenizer,
    frames_per_camera: int = 1,
) -> dict:
    """DrivingSample → AutoVLA SFT example.

    Returns dict with prompt/completion text, image paths, and the raw action
    token ids (for verification / debugging).
    """
    obs = sample.observation
    target = sample.target
    trajectory = np.asarray(target.future_waypoints_ego, dtype=np.float32)
    action_token_ids = tokenizer.encode(trajectory).tolist()

    reasoning_text = build_reasoning_text(
        command=obs.route_command,
        speed_mps=obs.ego_speed_mps,
        brake=target.brake,
        explicit=target.reasoning,
    )
    image_paths = current_frame_image_paths(obs, frames_per_camera=frames_per_camera)
    prompt = build_user_prompt(obs.route_command, obs.ego_speed_mps, num_images=len(image_paths))
    completion = build_completion(reasoning_text, action_token_ids)
    return {
        "sample_id": obs.sample_id,
        "image_paths": image_paths,
        "prompt": prompt,
        "completion": completion,
        "reasoning": reasoning_text,
        "action_token_ids": action_token_ids,
    }
