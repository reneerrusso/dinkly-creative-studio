from __future__ import annotations

import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.backend.models.content_agent import ContentSettings
from app.backend.services.concept_generator_background_service import ConceptGeneratorBackgroundService
from app.backend.services.concept_generator_schedule import next_scheduled_run
from app.backend.services.content_agent import DevelopmentFixtureProvider, UnavailableContentModelProvider
from app.backend.services.content_agent_scheduler import ConceptGeneratorScheduler
from app.backend.services.content_agent_service import ConceptGeneratorService
from app.backend.services.repository_service import RepositoryService


class ProductionTestProvider(DevelopmentFixtureProvider):
    name = "test-production-provider"
    development_fixture = False
    real_provider = True
    estimated_batch_cost = 0.5

    def test_connection(self) -> dict[str, Any]:
        return {"connected": True, "configured": True, "provider": self.name, "source": "local secrets file"}

    def health(self) -> dict[str, Any]:
        return {"configured": True, "provider": self.name, "real_provider": True, "source": "local secrets file"}


class BackgroundStub:
    def __init__(self, *, installed: bool = True, running: bool = True) -> None:
        self.installed = installed
        self.running = running

    def status(self) -> dict[str, Any]:
        return {"installed": self.installed, "loaded": self.running, "running": self.running, "status": "Running" if self.running else "Not Running"}


def enable(service: ConceptGeneratorService, **changes: Any) -> None:
    payload = {
        **service.settings().model_dump(mode="json"),
        "generate_daily_automatically": True,
        "enable_paid_model_calls": True,
        **changes,
    }
    service.update_settings(ContentSettings.model_validate(payload))


def scheduler(service: ConceptGeneratorService, *, running: bool = True) -> ConceptGeneratorScheduler:
    return ConceptGeneratorScheduler(service, BackgroundStub(installed=running, running=running))  # type: ignore[arg-type]


