from __future__ import annotations

from typing import Any


class CarlaVLAAgent:
    """Rule-based CARLA agent used to generate tiny smoke data."""

    def __init__(self, route_planner: Any, controller: Any) -> None:
        self.route_planner = route_planner
        self.controller = controller

    def run_step(self, vehicle: Any) -> tuple[Any, list[list[float]], str]:
        import carla

        transform = vehicle.get_transform()
        velocity = vehicle.get_velocity()
        speed_mps = (velocity.x**2 + velocity.y**2 + velocity.z**2) ** 0.5
        waypoints = self.route_planner.local_waypoints(transform)
        command = self.route_planner.next_command()
        control = self.controller.control(waypoints, speed_mps)
        return (
            carla.VehicleControl(
                steer=float(control.steer),
                throttle=float(control.throttle),
                brake=float(control.brake),
            ),
            waypoints,
            command,
        )
