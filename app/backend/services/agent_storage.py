from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from app.backend.services.repository_service import RepositoryService


class AgentStorage(Protocol):
    """Portable persistence boundary for the canonical Agent runtime."""

    def read(self, key: str, default: Any) -> Any: ...

    def write(self, key: str, payload: Any) -> None: ...

    def mark_external_event(self, event_id: str) -> bool: ...


class LocalAgentStorage:
    """Version-one JSON storage. Cloud adapters can implement the same boundary."""

    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def read(self, key: str, default: Any) -> Any:
        return self.repository.read_json(key, default)

    def write(self, key: str, payload: Any) -> None:
        self.repository.write_json(key, payload)

    def mark_external_event(self, event_id: str) -> bool:
        key = "app-data/dinkly-agent/processed-channel-events.json"
        records = self.repository.read_json(key, [])
        if any(item.get("id") == event_id for item in records):
            return False
        records.append({"id": event_id, "processed_at": datetime.now(UTC).isoformat()})
        self.repository.write_json(key, records[-5000:])
        return True


def build_agent_storage(repository: RepositoryService) -> AgentStorage:
    if repository.settings.app_mode != "cloud":
        return LocalAgentStorage(repository)
    from app.backend.services.cloud_persistence import PostgresAgentStorage, cloud_database

    return PostgresAgentStorage(cloud_database(repository.settings))
