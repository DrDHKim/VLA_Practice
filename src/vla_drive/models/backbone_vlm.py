from __future__ import annotations


class VLMBackbone:
    """Thin wrapper around Qwen2.5-VL/LLaVA-style models."""

    def __init__(self, model_name: str, freeze: bool = True) -> None:
        self.model_name = model_name
        self.freeze = freeze
        self.model = None
        self.processor = None

    def load(self) -> None:
        """TODO: load transformers model and processor."""
        raise NotImplementedError

    def encode(self, batch):
        """TODO: return pooled hidden state for waypoint/action heads."""
        raise NotImplementedError

