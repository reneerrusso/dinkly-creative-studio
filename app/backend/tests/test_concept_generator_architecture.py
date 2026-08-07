from __future__ import annotations

from datetime import datetime

from app.backend.main import app
from app.backend.models.concept_generator_agent import ConceptGeneratorSettings
from app.backend.services.concept_generator_agent import DevelopmentFixtureProvider
from app.backend.services.concept_generator_scheduler import ConceptGeneratorScheduler
from app.backend.services.concept_generator_service import ConceptGeneratorService
from app.backend.services.repository_service import RepositoryService


def test_canonical_and_compatibility_api_namespaces_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    required = {
        "/api/concept-generator",
        "/api/concept-generator/daily-batch",
        "/api/concept-generator/generate",
        "/api/concept-generator/run-now",
        "/api/concept-generator/production-queue",
        "/api/concept-generator/used-storylines",
        "/api/concept-generator/past-batches",
        "/api/concept-generator/scheduler",
        "/api/concept-generator/scheduler/diagnostic",
        "/api/concept-generator/scheduler/test",
        "/api/concept-generator/background-agent",
        "/api/concept-generator/provider",
    }
    assert required <= paths
    assert "/api/content-agent" in paths
    assert "/api/content-agent/concepts/{concept_id}/prompt-handoff" in paths


def test_canonical_service_uses_preserved_storage(repository: RepositoryService) -> None:
    service = ConceptGeneratorService(repository, DevelopmentFixtureProvider())
    service.chat("More outdoor stories")
    assert repository.read_json("data/content_agent_preferences.json", [])
    assert repository.read_json("app-data/content_agent_chat.json", [])
    assert service.state()["preferences"]
    assert isinstance(ConceptGeneratorScheduler(service), ConceptGeneratorScheduler)


def test_canonical_scheduler_runs_the_daily_workflow(repository: RepositoryService) -> None:
    class ProductionProvider(DevelopmentFixtureProvider):
        development_fixture = False
        real_provider = True

        def test_connection(self):
            return {"connected": True}

    service = ConceptGeneratorService(repository, ProductionProvider())
    service.update_settings(ConceptGeneratorSettings(generate_daily_automatically=True, enable_paid_model_calls=True, run_time="08:00"))
    scheduler = ConceptGeneratorScheduler(service)
    result = scheduler.run_due(datetime(2026, 8, 6, 9, 0, tzinfo=scheduler.timezone))
    assert result is not None
    assert result["run"]["agent"] == "concept-generator"
    assert len(service.list_concepts()) == 30
