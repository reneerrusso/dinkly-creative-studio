from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.backend.models.generation_engine import (
    ApprovalRequest,
    CandidateQaRequest,
    CandidateRetryRequest,
    CandidateSelectRequest,
    GeminiKeyInput,
    GenerationRequest,
    ImageGenerationSettings,
    ModelCompareRequest,
    RejectRunRequest,
    RepairRequest,
    StoryBriefRequest,
)
from app.backend.services.concept_service import ConceptService
from app.backend.services.generation_engine_service import TERMINAL_STATUSES, GenerationEngineService
from app.backend.services.prompt_service import PromptService
from app.backend.services.repository_service import RepositoryService

router = APIRouter(tags=["generation engine"])
repository = RepositoryService()
service = GenerationEngineService(repository, PromptService(repository, ConceptService(repository)))


@router.post("/api/generation-engine/brief")
def build_brief(payload: StoryBriefRequest) -> dict:
    return service.build_brief(payload)


@router.post("/api/generation-engine/generate", status_code=status.HTTP_202_ACCEPTED)
def generate(payload: GenerationRequest, background: BackgroundTasks) -> dict:
    run = service.start(payload)
    background.add_task(service.execute, run["id"])
    return run


@router.get("/api/generation-engine/runs/{run_id}")
def get_run(run_id: str) -> dict:
    return service.get(run_id)


@router.get("/api/generation-engine/runs/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    service.get(run_id)

    async def event_stream():
        last_id: str | None = None
        idle = 0
        while idle < 300:
            events = service.events(run_id, last_id)
            if events:
                idle = 0
                for event in events:
                    last_id = event["id"]
                    yield service.runtime.sse(event)
            else:
                idle += 1
                yield ": keep-alive\n\n"
            if service.get(run_id)["status"] in TERMINAL_STATUSES | {"awaiting_human"} and not events:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/generation-engine/runs/{run_id}/candidates")
def candidates(run_id: str) -> list[dict]:
    return service.list_candidates(run_id)


@router.get("/api/generation-engine/runs/{run_id}/events")
def run_events(run_id: str) -> list[dict]:
    return service.events(run_id)


@router.post("/api/generation-engine/candidates/{candidate_id}/select")
def select_candidate(candidate_id: str, payload: CandidateSelectRequest) -> dict:
    if not payload.selected:
        return service.select_candidate(candidate_id)
    return service.select_candidate(candidate_id)


@router.post("/api/generation-engine/candidates/{candidate_id}/qa")
def qa_candidate(candidate_id: str, payload: CandidateQaRequest) -> dict:
    return service.qa_candidate(candidate_id, payload.manual_findings)


@router.post("/api/generation-engine/candidates/{candidate_id}/retry")
def retry_candidate(candidate_id: str, payload: CandidateRetryRequest) -> dict:
    return service.retry_candidate(candidate_id, confirm_pro=payload.confirm_pro)


@router.post("/api/generation-engine/candidates/{candidate_id}/repair")
def repair_candidate(candidate_id: str, payload: RepairRequest) -> dict:
    return service.repair(candidate_id, payload)


@router.post("/api/generation-engine/runs/{run_id}/approve")
def approve(run_id: str, payload: ApprovalRequest) -> dict:
    return service.approve(run_id, payload.approved_by)


@router.post("/api/generation-engine/runs/{run_id}/reject")
def reject(run_id: str, payload: RejectRunRequest) -> dict:
    return service.reject(run_id, payload.reason)


@router.post("/api/generation-engine/runs/{run_id}/cancel")
def cancel(run_id: str) -> dict:
    return service.cancel(run_id)


@router.post("/api/generation-engine/model-compare", status_code=status.HTTP_202_ACCEPTED)
def model_compare(payload: ModelCompareRequest, background: BackgroundTasks) -> dict:
    run = service.compare_models(payload)
    background.add_task(service.execute_comparison, run["id"])
    return run


@router.get("/api/generation-engine/history")
def history() -> list[dict]:
    return service.history()


@router.get("/api/generation-engine/runs/{run_id}/download/final")
def download_final(run_id: str, format: str = "png", comic: int | None = None) -> FileResponse:
    artifact = service.download_final(run_id, format, comic_number=comic)
    return FileResponse(artifact.path, media_type=artifact.media_type, filename=artifact.filename)


@router.get("/api/generation-engine/runs/{run_id}/download/original")
def download_original(run_id: str, candidate_id: str | None = None) -> FileResponse:
    artifact = service.download_original(run_id, candidate_id=candidate_id)
    return FileResponse(artifact.path, media_type=artifact.media_type, filename=artifact.filename)


@router.get("/api/generation-engine/runs/{run_id}/download/candidates")
def download_candidates(run_id: str) -> FileResponse:
    artifact = service.download_candidates(run_id)
    return FileResponse(artifact.path, media_type=artifact.media_type, filename=artifact.filename)


@router.get("/api/generation-engine/runs/{run_id}/download/qa")
def download_qa(run_id: str) -> FileResponse:
    artifact = service.download_qa(run_id)
    return FileResponse(artifact.path, media_type=artifact.media_type, filename=artifact.filename)


@router.get("/api/generation-engine/runs/{run_id}/download/summary")
def download_summary(run_id: str) -> FileResponse:
    artifact = service.download_summary(run_id)
    return FileResponse(artifact.path, media_type=artifact.media_type, filename=artifact.filename)


@router.get("/api/generation-engine/runs/{run_id}/download/all")
def download_all_comics(run_id: str) -> FileResponse:
    artifact = service.download_all_comics(run_id)
    return FileResponse(artifact.path, media_type=artifact.media_type, filename=artifact.filename)


@router.get("/api/generation-engine/model-stats")
def model_stats() -> list[dict]:
    return service.model_stats()


@router.get("/api/image-models")
def image_models() -> list[dict]:
    settings = service.settings()
    return service.registry.list(expose_ids=not settings.demo_mode or settings.developer_mode)


@router.get("/api/image-provider/status")
def image_provider_status() -> dict:
    return service.provider_status()


@router.post("/api/image-provider/test")
def test_image_provider() -> dict:
    return service.provider_status(test=True)


@router.put("/api/image-provider/key")
def save_image_provider_key(payload: GeminiKeyInput) -> dict:
    return service.secrets.configure_gemini(payload.api_key)


@router.delete("/api/image-provider/key", status_code=status.HTTP_204_NO_CONTENT)
def remove_image_provider_key() -> Response:
    service.secrets.remove_gemini()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/generation-engine/settings")
def get_image_settings() -> dict:
    return service.settings().model_dump(mode="json")


@router.put("/api/generation-engine/settings")
def update_image_settings(payload: ImageGenerationSettings) -> dict:
    return service.update_settings(payload)
