from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.repository_service import RepositoryService


def create_task(
    service: AgentTaskService,
    *,
    channel: str = "web",
    task_type: str = "custom",
    instruction: str = "Do the assigned work",
    dedupe_key: str | None = None,
) -> tuple[dict, bool]:
    return service.create_task(
        source_channel=channel,  # type: ignore[arg-type]
        source_thread_id=f"thread-{channel}",
        user_instruction=instruction,
        task_type=task_type,  # type: ignore[arg-type]
        dedupe_key=dedupe_key,
    )


def test_shared_inbox_is_persistent_and_prevents_duplicate_events(repository: RepositoryService) -> None:
    service = AgentTaskService(repository)
    first, created = create_task(service, dedupe_key="slack:event-1")
    duplicate, duplicate_created = create_task(service, dedupe_key="slack:event-1")

    restarted = AgentTaskService(repository)
    assert created is True
    assert duplicate_created is False
    assert duplicate["id"] == first["id"]
    assert restarted.get(first["id"])["user_instruction"] == "Do the assigned work"
    assert restarted.mark_external_event("slack:event-2") is True
    assert restarted.mark_external_event("slack:event-2") is False


def test_priority_orders_user_approval_generation_schedule_and_learning(repository: RepositoryService) -> None:
    service = AgentTaskService(repository)
    learning, _ = create_task(service, channel="learning", task_type="learn", instruction="Review evidence")
    scheduled, _ = create_task(
        service,
        channel="scheduled",
        task_type="generate_concepts",
        instruction="Create scheduled concepts",
    )
    generation, _ = create_task(
        service,
        channel="scheduled",
        task_type="generate_comic",
        instruction="Generate scheduled comic",
    )
    approval, _ = create_task(service, channel="scheduled", task_type="approval", instruction="Approve comic")
    user, _ = create_task(service, channel="slack", task_type="generate_comic", instruction="Generate my comic")

    claimed = [service.claim_next()["id"] for _ in range(5)]  # type: ignore[index]
    assert claimed == [user["id"], approval["id"], generation["id"], scheduled["id"], learning["id"]]


def test_worker_restart_recovers_only_stale_running_work(repository: RepositoryService) -> None:
    service = AgentTaskService(repository)
    stale, _ = create_task(service, instruction="Recover me")
    fresh, _ = create_task(service, instruction="Leave me running")
    service.update(
        stale["id"],
        status="running",
        started_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    )
    service.update(fresh["id"], status="running", started_at=datetime.now(UTC).isoformat())

    recovered = AgentTaskService(repository).recover_interrupted(stale_after=timedelta(minutes=30))

    assert recovered == [stale["id"]]
    assert service.get(stale["id"])["status"] == "queued"
    assert service.get(fresh["id"])["status"] == "running"


def test_idle_inbox_claim_makes_no_work(repository: RepositoryService) -> None:
    assert AgentTaskService(repository).claim_next() is None


def test_cancel_queued_running_double_cancel_and_restart(repository: RepositoryService) -> None:
    service = AgentTaskService(repository)
    queued, _ = create_task(service, instruction="Cancel before start")
    cancelled, message = service.request_cancellation(queued["id"])
    assert cancelled["status"] == "cancelled"
    assert message == "Task cancelled."
    assert service.claim_next() is None

    running_source, _ = create_task(service, instruction="Cancel while running")
    running = service.claim_next()
    assert running and running["id"] == running_source["id"]
    stopping, message = service.request_cancellation(running["id"])
    assert stopping["status"] == "cancellation_requested"
    assert message == "Cancellation requested."
    same, message = service.request_cancellation(running["id"])
    assert same["status"] == "cancellation_requested"
    assert message == "Cancellation already requested."
    final = service.mark_cancelled(running["id"], stopped_at="Candidate 2 of 4", artifact_ids=["a", "b"])
    assert final["status"] == "cancelled"
    assert final["artifact_ids"] == ["a", "b"]
    restarted = service.restart(final["id"])
    assert restarted["id"] != final["id"]
    assert restarted["status"] == "queued"
    assert restarted["context"]["restarted_from_task_id"] == final["id"]


def test_completed_task_cannot_be_cancelled(repository: RepositoryService) -> None:
    service = AgentTaskService(repository)
    task, _ = create_task(service)
    service.complete(task["id"], {"message": "done"})
    unchanged, message = service.request_cancellation(task["id"])
    assert unchanged["status"] == "completed"
    assert message == "Task already completed."


def test_orphaned_stopping_task_is_finalized_and_cannot_be_resurrected(repository: RepositoryService) -> None:
    service = AgentTaskService(repository)
    task, _ = create_task(service, instruction="Orphaned approval")
    running = service.claim_next()
    assert running
    service.request_cancellation(task["id"])

    finalized = service.finalize_stale_cancellations(stale_after=timedelta(seconds=0), task_id=task["id"])
    assert finalized == [task["id"]]
    cancelled = service.get(task["id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["result"]["watchdog_finalized"] is True

    late = service.complete(task["id"], {"message": "late callback"})
    assert late["status"] == "cancelled"
    assert late["result"]["message"] != "late callback"
