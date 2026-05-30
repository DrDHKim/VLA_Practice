from __future__ import annotations


class CarlaClient:
    """TODO: manage CARLA connection, world, weather, actors, and cleanup."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2000) -> None:
        self.host = host
        self.port = port
        self.client = None
        self.world = None

    def connect(self) -> None:
        raise NotImplementedError