def test_manual_and_scheduled_use_the_same_canonical_service(repository: RepositoryService) -> None:
    class SpyService(ConceptGeneratorService):
        sources: list[str] = []

        def generate_daily_concept_batch(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.sources.append(str(kwargs.get("source")))
            return super().generate_daily_concept_batch(*args, **kwargs)

    service = SpyService(repository, ProductionTestProvider())
    service.generate_daily_concept_batch(source="manual", mode="supplemental", execute=False)
    enable(service)
    scheduler(service).run_due(datetime(2026, 8, 7, 8, 0, tzinfo=ZoneInfo("America/New_York")))
    assert service.sources == ["manual", "scheduled"]
    assert len(service.list_concepts()) == 30


def test_eight_am_is_local_and_next_run_is_dst_safe() -> None:
    zone = ZoneInfo("America/New_York")
    before = datetime(2026, 3, 7, 9, 0, tzinfo=zone)
    after = next_scheduled_run(before, "08:00", "America/New_York", "every_day")
    assert after.isoformat() == "2026-03-08T08:00:00-04:00"
    assert after.hour == 8
    assert after.utcoffset() == timedelta(hours=-4)


def test_timezone_and_scheduler_state_persist(repository: RepositoryService) -> None:
    service = ConceptGeneratorService(repository, ProductionTestProvider())
    enable(service, timezone="America/Los_Angeles")
    first = scheduler(service)
    first.run_due(datetime(2026, 8, 6, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles")))
    second = scheduler(ConceptGeneratorService(repository, ProductionTestProvider()))
    state = second.state(datetime(2026, 8, 6, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles")))
    assert state["timezone"] == "America/Los_Angeles"
    assert state["last_status"] == "Succeeded"
    assert state["last_successful_run"]


def test_diagnostic_reports_background_and_provider_failures(repository: RepositoryService) -> None:
    service = ConceptGeneratorService(repository, UnavailableContentModelProvider())
    enable(service)
    diagnostic = scheduler(service, running=False).diagnostic(datetime(2026, 8, 6, 7, 0, tzinfo=UTC))
    assert diagnostic["verdict"] == "NOT READY"
    assert "Background agent is not installed." in diagnostic["problems"]
    assert "No AI provider configured." in diagnostic["problems"]


def test_diagnostic_rejects_process_only_provider_secret(repository: RepositoryService) -> None:
    class ProcessOnlyProvider(ProductionTestProvider):
        def health(self) -> dict[str, Any]:
            return {**super().health(), "source": "environment"}

    service = ConceptGeneratorService(repository, ProcessOnlyProvider())
    enable(service)
    diagnostic = scheduler(service).diagnostic(datetime(2026, 8, 6, 7, 0, tzinfo=UTC))
    assert diagnostic["ready"] is False
    assert any("only in the API process environment" in problem for problem in diagnostic["problems"])


def test_budget_preflight_skips_without_creating_a_batch(repository: RepositoryService) -> None:
    service = ConceptGeneratorService(repository, ProductionTestProvider())
    enable(service, daily_model_budget=0.25, monthly_model_budget=1.0)
    result = scheduler(service).run_due(datetime(2026, 8, 6, 9, 0, tzinfo=ZoneInfo("America/New_York")))
    assert result and result["status"] == "skipped"
    assert "Daily AI budget" in " ".join(result["problems"])
    assert service.list_batches() == []


def test_duplicate_primary_is_protected_and_supplemental_is_allowed(repository: RepositoryService) -> None:
    service = ConceptGeneratorService(repository, ProductionTestProvider())
    enable(service)
    worker = scheduler(service)
    when = datetime(2026, 8, 6, 8, 0, tzinfo=ZoneInfo("America/New_York"))
    worker.run_due(when)
    assert worker.run_due(when + timedelta(minutes=1)) is None
    supplemental = service.generate_daily_concept_batch(when.date(), source="manual", mode="supplemental", execute=False)
    assert supplemental["batch"]["primary"] is False
    assert sum(item["primary"] for item in service.list_batches()) == 1


def test_current_day_catch_up_works_on_wake_and_app_start(repository: RepositoryService) -> None:
    zone = ZoneInfo("America/New_York")
    service = ConceptGeneratorService(repository, ProductionTestProvider())
    enable(service, catch_up_on_wake=True)
    result = scheduler(service).run_due(datetime(2026, 8, 6, 9, 37, tzinfo=zone), trigger="worker")
    assert result and result["batch"]["date"] == "2026-08-06"
    assert result["batch"]["generation_source"] == "catch_up"

    second_repository = repository.__class__(repository.settings)
    second_repository.write_json("data/content_batches.json", [])
    second_repository.write_json("data/content_concepts.json", [])
    second_repository.write_json("app-data/concept_generator_scheduler_state.json", {})
    second = ConceptGeneratorService(second_repository, ProductionTestProvider())
    enable(second, catch_up_on_start=True)
    started = scheduler(second).run_due(datetime(2026, 8, 7, 10, 0, tzinfo=zone), trigger="app_start")
    assert started and started["batch"]["date"] == "2026-08-07"
    assert all(batch["date"] != "2026-08-06" for batch in second.list_batches())


def test_fixture_provider_is_never_used_by_production_schedule(repository: RepositoryService) -> None:
    service = ConceptGeneratorService(repository, DevelopmentFixtureProvider())
    enable(service)
    result = scheduler(service).run_due(datetime(2026, 8, 6, 8, 0, tzinfo=ZoneInfo("America/New_York")))
    assert result and result["status"] == "skipped"
    assert "fixtures" in " ".join(result["problems"]).lower()
    assert service.list_concepts() == []


def test_two_minute_test_uses_worker_path_and_saves_supplemental(repository: RepositoryService) -> None:
    zone = ZoneInfo("America/New_York")
    service = ConceptGeneratorService(repository, ProductionTestProvider())
    enable(service)
    worker = scheduler(service)
    now = datetime(2026, 8, 6, 12, 0, tzinfo=zone)
    scheduled = worker.schedule_test(now)
    assert scheduled["scheduled"] is True
    assert worker.run_due(now + timedelta(seconds=119), trigger="worker") is None
    result = worker.run_due(now + timedelta(minutes=2), trigger="worker")
    assert result and result["batch"]["generation_source"] == "scheduler_test"
    assert result["batch"]["primary"] is False
    assert worker.state(now + timedelta(minutes=3))["test_status"] == "Succeeded"
    concepts = [item for item in service.list_concepts() if item["batch_id"] == result["batch"]["id"]]
    assert len(concepts) == 30
    events = service.runtime.events(result["run"]["id"])
    assert any(event["kind"] == "scheduler" for event in events)
    assert events[-1]["kind"] == "complete"


def test_launchagent_uses_current_repository_and_virtualenv(repository: RepositoryService, monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    python = repository.root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr("app.backend.services.concept_generator_background_service.shutil.which", lambda _: "/bin/launchctl")
    monkeypatch.setattr(ConceptGeneratorBackgroundService, "_launchctl", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(ConceptGeneratorBackgroundService, "_label_loaded", staticmethod(lambda _: True))
    background = ConceptGeneratorBackgroundService(repository)
    result = background.install()
    payload = plistlib.loads(background.plist_path.read_bytes())
    assert payload["ProgramArguments"] == [str(python), "-m", "app.backend.workers.concept_generator_worker"]
    assert payload["WorkingDirectory"] == str(repository.root)
    assert payload["EnvironmentVariables"]["DINKLY_REPOSITORY_ROOT"] == str(repository.root)
    assert result["installed"] is True


def test_restarted_worker_recovers_interrupted_scheduled_run(repository: RepositoryService) -> None:
    service = ConceptGeneratorService(repository, ProductionTestProvider())
    enable(service)
    worker = scheduler(service)
    started = service.generate_daily_concept_batch(
        datetime(2026, 8, 6, tzinfo=UTC).date(), source="scheduled", execute=False
    )
    worker._save(last_status="Running", last_run_id=started["run"]["id"], last_attempted_date="2026-08-06")
    recovered = worker.recover_interrupted_run()
    assert recovered and recovered["status"] == "Failed"
    assert worker.state(datetime(2026, 8, 6, 9, 0, tzinfo=ZoneInfo("America/New_York")))["last_status"] == "Failed"
    assert any(event["kind"] == "recovery" for event in service.runtime.events(started["run"]["id"]))
