from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.backend.config import Settings
from app.backend.services.agent_schedule_service import AgentScheduleService
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.repository_service import RepositoryService


class Concepts:
    def settings(self) -> SimpleNamespace:
        return SimpleNamespace(
            generate_daily_automatically=False,
            timezone="America/New_York",
            schedule_days=["monday"],
            run_time="09:00",
        )


class Visual:
    def settings(self) -> dict[str, int]:
        return {"learning_interval_minutes": 60}


def test_cloud_schedule_enqueues_idempotent_learning_task(tmp_path: Path) -> None:
    repository = RepositoryService(
        Settings(repository_root=tmp_path, frontend_origin="http://127.0.0.1:3000", max_upload_bytes=1024)
    )
    tasks = AgentTaskService(repository)
    schedule = AgentScheduleService(repository, tasks, Concepts(), Visual())  # type: ignore[arg-type]
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    first = schedule.queue_due(now)
    second = schedule.queue_due(now)
    assert len(first) == 1
    assert second == []
    assert tasks.get(first[0])["task_type"] == "learn"
