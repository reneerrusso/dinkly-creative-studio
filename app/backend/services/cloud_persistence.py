from __future__ import annotations

import hashlib
import mimetypes
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.backend.config import Settings, settings
from app.backend.providers.object_storage import ObjectStorage
from app.backend.services.repository_service import RepositoryError


class SupabaseDataAPI:
    """Backend-only Supabase Data API client using the service role.

    The service-role key is never returned, logged, or passed to the browser.
    """

    def __init__(self, app_settings: Settings = settings, *, client: httpx.Client | None = None) -> None:
        self.settings = app_settings
        if not app_settings.supabase_url or not app_settings.supabase_service_role_key:
            raise RepositoryError("Cloud database requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        self.base_url = app_settings.supabase_url.rstrip("/")
        self.client = client or httpx.Client(timeout=20.0)

    @property
    def headers(self) -> dict[str, str]:
        key = str(self.settings.supabase_service_role_key)
        return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def select(self, table: str, *, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        response = self._request("GET", f"rest/v1/{self._table(table)}", params={"select": "*", **(params or {})})
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def upsert(
        self,
        table: str,
        records: dict[str, Any] | list[dict[str, Any]],
        *,
        on_conflict: str = "id",
    ) -> list[dict[str, Any]]:
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        response = self._request(
            "POST",
            f"rest/v1/{self._table(table)}",
            params={"on_conflict": on_conflict},
            headers=headers,
            json=records,
        )
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def update(self, table: str, changes: dict[str, Any], *, filters: dict[str, str]) -> list[dict[str, Any]]:
        response = self._request(
            "PATCH",
            f"rest/v1/{self._table(table)}",
            params=filters,
            headers={**self.headers, "Prefer": "return=representation"},
            json=changes,
        )
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def delete(self, table: str, *, filters: dict[str, str]) -> None:
        self._request("DELETE", f"rest/v1/{self._table(table)}", params=filters)

    def rpc(self, function: str, payload: dict[str, Any] | None = None) -> Any:
        response = self._request("POST", f"rest/v1/rpc/{self._table(function)}", json=payload or {})
        return response.json()

    def health(self) -> dict[str, Any]:
        started = datetime.now(UTC)
        rows = self.select("schema_migrations", params={"limit": "1"})
        return {
            "status": "healthy",
            "provider": "supabase_postgres",
            "migration": rows[0].get("version") if rows else None,
            "latency_ms": round((datetime.now(UTC) - started).total_seconds() * 1000),
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", self.headers)
        try:
            response = self.client.request(method, f"{self.base_url}/{path}", headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise RepositoryError("Supabase database request timed out") from exc
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            detail = ""
            try:
                payload = exc.response.json()
                detail = str(payload.get("code") or payload.get("message") or "")[:120]
            except (ValueError, TypeError):
                pass
            raise RepositoryError(f"Supabase database error {code}{f': {detail}' if detail else ''}") from exc
        except httpx.HTTPError as exc:
            raise RepositoryError("Supabase database is unreachable") from exc

    @staticmethod
    def _table(value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise RepositoryError("Invalid cloud database identifier")
        return value


class SupabaseDocumentStore:
    """Compatibility projection for existing JSON-backed business services."""

    def __init__(self, database: SupabaseDataAPI) -> None:
        self.database = database

    def read(self, key: str, default: Any) -> Any:
        rows = self.database.select("runtime_documents", params={"key": f"eq.{key}", "limit": "1"})
        return rows[0].get("value_json", default) if rows else default

    def exists(self, key: str) -> bool:
        return bool(self.database.select("runtime_documents", params={"key": f"eq.{key}", "select": "key", "limit": "1"}))

    def keys(self, prefix: str, *, suffix: str | None = None) -> list[str]:
        rows = self.database.select("runtime_documents", params={"key": f"like.{prefix}*", "order": "key.asc"})
        keys = [str(row.get("key")) for row in rows]
        return [key for key in keys if not suffix or key.endswith(suffix)]

    def write(self, key: str, value: Any) -> None:
        now = datetime.now(UTC).isoformat()
        self.database.upsert(
            "runtime_documents",
            {"key": key, "value_json": value, "updated_at": now},
            on_conflict="key",
        )
        self._mirror(key, value, now)

    def _mirror(self, key: str, value: Any, now: str) -> None:
        if key == "app-data/dinkly-agent/events.json" and isinstance(value, list):
            events = [
                {
                    "id": item["id"],
                    "task_id": (item.get("details") or {}).get("task_id"),
                    "generation_id": item.get("source_run_id"),
                    "kind": item.get("state") or (item.get("details") or {}).get("event_type") or "activity",
                    "level": "error" if item.get("state") == "error" else "info",
                    "message": item.get("message") or "DINKLY activity",
                    "data_json": item,
                    "created_at": item.get("timestamp") or now,
                }
                for item in value
                if isinstance(item, dict) and item.get("id")
            ]
            if events:
                self.database.upsert("agent_events", events)
        if key == "app-data/dinkly-agent/learning-checkpoint.json" and isinstance(value, dict):
            self.database.upsert(
                "learning_checkpoints",
                {
                    "id": "primary-learning-loop",
                    "checkpoint_type": "production_evidence",
                    "last_processed_at": value.get("last_checked_at"),
                    "seen_evidence_ids": value.get("seen_evidence_ids") or [],
                    "pending_evidence_ids": value.get("pending_evidence_ids") or [],
                    "updated_at": now,
                },
            )
        if key == "app-data/dinkly-agent/approvals.json" and isinstance(value, list):
            approvals = [
                item
                for item in value
                if isinstance(item, dict) and item.get("id") and item.get("item_id")
            ]
            if approvals:
                self.database.upsert("approvals", approvals)
        run_match = re.fullmatch(r"app-data/generation-engine/runs/(generation-[a-f0-9]{12})/metadata\.json", key)
        if run_match and isinstance(value, dict):
            run_id = run_match.group(1)
            prompt = value.get("prompt_record") or {}
            self.database.upsert(
                "generation_runs",
                {
                    "id": run_id,
                    "status": value.get("status", "draft"),
                    "concept_text": value.get("concept_text"),
                    "story_format": value.get("story_format"),
                    "source_channel": value.get("source_channel"),
                    "source_task_id": value.get("source_task_id"),
                    "brain_refs_used": value.get("brain_refs_used") or [],
                    "memory_refs_used": value.get("memory_refs_used") or [],
                    "prompt_template_version": value.get("prompt_template_version") or prompt.get("template_version"),
                    "character_rule_version": value.get("character_rule_version") or prompt.get("character_rule_version"),
                    "failure_rule_version": value.get("failure_rule_version") or prompt.get("failure_rule_version"),
                    "image_model": value.get("selected_model"),
                    "image_model_tier": value.get("model_selection_mode"),
                    "record_json": value,
                    "updated_at": now,
                },
            )
            candidates = []
            for candidate in value.get("candidates", []):
                if not candidate.get("id"):
                    continue
                candidates.append(
                    {
                        "id": candidate["id"],
                        "generation_id": run_id,
                        "label": candidate.get("label"),
                        "model": candidate.get("model_key"),
                        "model_tier": candidate.get("model_power_label"),
                        "qa_status": candidate.get("qa_status"),
                        "recommended": bool(candidate.get("recommended")),
                        "selected": candidate.get("id") == value.get("selected_candidate_id"),
                        "asset_id": candidate.get("asset_id"),
                        "final_asset_id": candidate.get("final_asset_id"),
                        "record_json": candidate,
                        "updated_at": now,
                    }
                )
            if candidates:
                self.database.upsert("generation_candidates", candidates)
        learning_tables = {
            "data/prompt_learnings.json": "prompt_learnings",
            "data/qa_learnings.json": "qa_learnings",
            "data/generation_learnings.json": "generation_learnings",
        }
        table = learning_tables.get(key)
        if table and isinstance(value, list):
            records = [
                {
                    "id": item.get("id") or f"learning-{uuid.uuid4().hex[:12]}",
                    "statement": item.get("statement") or item.get("summary") or "Learning",
                    "evidence_ids": item.get("evidence_ids") or [],
                    "confidence": item.get("confidence") or "low",
                    "active": item.get("active", item.get("status") != "inactive"),
                    "record_json": item,
                    "last_validated_at": item.get("last_validated_at") or item.get("updated_at") or now,
                    "updated_at": now,
                }
                for item in value
                if isinstance(item, dict)
            ]
            if records:
                self.database.upsert(table, records)
        if key == "data/user_preferences.json" and isinstance(value, list):
            preferences = [
                {
                    "id": item.get("id") or f"preference-{uuid.uuid4().hex[:12]}",
                    "topic": item.get("topic") or item.get("key") or "creative-preference",
                    "direction": item.get("direction") or "prefer",
                    "statement": item.get("statement") or item.get("summary") or "Creative preference",
                    "evidence_ids": item.get("evidence_ids") or [],
                    "confidence": item.get("confidence") or "high",
                    "active": item.get("status") not in {"inactive", "rejected"},
                    "source_id": item.get("source_id"),
                    "created_at": item.get("created_at") or now,
                    "updated_at": now,
                }
                for item in value
                if isinstance(item, dict)
            ]
            if preferences:
                self.database.upsert("creative_preferences", preferences)


class SupabaseObjectStorage(ObjectStorage):
    def __init__(self, app_settings: Settings = settings, *, client: httpx.Client | None = None) -> None:
        self.settings = app_settings
        if not app_settings.supabase_url or not app_settings.supabase_service_role_key:
            raise RepositoryError("Cloud storage requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        self.base_url = app_settings.supabase_url.rstrip("/")
        self.bucket = app_settings.supabase_storage_bucket
        self.client = client or httpx.Client(timeout=60.0)

    @property
    def headers(self) -> dict[str, str]:
        key = str(self.settings.supabase_service_role_key)
        return {"apikey": key, "Authorization": f"Bearer {key}"}

    def upload(self, storage_path: str, content: bytes, *, content_type: str | None = None) -> dict[str, Any]:
        safe_path = self._path(storage_path)
        headers = {
            **self.headers,
            "Content-Type": content_type or mimetypes.guess_type(storage_path)[0] or "application/octet-stream",
            "x-upsert": "true",
        }
        try:
            response = self.client.post(
                f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/{quote(safe_path, safe='/')}",
                headers=headers,
                content=content,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RepositoryError("Supabase Storage upload timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise RepositoryError(f"Supabase Storage upload error {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise RepositoryError("Supabase Storage is unreachable") from exc
        return {
            "bucket": self.bucket,
            "path": safe_path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "content_type": headers["Content-Type"],
        }

    def download(self, storage_path: str) -> bytes:
        safe_path = self._path(storage_path)
        try:
            response = self.client.get(
                f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/{quote(safe_path, safe='/')}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RepositoryError("Cloud asset not found") from exc
            raise RepositoryError(f"Supabase Storage download error {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise RepositoryError("Supabase Storage is unreachable") from exc

    def health(self) -> dict[str, Any]:
        try:
            response = self.client.get(
                f"{self.base_url}/storage/v1/bucket/{quote(self.bucket, safe='')}", headers=self.headers
            )
            response.raise_for_status()
            return {"status": "healthy", "provider": "supabase_storage", "bucket": self.bucket}
        except httpx.HTTPStatusError as exc:
            return {"status": "unavailable", "provider": "supabase_storage", "error": f"HTTP {exc.response.status_code}"}
        except httpx.HTTPError:
            return {"status": "unavailable", "provider": "supabase_storage", "error": "unreachable"}

    @staticmethod
    def _path(value: str) -> str:
        clean = value.strip().lstrip("/")
        if not clean or ".." in Path(clean).parts:
            raise RepositoryError("Invalid cloud asset path")
        return clean


class PostgresAgentStorage:
    """AgentStorage implementation backed by normalized Supabase Postgres tables."""

    TASKS = "app-data/dinkly-agent/tasks.json"
    CONVERSATIONS = "app-data/dinkly-agent/conversations.json"
    EVENTS = "app-data/dinkly-agent/processed-channel-events.json"
    OUTBOX = "app-data/dinkly-agent/channel-outbox.json"

    def __init__(self, database: SupabaseDataAPI) -> None:
        self.database = database
        self.documents = SupabaseDocumentStore(database)

    def read(self, key: str, default: Any) -> Any:
        if key == self.TASKS:
            return [row.get("record_json", {}) for row in self.database.select("agent_tasks", params={"order": "created_at.asc"})]
        if key == self.CONVERSATIONS:
            return [row.get("record_json", {}) for row in self.database.select("conversation_messages", params={"order": "created_at.asc"})]
        if key == self.EVENTS:
            return self.database.select("processed_channel_events", params={"order": "processed_at.asc"})
        if key == self.OUTBOX:
            return [row.get("record_json", {}) for row in self.database.select("channel_outbox", params={"order": "created_at.asc"})]
        return self.documents.read(key, default)

    def write(self, key: str, payload: Any) -> None:
        if key == self.TASKS:
            self._write_tasks(payload)
            return
        if key == self.CONVERSATIONS:
            self._write_conversations(payload)
            return
        if key == self.EVENTS:
            records = [row for row in payload if isinstance(row, dict) and row.get("id")]
            if records:
                self.database.upsert("processed_channel_events", records)
            return
        if key == self.OUTBOX:
            records = [
                {"id": row["id"], "record_json": row, "created_at": row.get("created_at")}
                for row in payload
                if isinstance(row, dict) and row.get("id")
            ]
            if records:
                self.database.upsert("channel_outbox", records)
            return
        self.documents.write(key, payload)

    def claim_next(self) -> dict[str, Any] | None:
        result = self.database.rpc("claim_next_agent_task")
        return result if isinstance(result, dict) else None

    def mark_external_event(self, event_id: str) -> bool:
        return bool(self.database.rpc("mark_processed_channel_event", {"p_id": event_id}))

    @contextmanager
    def lock(self, _key: str) -> Iterator[None]:
        # Individual writes are upserts and queue claiming is an atomic DB RPC.
        yield

    def _write_tasks(self, payload: Any) -> None:
        for task in payload if isinstance(payload, list) else []:
            if not isinstance(task, dict) or not task.get("id"):
                continue
            self.database.rpc("persist_agent_task", {"p_record": task})

    def _write_conversations(self, payload: Any) -> None:
        for message in payload if isinstance(payload, list) else []:
            if not isinstance(message, dict) or not message.get("id"):
                continue
            channel = str(message.get("channel") or "web")
            external = str(message.get("thread_id") or "web-default")
            thread_id = f"thread-{hashlib.sha256(f'{channel}:{external}'.encode()).hexdigest()[:16]}"
            self.database.upsert(
                "conversation_threads",
                {
                    "id": thread_id,
                    "channel": channel,
                    "external_thread_id": external,
                    "user_id": message.get("user_id"),
                    "last_active_at": message.get("created_at") or datetime.now(UTC).isoformat(),
                },
            )
            self.database.upsert(
                "conversation_messages",
                {
                    "id": message["id"],
                    "thread_id": thread_id,
                    "role": message.get("role", "user"),
                    "content": message.get("message") or message.get("content") or "",
                    "external_message_id": message.get("external_message_id"),
                    "linked_task_ids": message.get("linked_task_ids") or [],
                    "linked_generation_ids": message.get("linked_run_ids") or [],
                    "record_json": message,
                    "created_at": message.get("created_at") or datetime.now(UTC).isoformat(),
                },
            )


def cloud_database(app_settings: Settings = settings) -> SupabaseDataAPI:
    return SupabaseDataAPI(app_settings)


def cloud_documents(app_settings: Settings = settings) -> SupabaseDocumentStore:
    return SupabaseDocumentStore(cloud_database(app_settings))


def cloud_storage(app_settings: Settings = settings) -> SupabaseObjectStorage:
    return SupabaseObjectStorage(app_settings)
