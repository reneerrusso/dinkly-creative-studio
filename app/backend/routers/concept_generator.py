from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response, status

from app.backend.models.content_agent import (
    BatchRequest,
    ChatRequest,
    ConceptActionRequest,
    ConceptEditRequest,
    ContentProviderInput,
    ContentSettings,
    PreferenceUpdateRequest,
)
from app.backend.services.concept_generator_background_service import ConceptGeneratorBackgroundService
from app.backend.services.concept_generator_scheduler import ConceptGeneratorScheduler
from app.backend.services.concept_generator_service import ConceptGeneratorService
from app.backend.services.repository_service import RepositoryService
from app.backend.services.secrets_service import SecretsService

repository = RepositoryService()
service = ConceptGeneratorService(repository)
background_service = ConceptGeneratorBackgroundService(repository)
scheduler = ConceptGeneratorScheduler(service, background_service)
secrets = SecretsService(repository)

operations = APIRouter()


@operations.get("")
def concept_generator_state() -> dict:
    return {**service.state(), "scheduler": scheduler.state(), "background_agent": background_service.status()}


@operations.get("/settings")
def get_settings() -> dict:
    return service.settings().model_dump(mode="json")


@operations.put("/settings")
def update_settings(payload: ContentSettings) -> dict:
    return service.update_settings(payload)


@operations.get("/daily-batch")
def daily_batch() -> dict:
    today = service.local_date().isoformat()
    batches = [item for item in service.list_batches() if item["date"] == today]
    return {"date": today, "batches": batches, "concepts": service.state()["today_concepts"]}


def _start_batch(payload: BatchRequest, background: BackgroundTasks) -> dict:
    started = service.generate_daily_concept_batch(source="manual", mode=payload.mode, execute=False)
    background.add_task(service.execute_batch, started["run"]["id"], started["batch"]["id"], payload.mode)
    return started


@operations.post("/batches", status_code=status.HTTP_202_ACCEPTED)
def start_batch(payload: BatchRequest, background: BackgroundTasks) -> dict:
    return _start_batch(payload, background)


@operations.post("/generate", status_code=status.HTTP_202_ACCEPTED)
@operations.post("/run-now", status_code=status.HTTP_202_ACCEPTED)
def run_now(payload: BatchRequest, background: BackgroundTasks) -> dict:
    return _start_batch(payload, background)


@operations.get("/batches")
@operations.get("/past-batches")
def batches() -> list[dict]:
    return service.list_batches()


@operations.get("/concepts")
def concepts() -> list[dict]:
    return service.list_concepts()


@operations.get("/production-queue")
def production_queue() -> list[dict]:
    return service.state()["production_queue"]


@operations.get("/used-storylines")
def used_storylines() -> list[dict]:
    return service.state()["used_storylines"]


@operations.post("/concepts/{concept_id}/approve")
def approve(concept_id: str) -> dict:
    return service.approve(concept_id)


@operations.post("/concepts/{concept_id}/pass")
def pass_concept(concept_id: str, payload: ConceptActionRequest) -> dict:
    return service.pass_concept(concept_id, payload.reason)


@operations.patch("/concepts/{concept_id}")
def edit_concept(concept_id: str, payload: ConceptEditRequest) -> dict:
    return service.edit(concept_id, payload.changes)


@operations.post("/concepts/{concept_id}/replace")
def replace_concept(concept_id: str) -> dict:
    return service.replace(concept_id)


@operations.post("/concepts/{concept_id}/prompt-handoff")
def prompt_handoff(concept_id: str) -> dict:
    return service.prompt_handoff(concept_id)


@operations.post("/concepts/{concept_id}/used")
def mark_used(concept_id: str) -> dict:
    return service.mark_used(concept_id)


@operations.delete("/concepts/{concept_id}/queue")
def remove_queue(concept_id: str) -> dict:
    return service.remove_from_queue(concept_id)


@operations.post("/used/{used_id}/variation")
def duplicate_variation(used_id: str) -> dict:
    return service.duplicate_variation(used_id)


@operations.get("/chat")
def chat_history() -> list[dict]:
    return service.state()["chat"]


@operations.post("/chat")
def chat(payload: ChatRequest) -> dict:
    return service.chat(payload.message)


@operations.get("/preferences")
def preferences() -> list[dict]:
    return service.preferences()


@operations.patch("/preferences/{preference_id}")
def update_preference(preference_id: str, payload: PreferenceUpdateRequest) -> dict:
    return service.update_preference(preference_id, payload.model_dump(mode="json", exclude_none=True))


@operations.delete("/preferences/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preference(preference_id: str) -> Response:
    service.delete_preference(preference_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@operations.get("/scheduler")
def scheduler_state() -> dict:
    return {**scheduler.state(), "background_agent": background_service.status()}


@operations.get("/scheduler/diagnostic")
def scheduler_diagnostic() -> dict:
    return scheduler.diagnostic()


@operations.post("/scheduler/test")
def schedule_scheduler_test() -> dict:
    return scheduler.schedule_test(minutes=2)


@operations.get("/background-agent")
def background_agent_status() -> dict:
    return background_service.status()


@operations.post("/background-agent/install")
def install_background_agent() -> dict:
    return background_service.install()


@operations.post("/background-agent/start")
def start_background_agent() -> dict:
    return background_service.start()


@operations.post("/background-agent/restart")
def restart_background_agent() -> dict:
    return background_service.restart()


@operations.get("/background-agent/logs")
def background_agent_logs(lines: int = 100) -> dict:
    return background_service.logs_tail(max(1, min(lines, 500)))


@operations.get("/provider")
def content_provider_status() -> dict:
    return {**secrets.get_content_provider_status(), "runtime": service.provider.health()}


@operations.put("/provider")
def configure_content_provider(payload: ContentProviderInput) -> dict:
    return secrets.configure_content_provider(payload.api_key, payload.model)


@operations.delete("/provider")
def remove_content_provider() -> dict:
    return secrets.remove_content_provider()


@operations.post("/provider/test")
def test_content_provider() -> dict:
    tester = getattr(service.provider, "test_connection", None)
    if not callable(tester):
        return {"connected": False, "message": "The configured provider cannot test its connection."}
    return tester()


router = APIRouter(tags=["concept generator"])
router.include_router(operations, prefix="/api/concept-generator")

# Temporary compatibility surface for old bookmarks and frontend clients. Both
# namespaces call the same service instance and therefore the same preserved
# records; no data is copied or forked.
compatibility_router = APIRouter(tags=["concept generator compatibility"])
compatibility_router.include_router(operations, prefix="/api/content-agent", deprecated=True)
