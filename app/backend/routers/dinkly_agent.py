from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi import status as http_status
from fastapi.responses import StreamingResponse

from app.backend.models.dinkly_agent import (
    AgentApprovalRequest,
    AgentInstructionRequest,
    AgentSettingsUpdate,
    DinklyAgentChatRequest,
    DinklyLearningRunRequest,
    ExpressionState,
)
from app.backend.services.agent_background_service import AgentBackgroundService
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.agent_visual_state_service import AgentVisualStateService, DinklyLearningLoop
from app.backend.services.dinkly_agent_runtime import DinklyAgent
from app.backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api/dinkly-agent", tags=["dinkly agent"])
repository = RepositoryService()
service = AgentVisualStateService(repository)
learning_loop = DinklyLearningLoop(repository, service)
task_service = AgentTaskService(repository)
agent = DinklyAgent(repository, tasks=task_service, visual=service, learning=learning_loop)
background = AgentBackgroundService(repository)


@router.get("/status")
def status() -> dict:
    return service.status()


@router.get("/events")
def events(after: str | None = None, limit: int = 100) -> list[dict]:
    return service.events(after, limit=limit)


@router.get("/stream")
async def stream() -> StreamingResponse:
    async def event_stream():
        last_id: str | None = None
        idle = 0
        while idle < 1800:
            records = service.events(last_id, limit=100)
            if records:
                idle = 0
                for event in records:
                    last_id = event["id"]
                    yield f"id: {event['id']}\nevent: activity\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            else:
                idle += 1
                yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/expressions")
def expressions() -> list[dict]:
    return service.expressions()


@router.put("/expressions/{state}")
async def upload_expression(state: ExpressionState, file: Annotated[UploadFile, File()]) -> dict:
    return service.save_expression(state, await file.read())


@router.get("/chat")
def chat() -> list[dict]:
    return learning_loop.chat()


@router.post("/chat")
def save_chat(payload: DinklyAgentChatRequest) -> dict:
    return learning_loop.save_chat_preference(payload.message)


@router.get("/learnings")
def learnings(limit: int = 12) -> list[dict]:
    return learning_loop.recent_learnings(limit)


@router.post("/learning/run")
def run_learning(payload: DinklyLearningRunRequest) -> dict:
    return learning_loop.run(force=payload.force)


@router.get("/learning/checkpoint")
def learning_checkpoint() -> dict:
    return repository.read_json("app-data/dinkly-agent/learning-checkpoint.json", {})


@router.get("/workspace")
def workspace() -> dict:
    return agent.workspace()


@router.post("/instructions", status_code=http_status.HTTP_202_ACCEPTED)
def receive_instruction(payload: AgentInstructionRequest) -> dict:
    return agent.receive_instruction(
        channel="web",
        message=payload.message,
        user_id=payload.user_id,
        thread_id=payload.thread_id,
        extra_context={**payload.context, "notify_slack": payload.notify_slack},
    )


@router.get("/conversations")
def conversations(channel: str = "web", thread_id: str = "web-default", limit: int = 100) -> list[dict]:
    return task_service.conversation(channel=channel, thread_id=thread_id, limit=limit)


@router.get("/tasks")
def tasks(task_status: str | None = None, limit: int = 100) -> list[dict]:
    return task_service.list_tasks(status=task_status, limit=limit)


@router.get("/tasks/current")
def current_task() -> dict:
    return task_service.current() or {"status": "idle", "message": "No task is currently running."}


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> dict:
    return agent.request_cancellation(task_id)


@router.post("/tasks/{task_id}/skip")
def skip_task(task_id: str) -> dict:
    return agent.request_cancellation(task_id, reason="Skipped by user", skip=True)


@router.post("/tasks/{task_id}/restart", status_code=http_status.HTTP_202_ACCEPTED)
def restart_task(task_id: str) -> dict:
    return {"task": agent.restart_task(task_id), "message": "A new task was queued."}


@router.get("/tasks/{task_id}")
def task(task_id: str) -> dict:
    return task_service.get(task_id)


@router.get("/tasks/{task_id}/events")
def task_events(task_id: str, after: str | None = None) -> list[dict]:
    return agent.task_events(task_id, after)


@router.get("/tasks/{task_id}/stream")
async def task_stream(task_id: str) -> StreamingResponse:
    task_service.get(task_id)

    async def event_stream():
        last_id: str | None = None
        idle = 0
        while idle < 1800:
            records = agent.task_events(task_id, last_id)
            if records:
                idle = 0
                for event in records:
                    last_id = event["id"]
                    yield f"id: {event['id']}\nevent: activity\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            else:
                idle += 1
                yield ": keep-alive\n\n"
            if task_service.get(task_id).get("status") in {"completed", "failed", "cancelled", "waiting_for_human"} and not records:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/tasks/run-next")
def run_next_task() -> dict:
    return agent.start_run() or {"status": "idle", "message": "No assignments are waiting."}


@router.get("/approvals")
def approvals() -> dict:
    return agent.approvals()


@router.post("/approvals", status_code=http_status.HTTP_202_ACCEPTED)
def approval(payload: AgentApprovalRequest) -> dict:
    return agent.receive_approval(
        action=payload.action,
        item_type=payload.item_type,
        item_id=payload.item_id,
        notes=payload.notes,
        source_channel=payload.source_channel,
        source_thread_id=payload.source_thread_id,
    )


@router.get("/history")
def work_history(limit: int = 100) -> list[dict]:
    return agent.history(limit)


@router.get("/settings")
def agent_settings() -> dict:
    return service.settings()


@router.put("/settings")
def update_agent_settings(payload: AgentSettingsUpdate) -> dict:
    return service.update_settings(payload.model_dump(exclude_unset=True))


@router.get("/worker")
def worker_status() -> dict:
    return background.status()


@router.post("/worker/install")
def install_worker() -> dict:
    return background.install()


@router.post("/worker/start")
def start_worker() -> dict:
    return background.start()


@router.post("/worker/restart")
def restart_worker() -> dict:
    return background.restart()


@router.get("/worker/logs")
def worker_logs(lines: int = 100) -> dict:
    return background.logs_tail(lines=max(10, min(lines, 500)))
