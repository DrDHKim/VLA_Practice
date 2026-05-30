from __future__ import annotations

from torch import nn

from vla_drive.models.waypoint_head import WaypointHead


class VLADrivingPolicy(nn.Module):
    def __init__(self, backbone, hidden_dim: int, waypoint_count: int) -> None:
        super().__init__()
        self.backbone = backbone
        self.waypoint_head = WaypointHead(hidden_dim, waypoint_count)

    def forward(self, batch):
        hidden = self.backbone.encode(batch)
        return {"future_waypoints_ego": self.waypoint_head(hidden)}

