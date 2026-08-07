from __future__ import annotations

import json
import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from app.backend.config import settings
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.agent_visual_state_service import AgentVisualStateService
from app.backend.services.repository_service import RepositoryService
from app.backend.services.secrets_service import SecretsService

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "DINKLY Creative Studio API"}


@router.get("/health/agent")
def agent_health() -> dict:
    repository = RepositoryService()
    tasks = AgentTaskService(repository)
    return {
        "status": "healthy",
        "agent": AgentVisualStateService(repository).status(),
        "queued": len(tasks.list_tasks(status="queued", limit=500)),
        "running": len(tasks.list_tasks(status="running", limit=500)),
    }


@router.get("/health/worker")
def worker_health() -> dict:
    heartbeat = RepositoryService().read_json("app-data/dinkly-agent/worker-heartbeat.json", {})
    fresh = False
    with suppress(ValueError, TypeError):
        timestamp = datetime.fromisoformat(str(heartbeat.get("timestamp", "")).replace("Z", "+00:00"))
        fresh = timestamp >= datetime.now(UTC) - timedelta(minutes=2)
    return {"status": "healthy" if fresh else "unavailable", "fresh": fresh, "heartbeat": heartbeat}


@router.get("/health/slack")
def slack_health() -> dict:
    repository = RepositoryService()
    configured = SecretsService(repository).get_slack_secret_status()
    slack_settings = repository.read_json("app-data/dinkly-agent/slack-settings.json", {})
    socket_ready = slack_settings.get("mode") != "socket_mode" or configured["socket_mode_configured"]
    connected = bool(configured["configured"] and slack_settings.get("connected") and socket_ready)
    return {
        "status": "healthy" if connected else "not_configured",
        "connected": connected,
        "mode": slack_settings.get("mode", "events_api"),
        "socket_mode_configured": configured["socket_mode_configured"],
        "socket_mode_active": bool(slack_settings.get("socket_mode_active")),
        "socket_mode_status": slack_settings.get("socket_mode_status"),
        "last_event_received": slack_settings.get("last_event_received"),
        "last_message_sent": slack_settings.get("last_message_sent"),
    }


@router.get("/api/status")
def status() -> dict:
    required = ["README.md", "CHARACTER_BIBLE.md", "data/social_posts.json", "schemas/social_post.schema.json"]
    structure_valid = all(settings.safe_path(item).is_file() for item in required)
    json_valid = True
    schemas_valid = True
    errors: list[str] = []
    for relative in ("data/social_posts.json", "data/social_learnings.json", "data/storyline_scores.json", "data/approved_prompts.json"):
        try:
            payload = json.loads(settings.safe_path(relative).read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("must contain an array")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            json_valid = False
            errors.append(f"{relative}: {exc}")
    for path in settings.safe_path("schemas").glob("*.schema.json"):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            if schema.get("type") != "object" or not schema.get("properties"):
                raise ValueError("invalid schema structure")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            schemas_valid = False
            errors.append(f"{path.name}: {exc}")
    return {
        "frontend_connected": True,
        "backend_connected": True,
        "repository_path": str(settings.repository_root),
        "repository_readable": os.access(settings.repository_root, os.R_OK),
        "repository_writable": os.access(settings.repository_root, os.W_OK),
        "repository_structure_valid": structure_valid,
        "schemas_valid": schemas_valid,
        "json_data_valid": json_valid,
        "errors": errors,
    }
