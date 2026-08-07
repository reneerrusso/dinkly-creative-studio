from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.backend.config import Settings
from app.backend.providers.object_storage import LocalFilesystemObjectStorage
from app.backend.services.cloud_persistence import (
    PostgresAgentStorage,
    SupabaseDataAPI,
    SupabaseObjectStorage,
)
from app.backend.services.repository_service import RepositoryError


def cloud_settings(tmp_path: Path) -> Settings:
    return Settings(
        repository_root=tmp_path,
        frontend_origin="https://studio.example.com",
        max_upload_bytes=1024,
        app_url="https://studio.example.com",
        app_mode="cloud",
        api_url="https://api.example.com",
        public_base_url="https://api.example.com",
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="test-service-role",
    )


def test_supabase_data_api_upsert_and_health_without_exposing_key(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"version": "0001_dinkly_cloud"}])
        return httpx.Response(201, json=json.loads(request.content))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    database = SupabaseDataAPI(cloud_settings(tmp_path), client=client)
    assert database.health()["migration"] == "0001_dinkly_cloud"
    database.upsert("agent_memories", {"id": "memory-1"})
    assert all("test-service-role" not in str(request.url) for request in seen)


def test_supabase_storage_upload_and_download(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"Key": "asset.png"})
        return httpx.Response(200, content=b"stored-image")

    storage = SupabaseObjectStorage(
        cloud_settings(tmp_path), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    uploaded = storage.upload("runs/asset.png", b"stored-image", content_type="image/png")
    assert uploaded["size_bytes"] == 12
    assert storage.download("runs/asset.png") == b"stored-image"


def test_local_and_cloud_storage_share_contract(tmp_path: Path) -> None:
    storage = LocalFilesystemObjectStorage(tmp_path / "assets")
    record = storage.upload("approved/comic.png", b"image")
    assert record["bucket"] == "local"
    assert storage.download("approved/comic.png") == b"image"
    with pytest.raises(RepositoryError):
        storage.download("../secret")


def test_postgres_agent_queue_uses_atomic_task_rpcs() -> None:
    class Database:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict | None]] = []
            self.processed_events: set[str] = set()

        def rpc(self, function: str, payload: dict | None = None) -> dict | bool:
            self.calls.append((function, payload))
            if function == "claim_next_agent_task":
                return {"id": "task-1", "status": "running"}
            if function == "mark_processed_channel_event":
                event_id = str((payload or {}).get("p_id"))
                inserted = event_id not in self.processed_events
                self.processed_events.add(event_id)
                return inserted
            return payload or {}

    database = Database()
    storage = PostgresAgentStorage(database)  # type: ignore[arg-type]
    storage.write(storage.TASKS, [{"id": "task-1", "status": "queued"}])
    claimed = storage.claim_next()
    assert database.calls[0][0] == "persist_agent_task"
    assert database.calls[1][0] == "claim_next_agent_task"
    assert claimed == {"id": "task-1", "status": "running"}
    assert storage.mark_external_event("slack:event-1") is True
    assert storage.mark_external_event("slack:event-1") is False
    assert database.calls[-1] == ("mark_processed_channel_event", {"p_id": "slack:event-1"})
