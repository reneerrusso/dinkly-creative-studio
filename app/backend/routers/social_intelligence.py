from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.backend.models.social_intelligence import (
    ActorIdsInput,
    BudgetSettings,
    BulkHandleInput,
    ClassificationOverride,
    ConceptDirectionRequest,
    HandleSelection,
    LearningDecision,
    ManualPostInput,
    MonitoredHandleInput,
    MonitoredHandleUpdate,
    ProviderConfigurationInput,
    ProviderResumeRequest,
    ProviderTestRequest,
    RefreshRequest,
)
from app.backend.services.repository_service import RepositoryService
from app.backend.services.social_intelligence_service import SocialIntelligenceService

router = APIRouter(prefix="/api", tags=["social intelligence"])
service = SocialIntelligenceService(RepositoryService())


@router.get("/social-data-providers")
def list_providers() -> list[dict]:
    return service.providers()


@router.post("/social-data-providers/test")
def test_provider(payload: ProviderTestRequest) -> dict:
    return service.test_apify_connection()


@router.post("/social-data-providers/apify/configure")
def configure_apify(payload: ProviderConfigurationInput) -> dict:
    return service.configure_apify(
        payload.token,
        payload.instagram_actor_id,
        payload.tiktok_actor_id,
        payload.instagram_enabled,
        payload.tiktok_enabled,
    )


@router.put("/social-data-providers/apify/actors")
def update_actor_ids(payload: ActorIdsInput) -> dict:
    return service.update_actor_settings(
        payload.instagram_actor_id,
        payload.tiktok_actor_id,
        payload.instagram_enabled,
        payload.tiktok_enabled,
    )


@router.get("/social-provider-actors")
def actor_registry() -> list[dict]:
    return service.actors.records()


@router.delete("/social-data-providers/apify/configure")
def remove_apify() -> dict:
    return {"configuration": service.secrets.remove_apify_token()}


@router.post("/social-data-providers/apify/pause")
def pause_apify() -> dict:
    return service.circuit.pause("Paused by user", "apify")


@router.post("/social-data-providers/apify/resume")
def resume_apify(payload: ProviderResumeRequest) -> dict:
    return service.circuit.resume(confirmed=payload.confirmed, provider="apify")


@router.get("/secrets/status")
def secret_status() -> dict:
    return service.secrets.get_provider_configuration_status()


@router.get("/provider-budget")
def get_budget() -> dict:
    return {
        "settings": service.budget.get_settings().model_dump(mode="json"),
        "usage": service.budget.usage_summary(),
        "provider": service.circuit.state("apify"),
    }


@router.put("/provider-budget")
def update_budget(payload: BudgetSettings) -> dict:
    settings_result, backup = service.budget.update_settings(payload)
    return {"settings": settings_result, "usage": service.budget.usage_summary(), "backup": backup}


@router.get("/provider-usage")
def provider_usage() -> list[dict]:
    return service.budget.usage()


@router.get("/monitored-handles")
def list_handles() -> list[dict]:
    return service.list_handles()


@router.post("/monitored-handles", status_code=status.HTTP_201_CREATED)
def add_handle(payload: MonitoredHandleInput) -> dict:
    record, backup = service.add_handle(payload)
    return {"handle": record, "backup": backup}


@router.post("/monitored-handles/bulk/preview")
def preview_bulk_handles(payload: BulkHandleInput) -> dict:
    return service.preview_bulk_handles(payload)


@router.post("/monitored-handles/bulk", status_code=status.HTTP_201_CREATED)
def add_bulk_handles(payload: BulkHandleInput) -> dict:
    records = service.add_bulk_handles(payload)
    return {"handles": records, "created": len(records)}


@router.put("/monitored-handles/{handle_id}")
def update_handle(handle_id: str, payload: MonitoredHandleUpdate) -> dict:
    record, backup = service.update_handle(handle_id, payload)
    return {"handle": record, "backup": backup}


@router.delete("/monitored-handles/{handle_id}")
def delete_handle(handle_id: str) -> dict:
    record, backup = service.remove_handle(handle_id)
    return {
        "handle": record,
        "backup": backup,
        "message": "Monitoring removed. Historical profiles, posts, snapshots, and learnings were preserved.",
    }


