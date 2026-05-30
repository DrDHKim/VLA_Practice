from __future__ import annotations


def driving_score(route_completion: float, infraction_penalty: float) -> float:
    return route_completion * infraction_penalty

