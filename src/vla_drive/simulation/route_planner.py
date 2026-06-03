from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from vla_drive.simulation.route_command import RouteCommandLookaheadMode, route_command_from_poses


@dataclass(frozen=True)
class RouteWaypoint:
    x: float
    y: float
    z: float = 0.0


class RoutePlanner:
    """Short-route helper that exposes local ego-frame waypoints."""

    def __init__(
        self,
        world: Any | None = None,
        route_length: int = 40,
        waypoint_spacing_m: float = 2.0,
        lookahead_count: int = 8,
        command_lookahead_mode: RouteCommandLookaheadMode = "meters",
        command_lookahead_meters: float = 30.0,
        command_lookahead_frames: int = 20,
        command_yaw_threshold_rad: float = 0.35,
    ) -> None:
        self.world = world
        self.route_length = int(route_length)
        self.waypoint_spacing_m = float(waypoint_spacing_m)
        self.lookahead_count = int(lookahead_count)
        self.command_lookahead_mode = command_lookahead_mode
        self.command_lookahead_meters = float(command_lookahead_meters)
        self.command_lookahead_frames = int(command_lookahead_frames)
        self.command_yaw_threshold_rad = float(command_yaw_threshold_rad)
        self._route: list[Any] = []
        self._cursor = 0

    def build_from_spawn(self, spawn_transform: Any) -> list[Any]:
        if self.world is None:
            raise RuntimeError("RoutePlanner needs a CARLA world to build map waypoints.")
        carla_map = self.world.get_map()
        current = carla_map.get_waypoint(spawn_transform.location, project_to_road=True)
        route = [current]
        for _ in range(max(0, self.route_length - 1)):
            candidates = route[-1].next(self.waypoint_spacing_m)
            if not candidates:
                break
            route.append(candidates[0])
        self._route = route
        self._cursor = 0
        return route

    def update(self, vehicle_transform: Any) -> None:
        if not self._route:
            return
        location = vehicle_transform.location
        best_idx = self._cursor
        best_dist = float("inf")
        for idx in range(self._cursor, min(len(self._route), self._cursor + 12)):
            waypoint_location = self._route[idx].transform.location
            dist = location.distance(waypoint_location)
            if dist < best_dist:
                best_idx = idx
                best_dist = dist
        self._cursor = best_idx

    def next_command(self) -> str:
        return route_command_from_poses(
            self._route,
            current_index=self._cursor,
            lookahead_mode=self.command_lookahead_mode,
            lookahead_frames=self.command_lookahead_frames,
            lookahead_meters=self.command_lookahead_meters,
            threshold_rad=self.command_yaw_threshold_rad,
        )

    def local_waypoints(self, vehicle_transform: Any, count: int | None = None) -> list[list[float]]:
        count = int(count or self.lookahead_count)
        if not self._route:
            return []
        self.update(vehicle_transform)
        waypoints = self._route[self._cursor + 1 : self._cursor + 1 + count]
        if not waypoints:
            waypoints = self._route[self._cursor : self._cursor + count]
        local_points = [
            _world_to_ego_xy(vehicle_transform, wp.transform.location.x, wp.transform.location.y)
            for wp in waypoints
        ]
        while local_points and len(local_points) < count:
            local_points.append(local_points[-1])
        return local_points

    def route_completion(self) -> float:
        if len(self._route) <= 1:
            return 0.0
        return min(1.0, max(0.0, self._cursor / float(len(self._route) - 1)))


def _world_to_ego_xy(vehicle_transform: Any, world_x: float, world_y: float) -> list[float]:
    location = vehicle_transform.location
    yaw = math.radians(vehicle_transform.rotation.yaw)
    dx = float(world_x) - float(location.x)
    dy = float(world_y) - float(location.y)
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    forward = cos_yaw * dx + sin_yaw * dy
    left = -sin_yaw * dx + cos_yaw * dy
    return [forward, left]
