from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.agent_visual_state_service import AgentVisualStateService
from app.backend.services.concept_generator_schedule import is_scheduled_day, scheduled_datetime
from app.backend.services.content_agent_service import ConceptGeneratorService
from app.backend.services.repository_service import RepositoryService


class AgentScheduleService:
    """Translates due work into the canonical inbox without invoking a model itself."""

    def __init__(
        self,
        repository: RepositoryService,
        tasks: AgentTaskService,
        concepts: ConceptGeneratorService,
        visual: AgentVisualStateService,
    ) -> None:
        self.repository = repository
        self.tasks = tasks
        self.concepts = concepts
        self.visual = visual

    def queue_due(self, now: datetime | None = None) -> list[str]:
        queued: list[str] = []
        now = now or datetime.now(UTC)
        settings = self.concepts.settings()
        local = now.astimezone(ZoneInfo(settings.timezone))
        if (
            settings.generate_daily_automatically
            and is_scheduled_day(local.date(), settings.schedule_days)
            and local >= scheduled_datetime(local.date(), settings.run_time, settings.timezone)
            and not self.concepts.has_primary_batch(local.date())
        ):
            task, created = self.tasks.create_task(
                source_channel="scheduled",
                source_thread_id=f"daily-concepts-{local.date().isoformat()}",
                user_instruction="Create today's scheduled DINKLY concept batch",
                task_type="generate_concepts",
                priority=4,
                context={"requested_count": 10, "scheduled_for": local.isoformat()},
                dedupe_key=f"scheduled-concepts:{local.date().isoformat()}",
            )
            if created:
                queued.append(task["id"])

        checkpoint = self.repository.read_json("app-data/dinkly-agent/learning-checkpoint.json", {})
        last = self._time(checkpoint.get("last_checked_at"))
        interval = timedelta(minutes=int(self.visual.settings()["learning_interval_minutes"]))
        if not last or now - last >= interval:
            bucket = int(now.timestamp() // max(60, int(interval.total_seconds())))
            task, created = self.tasks.create_task(
                source_channel="learning",
                source_thread_id=f"learning-{bucket}",
                user_instruction="Review new production evidence and update the DINKLY Brain",
                task_type="learn",
                priority=5,
                dedupe_key=f"scheduled-learning:{bucket}",
            )
            if created:
                queued.append(task["id"])
        return queued

    @staticmethod
    def _time(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
