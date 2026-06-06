from __future__ import annotations

import pytest
import torch

from vla_drive.models.backbone_vlm import DummyDrivingBackbone
from vla_drive.models.vla_policy import build_dummy_policy
from vla_drive.training.losses import waypoint_prediction_loss

VLM_MODEL_PATH = "data/offline/hf_models/Qwen2.5-VL-3B-Instruct"


def test_dummy_vla_policy_forward_loss_backward() -> None:
    policy = build_dummy_policy(hidden_dim=32, waypoint_count=8)
    batch = {
        "images": torch.zeros(2, 3, 32, 32),
        "ego_speed_mps": torch.tensor([1.0, 2.0]),
    }
    target = torch.zeros(2, 8, 3)

    output = policy(batch)
    pred = output["future_waypoints_ego"]
    assert tuple(pred.shape) == (2, 8, 3)

    loss = waypoint_prediction_loss(pred, target)
    loss.backward()
    assert loss.item() >= 0.0
    assert any(param.grad is not None for param in policy.parameters())


def test_dummy_backbone_is_route_command_conditioned() -> None:
    backbone = DummyDrivingBackbone(hidden_dim=16)
    batch = {
        "images": torch.zeros(2, 3, 32, 32),
        "ego_speed_mps": torch.tensor([3.0, 3.0]),
        "route_commands": ["lane_follow", "turn_left"],
    }

    hidden = backbone.encode(batch)

    assert hidden.shape == (2, 16)
    assert not torch.allclose(hidden[0], hidden[1])


def test_dummy_backbone_can_use_route_waypoints() -> None:
    backbone = DummyDrivingBackbone(hidden_dim=16, use_route_waypoints=True, route_waypoint_count=2)
    base_batch = {
        "images": torch.zeros(2, 3, 32, 32),
        "ego_speed_mps": torch.tensor([3.0, 3.0]),
        "route_commands": ["lane_follow", "lane_follow"],
        "route_waypoints_ego": torch.tensor(
            [
                [[2.0, 0.0, 0.0], [4.0, 0.0, 0.0]],
                [[2.0, 1.0, 0.0], [4.0, 1.0, 0.0]],
            ],
            dtype=torch.float32,
        ),
    }

    hidden = backbone.encode(base_batch)

    assert hidden.shape == (2, 16)
    assert not torch.allclose(hidden[0], hidden[1])


@pytest.mark.slow
def test_vlm_backbone_frozen_encode_shape(tmp_path) -> None:
    """Smoke test: VLMBackbone loads Qwen2.5-VL-3B and encodes one image."""
    from PIL import Image as PILImage

    from vla_drive.models.backbone_vlm import VLMBackbone

    img_path = tmp_path / "test_frame.png"
    PILImage.new("RGB", (320, 180), color=(128, 64, 32)).save(img_path)

    backbone = VLMBackbone(model_name_or_path=VLM_MODEL_PATH, freeze=True)
    backbone.load()

    batch = {
        "image_paths": [str(img_path)],
        "prompts": ["Drive with command=lane_follow at speed=5.00 m/s and predict future ego-frame waypoints."],
    }
    hidden = backbone.encode(batch)

    assert hidden.shape == (1, 2048), f"unexpected shape {hidden.shape}"
    assert hidden.dtype == torch.float32


@pytest.mark.slow
def test_vlm_policy_frozen_forward_and_backward(tmp_path) -> None:
    """Smoke test: frozen_vlm stage — only WaypointHead params get gradients."""
    from PIL import Image as PILImage

    from vla_drive.models.vla_policy import build_vlm_policy

    img_path = tmp_path / "test_frame.png"
    PILImage.new("RGB", (320, 180), color=(100, 150, 200)).save(img_path)

    policy = build_vlm_policy(model_path=VLM_MODEL_PATH, freeze=True, waypoint_count=8)

    batch = {
        "image_paths": [str(img_path)],
        "prompts": ["Drive with command=lane_follow at speed=5.00 m/s and predict future ego-frame waypoints."],
        "images": torch.zeros(1, 3, 64, 64),
        "ego_speed_mps": torch.tensor([5.0]),
    }
    target = torch.zeros(1, 8, 3)

    output = policy(batch)
    pred = output["future_waypoints_ego"]
    assert pred.shape == (1, 8, 3)

    loss = waypoint_prediction_loss(pred, target)
    loss.backward()

    head_params_with_grad = [p for p in policy.waypoint_head.parameters() if p.grad is not None]
    backbone_params_with_grad = [p for p in policy.backbone.model.parameters() if p.grad is not None]

    assert len(head_params_with_grad) > 0, "WaypointHead should have gradients"
    assert len(backbone_params_with_grad) == 0, "Frozen VLM backbone should have no gradients"
