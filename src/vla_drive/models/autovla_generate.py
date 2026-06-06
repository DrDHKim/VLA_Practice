"""AutoVLA generation/inference (step 3).

The LoRA-tuned VLM generates "<reasoning> Trajectory: <act_..>..." which is
parsed back into a trajectory:

    generated text -> parse_action_text -> TrajectoryActionTokenizer.decode -> [T, 3]

``decode_trajectory_from_text`` is pure (no VLM) and unit-testable; the runtime
helpers load the model and run generation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from vla_drive.data.autovla_format import build_user_prompt, parse_action_text
from vla_drive.models.action_tokenizer import TrajectoryActionTokenizer


def decode_trajectory_from_text(text: str, tokenizer: TrajectoryActionTokenizer) -> np.ndarray:
    """Generated completion text -> [T, 3] ego-frame waypoints.

    Returns an empty [0, 3] array if no action tokens were generated.
    """
    token_ids = parse_action_text(text)
    if not token_ids:
        return np.zeros((0, 3), dtype=np.float32)
    return tokenizer.decode(np.asarray(token_ids, dtype=np.int64))


def load_autovla(
    checkpoint_dir: str | Path,
    base_model_path: str | Path,
    codebook_path: str | Path,
    device: Any,
):
    """Load base Qwen2.5-VL + LoRA adapter + processor + trajectory codebook."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(str(checkpoint_dir), use_fast=True)
    dtype = torch.float16 if str(device).startswith("cuda") else torch.float32
    model = AutoModelForImageTextToText.from_pretrained(
        str(base_model_path), dtype=dtype, device_map=None, attn_implementation="eager"
    )
    # adapter training resized embeddings to include <act_i>.
    model.resize_token_embeddings(len(processor.tokenizer))
    model = PeftModel.from_pretrained(model, str(checkpoint_dir))
    model = model.to(device)
    model.eval()
    tokenizer = TrajectoryActionTokenizer()
    tokenizer.load(codebook_path)
    return model, processor, tokenizer


def generate_trajectory(
    model: Any,
    processor: Any,
    tokenizer: TrajectoryActionTokenizer,
    images: list[Any],
    command: str,
    speed_mps: float,
    device: Any,
    max_new_tokens: int = 96,
) -> dict:
    """Run one VLM generation and decode the trajectory."""
    import torch

    from vla_drive.data.autovla_sft import build_chat_messages

    prompt = build_user_prompt(command, speed_mps, num_images=len(images))
    _, prompt_msgs = build_chat_messages(prompt, "", num_images=len(images))
    text = processor.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=images, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    new_tokens = generated[0][inputs["input_ids"].shape[1]:]
    completion = processor.tokenizer.decode(new_tokens, skip_special_tokens=False)
    waypoints = decode_trajectory_from_text(completion, tokenizer)
    return {
        "completion": completion,
        "action_token_ids": parse_action_text(completion),
        "waypoints": waypoints.tolist(),
    }
