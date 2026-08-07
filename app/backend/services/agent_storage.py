from __future__ import annotations

from typing import Any, Protocol

from app.backend.services.repository_service import RepositoryService


class AgentStorage(Protocol):
    """Portable persistence boundary for the canonical Agent runtime."""

    def read(self, key: str, default: Any) -> Any: ...

    def write(self, key: str, payload: Any) -> None: ...


class LocalAgentStorage:
    """Version-one JSON storage. Cloud adapters can implement the same boundary."""

    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def read(self, key: str, default: Any) -> Any:
        return self.repository.read_json(key, default)

    def write(self, key: str, payload: Any) -> None:
        self.repository.write_json(key, payload)

