from __future__ import annotations

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, status

from app.backend.config import settings
from app.backend.routers.dinkly_agent import agent, repository, service, task_service
from app.backend.services.agent_schedule_service import AgentScheduleService
from app.backend.services.cloud_task_dispatcher import CloudTaskDispatcher
from app.backend.services.repository_service import RepositoryError

router = APIRouter(prefix="/api/cloud", tags=["cloud runtime"])
dispatcher = CloudTaskDispatcher(settings)


def _authorize(actual: str | None, expected: str | None, label: str) -> None:
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{label} is not configured")
    candidate = (actual or "").removeprefix("Bearer ").strip()
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cloud runtime authorization failed")


@router.post("/tasks/run-next")
def run_next(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    _authorize(authorization, settings.cloud_task_token, "CLOUD_TASK_TOKEN")
    completed: list[str] = []
    last: dict | None = None
    for _ in range(limit):
        last = agent.start_run()
        if not last:
            break
        if last.get("id"):
            completed.append(last["id"])
    return {
        "status": "processed" if completed else "idle",
        "processed_task_ids": completed,
        "last_task": last,
    }


@router.post("/schedules/{job}")
def run_schedule(
    job: str,
    background_tasks: BackgroundTasks,
    x_dinkly_scheduler_token: str | None = Header(default=None),
) -> dict:
    _authorize(x_dinkly_scheduler_token, settings.cloud_scheduler_token, "CLOUD_SCHEDULER_TOKEN")
    if job == "due":
        queued = AgentScheduleService(repository, task_service, agent.concepts, service).queue_due()
    elif job == "learning":
        bucket = int(datetime.now(UTC).timestamp() // 3600)
        task, created = task_service.create_task(
            source_channel="learning",
            source_thread_id=f"cloud-learning-{bucket}",
            user_instruction="Review new production evidence and update the DINKLY Brain",
            task_type="learn",
            priority=5,
            dedupe_key=f"cloud-learning:{bucket}",
        )
        queued = [task["id"]] if created else []
    elif job == "maintenance":
        recovered = task_service.recover_interrupted()
        return {"job": job, "recovered": recovered, "queued": []}
    else:
        raise RepositoryError("Unknown cloud schedule. Use due, learning, or maintenance")
    if queued:
        background_tasks.add_task(dispatcher.dispatch)
    return {"job": job, "queued": queued}
