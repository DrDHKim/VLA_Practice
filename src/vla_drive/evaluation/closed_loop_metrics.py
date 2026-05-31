from __future__ import annotations

from dataclasses import dataclass, asdict


def driving_score(route_completion: float, infraction_penalty: float) -> float:
    return route_completion * infraction_penalty


@dataclass(frozen=True)
class RouteEvaluation:
    route_id: str
    route_completion: float
    collision_count: int = 0
    red_light_count: int = 0
    offroad_count: int = 0

    @property
    def infraction_penalty(self) -> float:
        penalty = 1.0
        penalty *= 0.50 ** max(0, self.collision_count)
        penalty *= 0.70 ** max(0, self.red_light_count)
        penalty *= 0.80 ** max(0, self.offroad_count)
        return penalty

    @property
    def driving_score(self) -> float:
        return driving_score(self.route_completion, self.infraction_penalty)

    @property
    def failure_reason(self) -> str | None:
        if self.collision_count:
            return "collision"
        if self.red_light_count:
            return "red_light"
        if self.offroad_count:
            return "offroad"
        if self.route_completion < 0.95:
            return "incomplete"
        return None

    def to_dict(self) -> dict:
        record = asdict(self)
        record["infraction_penalty"] = self.infraction_penalty
        record["driving_score"] = self.driving_score
        record["failure_reason"] = self.failure_reason
        return record


def aggregate_route_evaluations(routes: list[RouteEvaluation]) -> dict:
    if not routes:
        return {
            "route_count": 0,
            "mean_route_completion": 0.0,
            "mean_driving_score": 0.0,
            "total_collisions": 0,
        }
    return {
        "route_count": len(routes),
        "mean_route_completion": sum(route.route_completion for route in routes) / len(routes),
        "mean_driving_score": sum(route.driving_score for route in routes) / len(routes),
        "total_collisions": sum(route.collision_count for route in routes),
    }
