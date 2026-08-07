from __future__ import annotations

import fcntl
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.backend.models.social_intelligence import RunStatus
from app.backend.services.concept_generator_background_service import ConceptGeneratorBackgroundService
from app.backend.services.concept_generator_schedule import (
    is_scheduled_day,
    next_scheduled_run,
    scheduled_datetime,
    valid_timezone,
)
from app.backend.services.content_agent_service import ConceptGeneratorService

STATE_PATH = "app-data/concept_generator_scheduler_state.json"


class ConceptGeneratorScheduler:
    """Durable orchestration around the one canonical Concept Generator workflow."""

    def __init__(
        self,
        service: ConceptGeneratorService,
        background: ConceptGeneratorBackgroundService | None = None,
    ) -> None:
        self.service = service
        self.repository = service.repository
        self.background = background or ConceptGeneratorBackgroundService(self.repository)

    @property
    def timezone(self) -> ZoneInfo:
        """Compatibility accessor for code written before timezone became persisted settings."""
        return self._timezone(self.service.settings().timezone)

    def state(self, now: datetime | None = None) -> dict[str, Any]:
        settings = self.service.settings()
        timezone = self._timezone(settings.timezone)
        local = self._local_now(now, timezone)
        persisted = self.repository.read_json(STATE_PATH, {})
        if not isinstance(persisted, dict):
            persisted = {}
        next_run = next_scheduled_run(local, settings.run_time, timezone.key, settings.schedule_days)
        if persisted.get("next_run") != next_run.isoformat():
            persisted = self._save(next_run=next_run.isoformat())
        return {
            "enabled": settings.generate_daily_automatically,
            "daily_time": settings.run_time,
            "timezone": timezone.key,
            "every_day_or_weekdays": settings.schedule_days,
            "catch_up_on_wake": settings.catch_up_on_wake,
            "catch_up_on_start": settings.catch_up_on_start,
            "last_checked_at": persisted.get("last_checked_at"),
            "last_attempted_run": persisted.get("last_attempted_run"),
            "last_attempted_date": persisted.get("last_attempted_date"),
            "last_successful_run": persisted.get("last_successful_run"),
            "last_status": persisted.get("last_status", "Never run"),
            "last_error": persisted.get("last_error"),
            "last_failure_at": persisted.get("last_failure_at"),
            "last_failure": persisted.get("last_failure"),
            "last_skip_reason": persisted.get("last_skip_reason"),
            "last_skip_at": persisted.get("last_skip_at") or (persisted.get("last_attempted_run") if persisted.get("last_skip_reason") else None),
            "last_skip": persisted.get("last_skip") or persisted.get("last_skip_reason"),
            "last_run_id": persisted.get("last_run_id"),
            "next_run": next_run.isoformat(),
            "test_scheduled_for": persisted.get("test_scheduled_for"),
            "test_status": persisted.get("test_status", "Not scheduled"),
            "test_completed_at": persisted.get("test_completed_at"),
            "test_error": persisted.get("test_error"),
            "test_batch_id": persisted.get("test_batch_id"),
        }

    def run_due(self, now: datetime | None = None, *, trigger: str = "worker") -> dict[str, Any] | None:
        with self._run_lock() as acquired:
            if not acquired:
                return None
            return self._run_due_locked(now, trigger=trigger)

    def _run_due_locked(self, now: datetime | None = None, *, trigger: str = "worker") -> dict[str, Any] | None:
        """Run a due test or today's single primary batch; never backfill older days."""
        settings = self.service.settings()
        timezone = self._timezone(settings.timezone)
        local = self._local_now(now, timezone)
        self._save(last_checked_at=local.isoformat())
        schedule_state = self.state(local)

        persisted = self.repository.read_json(STATE_PATH, {})
        test_result = self._run_due_test(local)
        if test_result is not None:
            return test_result
        if isinstance(persisted, dict) and persisted.get("test_status") == "Scheduled":
            # A two-minute acceptance test has exclusive priority so it cannot
            # accidentally turn into the daily primary run one second early.
            return None
        if not settings.generate_daily_automatically:
            return None
        if not is_scheduled_day(local.date(), settings.schedule_days):
            return None

        scheduled_for = scheduled_datetime(local.date(), settings.run_time, timezone.key)
        if local < scheduled_for:
            return None
        if self.service.has_primary_batch(local.date()):
            return None

        if schedule_state.get("last_attempted_date") == local.date().isoformat():
            return None

        is_catch_up = local > scheduled_for + timedelta(minutes=5)
        if is_catch_up:
            if trigger == "app_start" and not settings.catch_up_on_start:
                return None
            if trigger != "app_start" and not settings.catch_up_on_wake:
                return None
        source = "catch_up" if is_catch_up else "scheduled"
        return self._execute(
            target_date=local.date(),
            source=source,
            mode="primary",
            scheduled_for=scheduled_for,
            attempted_at=local,
            test=False,
        )

    def diagnostic(self, now: datetime | None = None) -> dict[str, Any]:
        """Check tomorrow's run without contacting or billing the model provider."""
        settings = self.service.settings()
        timezone = self._timezone(settings.timezone)
        local = self._local_now(now, timezone)
        schedule = self.state(local)
        background = self.background.status()
        provider = self.service.provider.health()
        budget = self.service.model_budget_summary()
        preflight = self.service.generation_preflight(
            source="scheduled",
            target_date=next_scheduled_run(local, settings.run_time, timezone.key, settings.schedule_days).date(),
            mode="supplemental",
        )
        problems = list(preflight["problems"])
        if not settings.generate_daily_automatically:
            problems.append("Automatic generation is disabled.")
        if not background["installed"]:
            problems.append("Background agent is not installed.")
        elif not background["running"]:
            problems.append("Background agent is not running.")
        if not valid_timezone(settings.timezone):
            problems.append("The configured IANA timezone is invalid.")
        if provider.get("configured") and provider.get("source") == "environment":
            problems.append("OpenAI API key is only in the API process environment; save it in local Settings so the background agent can load it.")
        elif provider.get("configured") and provider.get("source") not in {"local secrets file", None}:
            problems.append("The AI provider secret source cannot be loaded by the background agent.")
        today_batches = [item for item in self.service.list_batches() if item.get("date") == local.date().isoformat() and item.get("primary")]
        return {
            "ready": not problems,
            "verdict": "READY FOR 8:00 AM" if not problems else "NOT READY",
            "checked_at": local.isoformat(),
            "problems": list(dict.fromkeys(problems)),
            "scheduler": schedule,
            "background_worker": background,
            "ai_provider": provider,
            "provider_health": "Configured; no AI call made by diagnostic" if provider.get("configured") else "Not configured",
            "budget": budget,
            "today_batch_status": today_batches[0].get("status") if today_batches else "No primary batch",
            "duplicate_protection": "Primary exists" if today_batches else "Ready",
        }

    def schedule_test(self, now: datetime | None = None, *, minutes: int = 2) -> dict[str, Any]:
        if minutes != 2:
            raise ValueError("The scheduler acceptance test must run exactly two minutes in the future.")
        diagnostic = self.diagnostic(now)
        if not diagnostic["ready"]:
            return {"scheduled": False, "diagnostic": diagnostic, "message": "Scheduler test was not scheduled because preflight is not ready."}
        timezone = self._timezone(self.service.settings().timezone)
        local = self._local_now(now, timezone)
        due = local + timedelta(minutes=2)
        self._save(
            test_scheduled_for=due.astimezone(UTC).isoformat(),
            test_status="Scheduled",
            test_completed_at=None,
            test_error=None,
            test_batch_id=None,
        )
        return {"scheduled": True, "scheduled_for": due.isoformat(), "test_status": "Scheduled", "diagnostic": diagnostic}

    def recover_interrupted_run(self) -> dict[str, Any] | None:
        """Called only by a newly started LaunchAgent worker."""
        persisted = self.repository.read_json(STATE_PATH, {})
        if not isinstance(persisted, dict) or persisted.get("last_status") != "Running" or not persisted.get("last_run_id"):
            return None
        try:
            run = self.service.runtime.get_run(str(persisted["last_run_id"]))
        except Exception:
            return None
        source = str(run.get("request", {}).get("source", ""))
        if run.get("status") != RunStatus.RUNNING.value or source not in {"scheduled", "catch_up", "scheduler_test"}:
            return None
        message = "The LaunchAgent restarted before the scheduled Concept Generator run completed. The partial batch was preserved and no paid call was resumed automatically."
        failed_at = datetime.now(UTC).isoformat()
        recovered = self.service.runtime.update(run["id"], status=RunStatus.FAILED.value, error=message, completed_at=failed_at)
        self.service.runtime.emit(run["id"], "recovery", message, level="warning")
        batches = list(reversed(self.service.list_batches()))
        for batch in batches:
            if batch.get("agent_run_id") == run["id"] and batch.get("status") == "generating":
                batch["status"] = "failed"
                batch["source_summary"] = message
        self.repository.write_json("data/content_batches.json", batches)
        updates: dict[str, Any] = {
            "last_status": "Failed",
            "last_error": message,
            "last_failure": message,
            "last_failure_at": failed_at,
        }
        if source == "scheduler_test":
            updates.update(test_status="Failed", test_error=message, test_completed_at=failed_at)
        self._save(**updates)
        return recovered

    def _run_due_test(self, local: datetime) -> dict[str, Any] | None:
        persisted = self.repository.read_json(STATE_PATH, {})
        if not isinstance(persisted, dict) or persisted.get("test_status") != "Scheduled":
            return None
        raw_due = persisted.get("test_scheduled_for")
        if not raw_due:
            return None
        try:
            due = datetime.fromisoformat(str(raw_due).replace("Z", "+00:00"))
        except ValueError:
            self._save(test_status="Failed", test_error="Stored scheduler test time is invalid.")
            return None
        if local.astimezone(UTC) < due.astimezone(UTC):
            return None
        return self._execute(
            target_date=local.date(),
            source="scheduler_test",
            mode="supplemental",
            scheduled_for=due.astimezone(local.tzinfo),
            attempted_at=local,
            test=True,
        )

    def _execute(
        self,
        *,
        target_date: date,
        source: str,
        mode: str,
        scheduled_for: datetime,
        attempted_at: datetime,
        test: bool,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {
            "last_attempted_run": attempted_at.isoformat(),
            "last_status": "Running",
            "last_error": None,
            "last_skip_reason": None,
        }
        if not test:
            updates["last_attempted_date"] = target_date.isoformat()
        else:
            updates["test_status"] = "Running"
        self._save(**updates)
        try:
            preflight = self.service.generation_preflight(source=source, target_date=target_date, mode=mode)
            if not preflight["ready"]:
                result = self.service.record_skipped_run(target_date, source, preflight["problems"], scheduled_for=scheduled_for)
            else:
                connection = self._verify_provider_connection()
                if not connection["connected"]:
                    result = self.service.record_skipped_run(target_date, source, [connection["message"]], scheduled_for=scheduled_for)
                else:
                    result = self.service.generate_daily_concept_batch(
                        target_date,
                        source=source,
                        mode=mode,
                        scheduled_for=scheduled_for,
                        execute=False,
                    )
                    self._save(last_run_id=result["run"]["id"])
                    result["result"] = self.service.execute_batch(result["run"]["id"], result["batch"]["id"], mode)
            run = result.get("run", {})
            run_id = run.get("id")
            if result.get("status") == "skipped":
                reason = result.get("message", "Scheduler preflight did not pass.")
                skipped_at = datetime.now(UTC).isoformat()
                saved = {"last_status": "Skipped", "last_skip_reason": reason, "last_skip": reason, "last_skip_at": skipped_at, "last_run_id": run_id}
                if test:
                    saved.update(test_status="Skipped", test_error=reason, test_completed_at=attempted_at.isoformat())
                self._save(**saved)
                return result
            batch_id = result.get("batch", {}).get("id")
            successful = datetime.now(UTC).isoformat()
            saved = {
                "last_status": "Succeeded",
                "last_successful_run": successful,
                "last_run_id": run_id,
                "last_error": None,
            }
            if test:
                saved.update(test_status="Succeeded", test_completed_at=successful, test_batch_id=batch_id)
            self._save(**saved)
            return result
        except Exception as exc:
            message = str(exc)
            failed_at = datetime.now(UTC).isoformat()
            saved = {"last_status": "Failed", "last_error": message, "last_failure": message, "last_failure_at": failed_at}
            if test:
                saved.update(test_status="Failed", test_error=message, test_completed_at=failed_at)
            self._save(**saved)
            raise

    def _verify_provider_connection(self) -> dict[str, Any]:
        provider = self.service.provider
        tester = getattr(provider, "test_connection", None)
        if not callable(tester):
            return {"connected": False, "message": "AI provider cannot verify its connection."}
        try:
            result = tester()
        except Exception as exc:
            return {"connected": False, "message": f"OpenAI connection failed: {exc}"}
        if result.get("connected"):
            return result
        return {**result, "connected": False, "message": result.get("message") or "OpenAI connection failed."}

    def _save(self, **changes: Any) -> dict[str, Any]:
        with self._state_lock():
            state = self.repository.read_json(STATE_PATH, {})
            if not isinstance(state, dict):
                state = {}
            state.update(changes)
            self.repository.write_json(STATE_PATH, state, create_backup=False)
            return state

    @contextmanager
    def _state_lock(self):
        path = self.repository.path("app-data/concept_generator_scheduler_state.lock")
        with path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def _run_lock(self):
        path = self.repository.path("app-data/concept_generator_scheduler_run.lock")
        with path.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _timezone(value: str) -> ZoneInfo:
        return ZoneInfo(value if valid_timezone(value) else "America/New_York")

    @staticmethod
    def _local_now(value: datetime | None, timezone: ZoneInfo) -> datetime:
        if value is None:
            return datetime.now(timezone)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone)
        return value.astimezone(timezone)


# Old imports and an installed pre-consolidation worker continue to resolve to
# the exact same scheduler implementation and preserved records.
ContentAgentScheduler = ConceptGeneratorScheduler
