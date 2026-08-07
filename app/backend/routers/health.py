from __future__ import annotations

import json
import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from app.backend.config import settings
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.agent_visual_state_service import AgentVisualStateService
from app.backend.services.cloud_persistence import cloud_database, cloud_storage
from app.backend.services.repository_service import RepositoryService
from app.backend.services.secrets_service import SecretsService

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    database = database_health()
    storage = storage_health()
    gemini = gemini_health()
    required = [database, storage]
    return {
        "status": "healthy" if all(item["status"] == "healthy" for item in required) else "degraded",
        "service": "DINKLY Creative Studio API",
        "mode": settings.app_mode,
        "database": database,
        "storage": storage,
        "gemini": gemini,
    }


@router.get("/health/database")
def database_health() -> dict:
    if settings.app_mode == "local":
        return {"status": "healthy", "provider": "local_json"}
    try:
        return cloud_database(settings).health()
    except Exception as exc:
        return {"status": "unavailable", "provider": "supabase_postgres", "reason": str(exc)}


@router.get("/health/storage")
def storage_health() -> dict:
    if settings.app_mode == "local":
        return {"status": "healthy", "provider": "local_filesystem"}
    try:
        return cloud_storage(settings).health()
    except Exception as exc:
        return {"status": "unavailable", "provider": "supabase_storage", "reason": str(exc)}


@router.get("/health/gemini")
def gemini_health() -> dict:
    configured = SecretsService(RepositoryService()).get_gemini_status()["configured"]
    return {
        "status": "configured" if configured else "not_configured",
        "provider": "google_gemini",
        "live_api_call_performed": False,
    }


@router.get("/health/agent")
def agent_health() -> dict:
    repository = RepositoryService()
    tasks = AgentTaskService(repository)
    dependencies = [database_health(), storage_health()]
    executor_ready = settings.app_mode == "local" or bool(
        settings.cloud_task_runner_url and settings.cloud_task_token
    )
    healthy = all(item["status"] == "healthy" for item in dependencies) and executor_ready
    return {
        "status": "healthy" if healthy else "degraded",
        "mode": settings.app_mode,
        "executor_configured": executor_ready,
        "dependencies": dependencies,
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