@router.post("/monitored-handles/validate")
def validate_handles(payload: HandleSelection) -> list[dict]:
    return service.validate_handles(payload)


@router.post("/monitored-handles/preflight")
def preflight(payload: HandleSelection) -> dict:
    return service.preflight(payload)


@router.post("/monitored-handles/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_handles(payload: RefreshRequest, background_tasks: BackgroundTasks) -> dict:
    result = service.start_refresh(payload)
    background_tasks.add_task(service.execute_refresh, result["run"]["id"], payload)
    return result


@router.post("/monitored-handles/{handle_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_handle(handle_id: str, payload: RefreshRequest, background_tasks: BackgroundTasks) -> dict:
    scoped = payload.model_copy(update={"handle_ids": [handle_id]})
    result = service.start_refresh(scoped)
    background_tasks.add_task(service.execute_refresh, result["run"]["id"], scoped)
    return result


@router.get("/competitor-profiles")
def competitor_profiles() -> list[dict]:
    return service.list_profiles()


@router.post("/competitor-posts/import", status_code=status.HTTP_201_CREATED)
async def import_competitor_posts(file: Annotated[UploadFile, File()]) -> dict:
    return service.import_posts(file.filename or "public-posts.json", await file.read())


@router.post("/competitor-posts", status_code=status.HTTP_201_CREATED)
def add_competitor_post(payload: ManualPostInput) -> dict:
    return service.add_manual_post(payload)


@router.get("/competitor-posts")
def competitor_posts() -> list[dict]:
    return service.list_posts()


@router.get("/competitor-posts/{post_id}")
def competitor_post(post_id: str) -> dict:
    return service.get_post(post_id)


@router.get("/competitor-posts/{post_id}/snapshots")
def competitor_post_snapshots(post_id: str) -> list[dict]:
    service.get_post(post_id)
    return service.snapshots(post_id)


@router.put("/competitor-posts/{post_id}/classification")
def override_classification(post_id: str, payload: ClassificationOverride) -> dict:
    return service.override_classification(post_id, payload.creative_attributes)


@router.post("/competitor-analysis")
def analyze_existing() -> dict:
    return service.analyze_existing_data()


@router.get("/competitor-learnings")
def competitor_learnings() -> list[dict]:
    return service.list_learnings()


@router.post("/competitor-learnings/{learning_id}/approve")
def approve_learning(learning_id: str, payload: LearningDecision) -> dict:
    return service.decide_learning(learning_id, "Approved", payload.notes)


@router.post("/competitor-learnings/{learning_id}/reject")
def reject_learning(learning_id: str, payload: LearningDecision) -> dict:
    return service.decide_learning(learning_id, "Rejected", payload.notes)


@router.post("/competitor-concepts/generate")
def generate_competitor_concepts(payload: ConceptDirectionRequest) -> dict:
    records = service.generate_directions(payload)
    return {"directions": records, "created": len(records)}


@router.get("/competitor-concepts")
def competitor_concepts() -> list[dict]:
    return service.list_directions()


@router.post("/competitor-concepts/{direction_id}/open-in-prompt-builder")
def open_in_prompt_builder(direction_id: str) -> dict:
    return service.open_direction_in_prompt_builder(direction_id)


@router.get("/agent-runs")
def list_agent_runs() -> list[dict]:
    return service.runtime.list_runs()


@router.get("/agent-runs/{run_id}")
def get_agent_run(run_id: str) -> dict:
    return service.runtime.get_run(run_id)


@router.post("/agent-runs/{run_id}/cancel")
def cancel_agent_run(run_id: str) -> dict:
    return service.cancel_run(run_id)


@router.get("/agent-runs/{run_id}/events")
async def stream_agent_events(run_id: str, request: Request) -> StreamingResponse:
    service.runtime.get_run(run_id)

    async def stream():
        cursor: str | None = None
        idle_ticks = 0
        while True:
            if await request.is_disconnected():
                break
            events = service.runtime.events(run_id, cursor)
            if events:
                idle_ticks = 0
                for event in events:
                    cursor = event["id"]
                    yield service.runtime.sse(event)
            else:
                idle_ticks += 1
                if idle_ticks % 30 == 0:
                    yield ": keep-alive\n\n"
            run = service.runtime.get_run(run_id)
            if run["status"] != "Running" and not service.runtime.events(run_id, cursor):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
