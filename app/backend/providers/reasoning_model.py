from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.backend.models.content_agent import ContentFormat


class ReasoningModelProvider(ABC):
    """Replaceable reasoning boundary; DINKLY identity and persistence live elsewhere."""

    name = "unavailable"
    development_fixture = False
    real_provider = False
    estimated_batch_cost = 1.0

    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    def generate_candidates(
        self,
        content_format: ContentFormat,
        brief: dict[str, Any],
        count: int,
    ) -> list[dict[str, Any]]: ...

    def health(self) -> dict[str, Any]:
        return {"configured": self.configured, "provider": self.name, "real_provider": self.real_provider}
