from __future__ import annotations

import fcntl
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from app.backend.models.dinkly_agent import (
    AgentConversationMessage,
    AgentSourceChannel,
    AgentTask,
    AgentTaskType,
)
from app.backend.services.agent_storage import AgentStorage, LocalAgentStorage
from app.backend.services.repository_service import RepositoryError, RepositoryService

TASKS_PATH = "app-data/dinkly-agent/tasks.json"
CONVERSATIONS_PATH = "app-data/dinkly-agent/conversations.json"
PROCESSED_EVENTS_PATH = "app-data/dinkly-agent/processed-channel-events.json"
OUTBOX_PATH = "app-data/dinkly-agent/channel-outbox.json"
TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}

TASK_PRIORITY: dict[str, int] = {
    "explicit_user": 1,
    "approval": 2,
    "generation": 3,
    "scheduled": 4,
    "learning": 5,
    "maintenance": 6,
}


class AgentTaskService:
    """One persisted inbox shared by web, Slack, schedules, and learning."""

    _lock = threading.RLock()

    def __init__(self, repository: RepositoryService, storage: AgentStorage | None = None) -> None:
        self.repository = repository
        self.storage = storage or LocalAgentStorage(repository)
        self._ensure_files()

    def create_task(
        self,
        *,
        source_channel: AgentSourceChannel,
        source_thread_id: str,
        user_instruction: str,
        task_type: AgentTaskType,
        source_user_id: str | None = None,
        source_message_id: str | None = None,
        context: dict[str, Any] | None = None,
        approval_required: bool = False,
        priority: int | None = None,
        dedupe_key: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        instruction = " ".join(user_instruction.strip().split())
        if len(instruction) < 2:
            raise RepositoryError("Tell DINKLY what to work on")
        with self._storage_lock():
            tasks = self.storage.read(TASKS_PATH, [])
            if dedupe_key:
                existing = next((item for item in tasks if item.get("dedupe_key") == dedupe_key), None)
                if existing:
                    return existing, False
            now = datetime.now(UTC).isoformat()
            record = AgentTask(
                id=f"task-{uuid.uuid4().hex[:12]}",
                source_channel=source_channel,
                source_thread_id=source_thread_id,
                source_user_id=source_user_id,
                source_message_id=source_message_id,
                user_instruction=instruction,
                task_type=task_type,
                status="queued",
                priority=priority or self.priority_for(source_channel, task_type),
                context=context or {},
                approval_required=approval_required,
                created_at=now,
            ).model_dump(mode="json")
            if dedupe_key:
                record["dedupe_key"] = dedupe_key
            tasks.append(record)
            self.storage.write(TASKS_PATH, tasks)
            return record, True

    def list_tasks(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        tasks = self.storage.read(TASKS_PATH, [])
        if status:
            tasks = [item for item in tasks if item.get("status") == status]
        return sorted(tasks, key=lambda item: item.get("created_at", ""), reverse=True)[: max(1, min(limit, 500))]

    def get(self, task_id: str) -> dict[str, Any]:
        task = next((item for item in self.storage.read(TASKS_PATH, []) if item.get("id") == task_id), None)
        if not task:
            raise RepositoryError("DINKLY Agent task not found")
        return task

    def claim_next(self) -> dict[str, Any] | None:
        with self._storage_lock():
            tasks = self.storage.read(TASKS_PATH, [])
            pending = [item for item in tasks if item.get("status") == "queued"]
            if not pending:
                return None
            selected = min(pending, key=lambda item: (int(item.get("priority", 6)), item.get("created_at", "")))
            now = datetime.now(UTC).isoformat()
            selected.update(status="running", started_at=now, error=None)
            self.storage.write(TASKS_PATH, tasks)
            return selected

    def current(self, *, thread_id: str | None = None) -> dict[str, Any] | None:
        active = [
            item for item in self.storage.read(TASKS_PATH, [])
            if item.get("status") in {"running", "cancellation_requested"}
            and (thread_id is None or item.get("source_thread_id") == thread_id)
        ]
        return min(active, key=lambda item: item.get("started_at") or item.get("created_at", "")) if active else None

    def peek_next(self) -> dict[str, Any] | None:
        queued = [item for item in self.storage.read(TASKS_PATH, []) if item.get("status") == "queued"]
        return min(queued, key=lambda item: (int(item.get("priority", 6)), item.get("created_at", ""))) if queued else None

    def request_cancellation(self, task_id: str, *, reason: str = "Cancelled by user", skip: bool = False) -> tuple[dict[str, Any], str]:
        """Persist a safe, idempotent cancellation request without killing the worker."""
        with self._storage_lock():
            tasks = self.storage.read(TASKS_PATH, [])
            for task in tasks:
                if task.get("id") != task_id:
                    continue
                status = str(task.get("status"))
                if status == "cancelled":
                    return task, "Task already cancelled."
                if status in {"completed", "failed", "waiting_for_human"}:
                    return task, f"Task already {status.replace('_', ' ')}."
                now = datetime.now(UTC).isoformat()
                task.update(
                    cancellation_requested_at=task.get("cancellation_requested_at") or now,
                    cancellation_reason=task.get("cancellation_reason") or reason,
                    skip_to_next=bool(task.get("skip_to_next") or skip),
                )
                if status == "queued":
                    task.update(status="cancelled", completed_at=now, stopped_at="Queue", stopped_step="queued")
                    message = "Task cancelled."
                elif status == "cancellation_requested":
                    message = "Cancellation already requested."
                else:
                    task["status"] = "cancellation_requested"
                    message = "Cancellation requested."
                AgentTask.model_validate(task)
                self.storage.write(TASKS_PATH, tasks)
                return task, message
        raise RepositoryError("DINKLY Agent task not found")

    def mark_cancelled(
        self,
        task_id: str,
        *,
        stopped_at: str,
        result: dict[str, Any] | None = None,
        run_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        current = self.get(task_id)
        return self.update(
            task_id,
            status="cancelled",
            stopped_at=stopped_at,
            stopped_step=stopped_at,
            result={**(current.get("result") or {}), **(result or {})},
            run_ids=run_ids if run_ids is not None else current.get("run_ids", []),
            artifact_ids=artifact_ids if artifact_ids is not None else current.get("artifact_ids", []),
            completed_at=datetime.now(UTC).isoformat(),
        )

    def restart(self, task_id: str) -> dict[str, Any]:
        original = self.get(task_id)
        if original.get("status") != "cancelled":
            raise RepositoryError("Only a cancelled task can be restarted")
        restarted, _ = self.create_task(
            source_channel=original["source_channel"],
            source_thread_id=original["source_thread_id"],
            source_user_id=original.get("source_user_id"),
            user_instruction=original["user_instruction"],
            task_type=original["task_type"],
            context={**(original.get("context") or {}), "restarted_from_task_id": task_id},
            approval_required=bool(original.get("approval_required")),
            priority=int(original.get("priority", 6)),
        )
        return restarted

    def update(self, task_id: str, **changes: Any) -> dict[str, Any]:
        with self._storage_lock():
            tasks = self.storage.read(TASKS_PATH, [])
            for index, task in enumerate(tasks):
                if task.get("id") != task_id:
                    continue
                requested_status = changes.get("status")
                # Cancellation wins every race. A provider/API callback that
                # returns late may add harmless metadata, but it can never
                # resurrect a stopping or cancelled task as complete/failed.
                if (
                    task.get("status") in {"cancellation_requested", "cancelled"}
                    and requested_status
                    and requested_status not in {"cancellation_requested", "cancelled"}
                ):
                    return task
                updated = {**task, **changes}
                if updated.get("status") in TERMINAL_TASK_STATUSES and not updated.get("completed_at"):
                    updated["completed_at"] = datetime.now(UTC).isoformat()
                AgentTask.model_validate(updated)
                tasks[index] = updated
                self.storage.write(TASKS_PATH, tasks)
                return updated
        raise RepositoryError("DINKLY Agent task not found")

    def complete(
        self,
        task_id: str,
        result: dict[str, Any],
        *,
        run_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        waiting_for_human: bool = False,
    ) -> dict[str, Any]:
        return self.update(
            task_id,
            status="waiting_for_human" if waiting_for_human else "completed",
            result=result,
            run_ids=run_ids or self.get(task_id).get("run_ids", []),
            artifact_ids=artifact_ids or self.get(task_id).get("artifact_ids", []),
            approval_required=waiting_for_human,
            completed_at=None if waiting_for_human else datetime.now(UTC).isoformat(),
        )

    def fail(self, task_id: str, error: str) -> dict[str, Any]:
        return self.update(task_id, status="failed", error=error, completed_at=datetime.now(UTC).isoformat())

    def recover_interrupted(self, *, stale_after: timedelta = timedelta(minutes=30)) -> list[str]:
        cutoff = datetime.now(UTC) - stale_after
        recovered: list[str] = []
        with self._storage_lock():
            tasks = self.storage.read(TASKS_PATH, [])
            for task in tasks:
                if task.get("status") == "cancellation_requested":
                    task.update(status="cancelled", completed_at=datetime.now(UTC).isoformat(), stopped_at="Worker restart")
                    recovered.append(str(task["id"]))
                    continue
                if task.get("status") != "running":
                    continue
                started = self._parse_time(task.get("started_at"))
                if not started or started <= cutoff:
                    task.update(status="queued", started_at=None, error="Recovered after the Agent worker restarted.")
                    recovered.append(str(task["id"]))
            if recovered:
                self.storage.write(TASKS_PATH, tasks)
        return recovered

    def finalize_stale_cancellations(
        self,
        *,
        stale_after: timedelta = timedelta(seconds=5),
        task_id: str | None = None,
    ) -> list[str]:
        """Finalize orphaned STOPPING tasks when their owning request/process is gone.

        A live worker blocked inside a provider call cannot run this reaper. Its
        normal post-call checkpoint remains authoritative. This handles tasks
        owned by a dead API request or a restarted worker.
        """
        cutoff = datetime.now(UTC) - stale_after
        finalized: list[str] = []
        with self._storage_lock():
            tasks = self.storage.read(TASKS_PATH, [])
            for task in tasks:
                if task_id and task.get("id") != task_id:
                    continue
                if task.get("status") != "cancellation_requested":
                    continue
                requested = self._parse_time(task.get("cancellation_requested_at"))
                if requested and requested > cutoff:
                    continue
                now = datetime.now(UTC).isoformat()
                task.update(
                    status="cancelled",
                    completed_at=now,
                    stopped_at=task.get("stopped_at") or "Cancellation watchdog",
                    stopped_step=task.get("stopped_step") or "Cancellation watchdog",
                    result={
                        **(task.get("result") or {}),
                        "message": "Task cancelled. Completed work was preserved.",
                        "task_cancelled": True,
                        "watchdog_finalized": True,
                    },
                )
                AgentTask.model_validate(task)
                finalized.append(str(task["id"]))
            if finalized:
                self.storage.write(TASKS_PATH, tasks)
        return finalized

    def append_message(
        self,
        *,
        channel: str,
        thread_id: str,
        message: str,
        role: str,
        user_id: str | None = None,
        linked_run_ids: list[str] | None = None,
        linked_artifact_ids: list[str] | None = None,
        linked_task_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        record = AgentConversationMessage(
            id=f"message-{uuid.uuid4().hex[:12]}",
            channel=channel,
            thread_id=thread_id,
            user_id=user_id,
            message=" ".join(message.strip().split()),
            role=role,
            created_at=datetime.now(UTC).isoformat(),
            linked_run_ids=linked_run_ids or [],
            linked_artifact_ids=linked_artifact_ids or [],
            linked_task_ids=linked_task_ids or [],
        ).model_dump(mode="json")
        with self._lock:
            records = self.storage.read(CONVERSATIONS_PATH, [])
            records.append(record)
            self.storage.write(CONVERSATIONS_PATH, records[-5000:])
        return record

    def conversation(self, *, channel: str | None = None, thread_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        records = self.storage.read(CONVERSATIONS_PATH, [])
        if channel:
            records = [item for item in records if item.get("channel") == channel]
        if thread_id:
            records = [item for item in records if item.get("thread_id") == thread_id]
        return records[-max(1, min(limit, 500)) :]

    def resolve_context(self, channel: str, thread_id: str) -> dict[str, Any]:
        messages = self.conversation(channel=channel, thread_id=thread_id, limit=50)
        tasks = self.list_tasks(limit=250)
        linked_task_ids = [task_id for message in messages for task_id in message.get("linked_task_ids", [])]
        linked = [task for task in tasks if task.get("id") in linked_task_ids]
        most_recent = linked[0] if linked else None
        return {
            "recent_task_id": most_recent.get("id") if most_recent else None,
            "recent_run_ids": most_recent.get("run_ids", []) if most_recent else [],
            "recent_artifact_ids": most_recent.get("artifact_ids", []) if most_recent else [],
            "recent_result": most_recent.get("result", {}) if most_recent else {},
        }

    def record_outbox(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {"id": f"delivery-{uuid.uuid4().hex[:12]}", "created_at": datetime.now(UTC).isoformat(), **payload}
        records = self.storage.read(OUTBOX_PATH, [])
        records.append(record)
        self.storage.write(OUTBOX_PATH, records[-5000:])
        return record

    def mark_external_event(self, event_id: str) -> bool:
        with self._lock:
            records = self.storage.read(PROCESSED_EVENTS_PATH, [])
            if any(item.get("id") == event_id for item in records):
                return False
            records.append({"id": event_id, "processed_at": datetime.now(UTC).isoformat()})
            self.storage.write(PROCESSED_EVENTS_PATH, records[-5000:])
            return True

    @staticmethod
    def priority_for(source_channel: str, task_type: str) -> int:
        if task_type == "approval":
            return TASK_PRIORITY["approval"]
        if source_channel in {"web", "slack"}:
            return TASK_PRIORITY["explicit_user"]
        if task_type in {"generate_comic", "repair_comic", "review_comic"}:
            return TASK_PRIORITY["generation"]
        if source_channel == "scheduled":
            return TASK_PRIORITY["scheduled"]
        if task_type == "learn" or source_channel == "learning":
            return TASK_PRIORITY["learning"]
        return TASK_PRIORITY["maintenance"]

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    def _ensure_files(self) -> None:
        for path in (TASKS_PATH, CONVERSATIONS_PATH, PROCESSED_EVENTS_PATH, OUTBOX_PATH):
            if not self.repository.path(path).exists():
                self.storage.write(path, [])

    @contextmanager
    def _storage_lock(self):
        """Serialize queue mutations across the API and the persistent worker."""
        lock_path = self.repository.path("app-data/dinkly-agent/task-inbox.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
