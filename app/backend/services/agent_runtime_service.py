from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.backend.models.social_intelligence import RunStatus
from app.backend.services.repository_service import RepositoryError, RepositoryService

RUNS_PATH = "app-data/agent_runs.json"
EVENTS_PATH = "app-data/agent_events.json"
TERMINAL_STATUSES = {status.value for status in RunStatus if status is not RunStatus.RUNNING}


class AgentRuntimeService:
    _lock = threading.RLock()

    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.recover_interrupted_runs()

    def create_run(self, kind: str, request: dict[str, Any], *, agent: str = "social-intelligence") -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        record = {
            "id": f"run-{uuid.uuid4().hex[:12]}",
            "agent": agent,
            "kind": kind,
            "status": RunStatus.RUNNING.value,
            "request": request,
            "summary": {},
            "warnings": [],
            "error": None,
            "cancel_requested": False,
            "created_at": now,
            "started_at": now,
            "completed_at": None,
        }
        with self._lock:
            records = self.repository.read_json(RUNS_PATH, [])
            records.append(record)
            self.repository.write_json(RUNS_PATH, records)
        self.emit(record["id"], "run", "Run created.", {"kind": kind})
        return record

    def list_runs(self) -> list[dict[str, Any]]:
        return [self._with_display_agent(record) for record in reversed(self.repository.read_json(RUNS_PATH, []))]

    def get_run(self, run_id: str) -> dict[str, Any]:
        for record in self.repository.read_json(RUNS_PATH, []):
            if record.get("id") == run_id:
                return self._with_display_agent(record)
        raise RepositoryError("Agent run not found")

    def update(self, run_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            records = self.repository.read_json(RUNS_PATH, [])
            for index, record in enumerate(records):
                if record.get("id") == run_id:
                    updated = {**record, **changes}
                    if updated.get("status") in TERMINAL_STATUSES and not updated.get("completed_at"):
                        updated["completed_at"] = datetime.now(UTC).isoformat()
                    records[index] = updated
                    self.repository.write_json(RUNS_PATH, records)
                    return updated
        raise RepositoryError("Agent run not found")

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        summary: dict[str, Any],
        *,
        warnings: list[str] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        record = self.update(run_id, status=status.value, summary=summary, warnings=warnings or [], error=error)
        message = {
            RunStatus.COMPLETED: "Social Intelligence refresh completed.",
            RunStatus.WARNINGS: "Social Intelligence refresh completed with warnings.",
            RunStatus.PARTIAL: "Social Intelligence refresh preserved partial results.",
            RunStatus.BUDGET_STOPPED: "Social Intelligence refresh stopped at a configured budget boundary.",
            RunStatus.RATE_LIMITED: "Social Intelligence refresh stopped after provider rate limiting.",
            RunStatus.PROVIDER_UNAVAILABLE: "Social Intelligence refresh stopped because the provider was unavailable.",
            RunStatus.CANCELLED: "Social Intelligence refresh was cancelled.",
        }.get(status, "Social Intelligence refresh failed.")
        self.emit(run_id, "complete", message, {"status": status.value, "summary": summary}, level="warning" if warnings or error else "info")
        return record

    def cancel(self, run_id: str) -> dict[str, Any]:
        record = self.get_run(run_id)
        if record.get("status") in TERMINAL_STATUSES:
            return record
        updated = self.update(run_id, cancel_requested=True)
        self.emit(run_id, "cancellation", "Cancellation requested. The active provider request will be stopped when supported.", level="warning")
        return updated

    def is_cancelled(self, run_id: str) -> bool:
        return bool(self.get_run(run_id).get("cancel_requested"))

    def emit(
        self,
        run_id: str,
        kind: str,
        message: str,
        data: dict[str, Any] | None = None,
        *,
        level: str = "info",
    ) -> dict[str, Any]:
        event = {
            "id": f"event-{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "kind": kind,
            "message": message,
            "data": data or {},
        }
        with self._lock:
            records = self.repository.read_json(EVENTS_PATH, [])
            records.append(event)
            self.repository.write_json(EVENTS_PATH, records)
        return event

    def events(self, run_id: str, after: str | None = None) -> list[dict[str, Any]]:
        records = [item for item in self.repository.read_json(EVENTS_PATH, []) if item.get("run_id") == run_id]
        if not after:
            return records
        for index, record in enumerate(records):
            if record.get("id") == after:
                return records[index + 1 :]
        return records

    def sse(self, event: dict[str, Any]) -> str:
        return f"id: {event['id']}\nevent: {event['kind']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    def recover_interrupted_runs(self, *, stale_after: timedelta = timedelta(minutes=30)) -> list[str]:
        """Recover genuinely stale runs without corrupting work active in another process."""
        recovered: list[str] = []
        cutoff = datetime.now(UTC) - stale_after
        with self._lock:
            records = self.repository.read_json(RUNS_PATH, [])
            changed = False
            for record in records:
                try:
                    started = datetime.fromisoformat(str(record.get("started_at", "")).replace("Z", "+00:00"))
                except ValueError:
                    started = datetime.min.replace(tzinfo=UTC)
                if record.get("status") == RunStatus.RUNNING.value and started <= cutoff:
                    record["status"] = RunStatus.PARTIAL.value if record.get("summary") else RunStatus.FAILED.value
                    record["error"] = "The local worker stopped before this run completed. It can be retried."
                    record["completed_at"] = datetime.now(UTC).isoformat()
                    recovered.append(record["id"])
                    changed = True
            if changed:
                self.repository.write_json(RUNS_PATH, records)
        for run_id in recovered:
            self.emit(run_id, "recovery", "Recovered an interrupted run after the local worker restarted.", level="warning")
        return recovered

    @staticmethod
    def _with_display_agent(record: dict[str, Any]) -> dict[str, Any]:
        display = {
            "content": "Concept Generator",
            "content-agent": "Concept Generator",
            "concept-generator": "Concept Generator",
        }.get(str(record.get("agent")))
        return {**record, **({"display_agent": display} if display else {})}
