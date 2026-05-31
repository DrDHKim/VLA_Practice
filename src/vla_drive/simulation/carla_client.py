from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CarlaClientSettings:
    host: str = "127.0.0.1"
    port: int = 2000
    timeout_seconds: float = 10.0
    town: str | None = None
    weather: str = "ClearNoon"
    synchronous_mode: bool = True
    fixed_delta_seconds: float = 0.05


class CarlaClient:
    """Small CARLA connection wrapper with actor tracking and cleanup."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 2000,
        timeout_seconds: float = 10.0,
        town: str | None = None,
        weather: str = "ClearNoon",
        synchronous_mode: bool = True,
        fixed_delta_seconds: float = 0.05,
    ) -> None:
        self.host = host
        self.port = port
        self.settings = CarlaClientSettings(
            host=host,
            port=port,
            timeout_seconds=timeout_seconds,
            town=town,
            weather=weather,
            synchronous_mode=synchronous_mode,
            fixed_delta_seconds=fixed_delta_seconds,
        )
        self.client: Any | None = None
        self.world: Any | None = None
        self.original_settings: Any | None = None
        self.actors: list[Any] = []
        self._carla: Any | None = None

    def connect(self) -> Any:
        """Connect to CARLA, optionally load a town, set weather, and sync mode."""
        import carla

        self._carla = carla
        self.client = carla.Client(self.host, int(self.port))
        self.client.set_timeout(float(self.settings.timeout_seconds))

        if self.settings.town:
            current_world = self.client.get_world()
            current_map = current_world.get_map().name  # e.g. "Carla/Maps/Town01"
            if self.settings.town in current_map:
                self.world = current_world
            else:
                self.world = self.client.load_world(self.settings.town)
        else:
            self.world = self.client.get_world()

        self.original_settings = self.world.get_settings()
        world_settings = self.world.get_settings()
        world_settings.synchronous_mode = bool(self.settings.synchronous_mode)
        world_settings.fixed_delta_seconds = (
            float(self.settings.fixed_delta_seconds) if self.settings.synchronous_mode else None
        )
        world_settings.no_rendering_mode = False
        self.world.apply_settings(world_settings)

        if self.settings.weather and hasattr(carla.WeatherParameters, self.settings.weather):
            self.world.set_weather(getattr(carla.WeatherParameters, self.settings.weather))

        return self.world

    def require_world(self) -> Any:
        if self.world is None:
            raise RuntimeError("CARLA world is not connected. Call connect() first.")
        return self.world

    def spawn_actor(self, blueprint: Any, transform: Any, attach_to: Any | None = None) -> Any:
        world = self.require_world()
        actor = world.spawn_actor(blueprint, transform, attach_to=attach_to)
        self.actors.append(actor)
        return actor

    def try_spawn_actor(self, blueprint: Any, transform: Any) -> Any | None:
        world = self.require_world()
        actor = world.try_spawn_actor(blueprint, transform)
        if actor is not None:
            self.actors.append(actor)
        return actor

    def tick(self) -> int:
        world = self.require_world()
        if self.settings.synchronous_mode:
            return int(world.tick())
        return int(world.wait_for_tick(seconds=self.settings.timeout_seconds).frame)

    def cleanup(self) -> None:
        for actor in reversed(self.actors):
            try:
                if actor.is_alive:
                    actor.destroy()
            except Exception:
                pass
        self.actors.clear()

        if self.world is not None and self.original_settings is not None:
            try:
                self.world.apply_settings(self.original_settings)
            except Exception:
                pass

    def __enter__(self) -> "CarlaClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()
