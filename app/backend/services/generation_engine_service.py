from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.backend.models.generation_engine import (
    GenerationRequest,
    ImageGenerationSettings,
    ModelCompareRequest,
    RepairRequest,
    StoryBrief,
    StoryBriefRequest,
)
from app.backend.models.prompts import PromptGenerateRequest
from app.backend.models.reviews import EditPromptRequest
from app.backend.providers.image_provider import GeminiImageProvider, ImageProvider, ImageProviderError
from app.backend.services.agent_runtime_service import AgentRuntimeService
from app.backend.services.agent_visual_state_service import AgentVisualStateService
from app.backend.services.art_review_service import ArtReviewService
from app.backend.services.generation_export_service import ExportArtifact, GenerationExportService
from app.backend.services.image_model_registry import ImageModelRegistry
from app.backend.services.memory_service import AgentContextBuilder
from app.backend.services.prompt_service import PromptService
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.secrets_service import SecretsService
from app.backend.services.story_library_service import StoryLibraryService

TERMINAL_STATUSES = {"approved", "rejected", "failed", "cancelled"}
SETTINGS_PATH = "app-data/generation-engine/settings.json"
PROMPTS_PATH = "app-data/generation-engine/prompts.json"


class GenerationCancellationRequested(Exception):
    """Raised only after the persisted run has stopped at a safe checkpoint."""


class GenerationEngineService:
    _lock = threading.RLock()

    def __init__(
        self,
        repository: RepositoryService,
        prompt_service: PromptService,
        *,
        provider_factory: Callable[[], ImageProvider] | None = None,
    ) -> None:
        self.repository = repository
        self.prompt_service = prompt_service
        self.story_library = StoryLibraryService(repository)
        self.secrets = SecretsService(repository)
        self.registry = ImageModelRegistry()
        self.exports = GenerationExportService(repository, self.registry)
        self.runtime = AgentRuntimeService(repository)
        self.art_review = ArtReviewService(repository)
        self.agent_visual = AgentVisualStateService(repository)
        self.provider_factory = provider_factory or self._default_provider
        self.runs_dir = repository.path("app-data/generation-engine/runs")
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def build_brief(self, request: StoryBriefRequest) -> dict[str, Any]:
        if request.story_brief:
            brief = self._brief_from_record(request.story_brief)
            source = "provided_story_brief"
        elif request.story_id:
            record = self.story_library.get(request.story_id)
            if not record:
                raise RepositoryError("Story Library record not found")
            brief = self._brief_from_record(record)
            source = "story_library"
        else:
            left, right = self._parse_concept(request.concept_text or "")
            match = self.story_library.find_by_titles(left, right)
            brief = self._brief_from_record(match) if match else self._generic_brief(left, right)
            source = "story_library_match" if match else "concept_text"
        return {"story_brief": brief.model_dump(mode="json"), "source": source}

    def start(self, request: GenerationRequest) -> dict[str, Any]:
        settings = self.settings()
        references = self.reference_manifest(request.story_brief)
        allow_pro = request.confirm_pro and (
            request.model_selection_mode == "pro" or settings.automatic_pro_usage
        )
        key, reason = self.registry.select(
            request.story_brief,
            request.model_selection_mode,
            reference_count=len(references["paths"]),
            allow_pro=allow_pro,
        )
        estimate = self._preflight(key, request.candidate_count, confirm_pro=request.confirm_pro)
        now = datetime.now(UTC).isoformat()
        run_id = f"generation-{uuid.uuid4().hex[:12]}"
        prompt_record = self._compile_prompt(request.story_brief)
        run = {
            "id": run_id,
            "concept_id": request.story_brief.concept_id or request.story_brief.id,
            "concept_text": self._concept_label(request.story_brief),
            "story_brief": request.story_brief.model_dump(mode="json"),
            "story_format": request.story_brief.format,
            "status": "compiling",
            "provider": "google_gemini",
            "source_channel": "web",
            "source_task_id": None,
            "model_selection_mode": request.model_selection_mode,
            "selected_model": key,
            "selection_reason": reason,
            "candidate_count": request.candidate_count,
            "candidate_ids": [],
            "candidates": [],
            "selected_candidate_id": None,
            "final_asset_id": None,
            "final_asset_url": None,
            "prompt_id": prompt_record["prompt_id"],
            "prompt_record": prompt_record,
            "prompt_template_version": prompt_record["template_version"],
            "character_rule_version": prompt_record["character_rule_version"],
            "failure_rule_version": prompt_record["failure_rule_version"],
            "brain_refs_used": prompt_record["brain_refs_used"],
            "memory_refs_used": prompt_record["memory_refs_used"],
            "image_model": key,
            "image_model_tier": self.registry.get(key)["power_label"],
            "dinko_reference_version": references["dinko_reference_version"],
            "dinka_reference_version": references["dinka_reference_version"],
            "reference_paths": references["relative_paths"],
            "started_at": now,
            "completed_at": None,
            "approved_at": None,
            "runtime_ms": None,
            "estimated_cost": estimate,
            "reported_cost": None,
            "aspect_ratio": request.aspect_ratio,
            "error": None,
            "warnings": self._budget_warnings(estimate),
            "comparison": False,
        }
        self._save_run(run)
        self._emit_stage(
            run_id,
            "story",
            "active",
            "Expanding your concept into a DINKLY scene…",
        )
        self._emit(run_id, "brief", "Story brief loaded.")
        self._emit_stage(run_id, "story", "complete", "Story Brief ready.")
        self._emit_stage(
            run_id,
            "compile",
            "active",
            "Applying character locks and scene rules…",
        )
        self._emit(run_id, "prompt", "Prompt recipe compiled.")
        self._emit_stage(run_id, "compile", "complete", "Production prompt compiled.")
        self._emit_stage(
            run_id,
            "references",
            "active",
            "Loading official Dinko and Dinka references…",
        )
        for label in references["labels"]:
            self._emit(run_id, "reference", f"{label} reference loaded.")
        self._emit_stage(run_id, "references", "complete", "Official character references loaded.")
        model = self.registry.get(key)
        self._emit(
            run_id,
            "model",
            f"Selected {model['power_label']}: {model['display_name']}.",
            {"reason": reason, "model": self._model_presentation(key, expose_id=False)},
        )
        self._emit_stage(
            run_id,
            "generate",
            "active",
            f"Preparing {request.candidate_count} candidates with {model['display_name']}…",
            model=self._model_presentation(key, expose_id=False),
            completed=0,
            total=request.candidate_count,
        )
        return self.get(run_id)

    def execute(
        self,
        run_id: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        run = self._load_run(run_id)
        cancelled = should_cancel or (lambda: False)
        started = datetime.now(UTC)
        provider = self.provider_factory()
        model = self.registry.get(run["selected_model"])
        references = [self.repository.path(path) for path in run["reference_paths"]]
        run["status"] = "generating"
        self._save_run(run)
        successful = 0
        for index in range(run["candidate_count"]):
            if cancelled():
                self._cancel_run(run_id, f"Candidate {index} of {run['candidate_count']}")
            if self._load_run(run_id).get("status") == "rejected":
                self._emit_stage(run_id, "generate", "warning", "Generation cancelled; completed candidates were preserved.")
                self._emit(run_id, "rejection", "Generation cancelled. Completed candidates were preserved.")
                return
            label = chr(65 + index)
            self._emit_stage(
                run_id,
                "generate",
                "active",
                f"Generating Candidate {label} with {model['display_name']}.",
                candidate=label,
                candidate_status="working",
                completed=index,
                total=run["candidate_count"],
                model=self._model_presentation(run["selected_model"], expose_id=False),
            )
            self._emit(
                run_id,
                "generation",
                f"Generating Candidate {label} with {model['display_name']}.",
                {"candidate": label, "model": model["display_name"]},
            )
            try:
                result = provider.generate(
                    prompt=run["prompt_record"]["prompt"],
                    model_key=run["selected_model"],
                    reference_paths=references,
                    aspect_ratio=run["aspect_ratio"],
                    image_size=model["default_resolution"],
                )
                # Gemini does not expose remote cancellation for this request.
                # If cancellation arrived while it was in flight, discard the
                # response before any asset or candidate record is written.
                if cancelled():
                    self._cancel_run(run_id, f"Before Candidate {label} was saved")
                candidate = self._persist_candidate(run, result, index=index, label=label)
                run["candidates"].append(candidate)
                run["candidate_ids"].append(candidate["id"])
                successful += 1
                self._emit(
                    run_id,
                    "candidate",
                    f"Candidate {label} generated with {model['display_name']}.",
                    {
                        "candidate_id": candidate["id"],
                        "candidate": label,
                        "completed": index + 1,
                        "total": run["candidate_count"],
                        "model": model["display_name"],
                    },
                )
                self._emit_stage(
                    run_id,
                    "generate",
                    "active",
                    f"Candidate {label} received. {index + 1} / {run['candidate_count']} complete.",
                    candidate=label,
                    candidate_status="complete",
                    completed=index + 1,
                    total=run["candidate_count"],
                    model=self._model_presentation(run["selected_model"], expose_id=False),
                )
                if on_progress:
                    on_progress({"stage": "generate", "completed": index + 1, "total": run["candidate_count"], "candidate": label})
            except ImageProviderError as exc:
                if cancelled():
                    self._cancel_run(run_id, f"During Candidate {label}")
                failure = self._failed_candidate(run, index=index, label=label, error=exc)
                run["candidates"].append(failure)
                run["candidate_ids"].append(failure["id"])
                run["warnings"].append(f"Candidate {label}: {exc}")
                self._emit(run_id, "warning", f"Candidate {label} failed: {exc}", {"code": exc.code}, level="warning")
                self._emit_stage(
                    run_id,
                    "generate",
                    "warning",
                    f"Candidate {label} failed: {exc}",
                    candidate=label,
                    candidate_status="failed",
                    completed=index + 1,
                    total=run["candidate_count"],
                    code=exc.code,
                )
            self._save_run(run)
            if cancelled():
                self._cancel_run(run_id, f"Candidate {index + 1} of {run['candidate_count']}")
        if not successful:
            run["status"] = "failed"
            run["error"] = "All candidate requests failed. Successful prior runs and assets were preserved."
            run["completed_at"] = datetime.now(UTC).isoformat()
            run["runtime_ms"] = int((datetime.now(UTC) - started).total_seconds() * 1000)
            self._save_run(run)
            self._emit_stage(run_id, "generate", "failed", "All candidate requests failed.")
            self._emit(run_id, "complete", "All candidate requests failed.", level="warning")
            return
        if self._load_run(run_id).get("status") == "rejected":
            self._emit(run_id, "rejection", "Generation cancelled before QA. Completed candidates were preserved.")
            return
        if cancelled():
            self._cancel_run(run_id, "Before layout")
        run["status"] = "reviewing"
        self._save_run(run)
        self._emit_stage(
            run_id,
            "generate",
            "complete" if successful == run["candidate_count"] else "warning",
            f"{successful} / {run['candidate_count']} candidates generated.",
            completed=successful,
            total=run["candidate_count"],
        )
        self._emit_stage(run_id, "layout", "active", "Applying the final DINKLY 80/20 composition.")
        if on_progress:
            on_progress({"stage": "layout", "completed": successful, "total": run["candidate_count"]})
        try:
            for candidate in run["candidates"]:
                if cancelled():
                    self._save_run(run)
                    self._cancel_run(run_id, "During layout")
                if not candidate.get("image_path"):
                    continue
                source = self.repository.path(candidate["image_path"])
                target = source.with_name(f"{source.stem}-final.png")
                final_path, layout = self._compose_final_layout(run, source, target=target)
                candidate["original_image_path"] = candidate["image_path"]
                candidate["final_image_path"] = self.repository.relative(final_path)
                candidate["final_asset_url"] = self._asset_url(final_path)
                candidate["final_layout"] = layout
            self._save_run(run)
        except RepositoryError as exc:
            run["status"] = "failed"
            run["error"] = str(exc)
            run["completed_at"] = datetime.now(UTC).isoformat()
            self._save_run(run)
            self._emit_stage(run_id, "layout", "failed", str(exc))
            self._emit(run_id, "complete", f"Final layout failed: {exc}", level="warning")
            return
        self._emit_stage(run_id, "layout", "complete", "Validated 80/20 final layouts applied to the generated candidates.")
        qa_total = len([candidate for candidate in run["candidates"] if candidate.get("image_path")])
        self._emit_stage(
            run_id,
            "qa",
            "active",
            "Checking character consistency and scene accuracy…",
            completed=0,
            total=qa_total,
        )
        self._emit(run_id, "qa", "Starting QA.")
        if on_progress:
            on_progress({"stage": "qa", "completed": 0, "total": qa_total})
        qa_completed = 0
        for candidate in run["candidates"]:
            if candidate.get("image_path"):
                if cancelled():
                    self._cancel_run(run_id, f"Before QA Candidate {candidate['label']}")
                self._emit_stage(
                    run_id,
                    "qa",
                    "active",
                    f"Candidate {candidate['label']} checking…",
                    candidate=candidate["label"],
                    candidate_status="working",
                    completed=qa_completed,
                    total=qa_total,
                )
                if on_progress:
                    on_progress({"stage": "qa", "completed": qa_completed, "total": qa_total, "candidate": candidate["label"]})
                self._qa_candidate(run, candidate, provider)
                if cancelled():
                    self._cancel_run(run_id, f"During QA Candidate {candidate['label']}")
                qa_completed += 1
                self._save_run(run)
                self._emit_stage(
                    run_id,
                    "qa",
                    "active",
                    f"Candidate {candidate['label']} checked.",
                    candidate=candidate["label"],
                    candidate_status="complete",
                    qa_status=candidate["qa_status"],
                    completed=qa_completed,
                    total=qa_total,
                )
        if cancelled():
            self._cancel_run(run_id, "Before approval preparation")
        self._rank(run)
        recommended = next((candidate for candidate in run["candidates"] if candidate.get("recommended")), None)
        if recommended:
            run["final_image_path"] = recommended.get("final_image_path")
            run["final_asset_url"] = recommended.get("final_asset_url")
        run["status"] = "awaiting_human"
        run["completed_at"] = datetime.now(UTC).isoformat()
        run["runtime_ms"] = int((datetime.now(UTC) - started).total_seconds() * 1000)
        run["reported_cost"] = self._candidate_cost(run)
        self._save_run(run)
        self._emit_stage(
            run_id,
            "qa",
            "complete",
            f"QA complete for {qa_completed} candidates.",
            completed=qa_completed,
            total=qa_total,
        )
        self._emit_stage(run_id, "repair", "skipped", "No repair requested.")
        self._emit_stage(run_id, "human_review", "active", "Ready for your approval.")
        if on_progress:
            on_progress({"stage": "approval", "completed": qa_completed, "total": qa_total})
        self._emit(run_id, "checkpoint", "Candidates ready for the human checkpoint.")

    def get(self, run_id: str) -> dict[str, Any]:
        run = self._load_run(run_id)
        settings = self.settings()
        if run.get("selected_model"):
            run["selected_model_info"] = self._model_presentation(run["selected_model"], expose_id=False)
        # Runs created before model power metadata was introduced only stored the
        # registry key on each candidate. Hydrate those legacy records at read
        # time so History remains compatible without rewriting production data.
        for candidate in run.get("candidates", []):
            model_key = candidate.get("model") or run.get("selected_model")
            if not model_key:
                continue
            try:
                model_info = self._model_presentation(model_key, expose_id=False)
            except RepositoryError:
                continue
            candidate.setdefault("model_display_name", model_info["display_name"])
            candidate.setdefault("model_power_label", model_info["power_label"])
            candidate.setdefault("model_power_level", model_info["power_level"])
            candidate.setdefault("model_description", model_info["description"])
            candidate.setdefault("model_cost_tier", model_info["cost_tier"])
        if run.get("comparison_models"):
            run["comparison_model_info"] = [
                self._model_presentation(key, expose_id=False) for key in run["comparison_models"]
            ]
        selected = next(
            (item for item in run.get("candidates", []) if item.get("id") == run.get("selected_candidate_id")),
            {},
        )
        run["comic_asset_count"] = len(
            run.get("comic_asset_paths") or selected.get("comic_asset_paths") or []
        )
        if settings.demo_mode and not settings.developer_mode:
            run["prompt_record"] = {
                key: value for key, value in run["prompt_record"].items() if key != "prompt"
            }
            run["generation_recipe"] = [
                "Character references loaded",
                "Scene template selected",
                "Character locks applied",
                "Scene protections applied",
                "Background rules applied",
                "Prop protections applied",
                "Generation recipe ready",
            ]
        return run

    def record_source(self, run_id: str, *, source_channel: str, source_task_id: str | None) -> dict[str, Any]:
        """Attach origin metadata without creating a second generation history."""
        run = self._load_run(run_id)
        run["source_channel"] = source_channel
        run["source_task_id"] = source_task_id
        self._save_run(run)
        return self.get(run_id)

    def record_slack_delivery(self, run_id: str, *, status: str, issue: str | None = None) -> dict[str, Any]:
        """Persist sanitized Slack delivery metadata on the canonical generation run."""
        if status not in {"image_sent", "link_sent", "failed"}:
            raise RepositoryError("Unknown Slack delivery status")
        run = self._load_run(run_id)
        run["slack_delivery_status"] = status
        if issue:
            run["slack_delivery_issue"] = issue
        else:
            run.pop("slack_delivery_issue", None)
        self._save_run(run)
        return self.get(run_id)

    def download_final(
        self,
        run_id: str,
        output_format: str,
        *,
        comic_number: int | None = None,
    ) -> ExportArtifact:
        return self.exports.final(self.get(run_id), output_format, comic_number=comic_number)

    def download_candidates(self, run_id: str) -> ExportArtifact:
        return self.exports.candidates(self.get(run_id))

    def download_qa(self, run_id: str) -> ExportArtifact:
        return self.exports.qa_report(self.get(run_id))

    def download_summary(self, run_id: str) -> ExportArtifact:
        return self.exports.summary(self.get(run_id))

    def download_all_comics(self, run_id: str) -> ExportArtifact:
        return self.exports.all_comics(self.get(run_id))

    def list_candidates(self, run_id: str) -> list[dict[str, Any]]:
        return self.get(run_id)["candidates"]

    def events(self, run_id: str, after: str | None = None) -> list[dict[str, Any]]:
        self._load_run(run_id)
        return self.runtime.events(run_id, after)

    def select_candidate(self, candidate_id: str) -> dict[str, Any]:
        run, candidate = self._find_candidate(candidate_id)
        if not candidate.get("image_path"):
            raise RepositoryError("A failed candidate cannot be selected")
        run["selected_candidate_id"] = candidate_id
        for item in run["candidates"]:
            item["selected"] = item["id"] == candidate_id
        self._save_run(run)
        self._emit(run["id"], "selection", f"Candidate {candidate['label']} selected.")
        return self.get(run["id"])

    def qa_candidate(self, candidate_id: str, manual_findings: list[dict[str, Any]] | None = None, *, should_cancel: Callable[[], bool] | None = None) -> dict[str, Any]:
        run, candidate = self._find_candidate(candidate_id)
        if should_cancel and should_cancel():
            self._cancel_run(run["id"], "Before QA")
        if manual_findings is not None:
            candidate["qa_findings"] = manual_findings
            candidate["qa_status"] = self._qa_status(manual_findings)
            candidate["qa_summary"] = self._qa_summary(candidate["qa_status"], manual_findings)
        else:
            self._qa_candidate(run, candidate, self.provider_factory())
        if should_cancel and should_cancel():
            self._cancel_run(run["id"], "During QA")
        self._rank(run)
        self._save_run(run)
        return candidate

    def retry_candidate(self, candidate_id: str, *, confirm_pro: bool = False) -> dict[str, Any]:
        run, candidate = self._find_candidate(candidate_id)
        if candidate.get("image_path") or not candidate.get("error", {}).get("retryable"):
            raise RepositoryError("Only a retryable failed candidate can be retried")
        model_key = candidate["model"]
        self._preflight(model_key, 1, confirm_pro=confirm_pro)
        retries = sum(1 for item in run["candidates"] if item.get("retry_parent_id") == candidate_id) + 1
        provider = self.provider_factory()
        model = self.registry.get(model_key)
        self._emit_stage(
            run["id"],
            "generate",
            "active",
            f"Retrying Candidate {candidate['label']} with {model['display_name']}.",
            candidate=candidate["label"],
            candidate_status="working",
            model=self._model_presentation(model_key, expose_id=False),
        )
        try:
            result = provider.generate(
                prompt=run["prompt_record"]["prompt"],
                model_key=model_key,
                reference_paths=[self.repository.path(path) for path in run["reference_paths"]],
                aspect_ratio=run["aspect_ratio"],
                image_size=self.registry.get(model_key)["default_resolution"],
            )
        except ImageProviderError as exc:
            candidate.setdefault("retry_failures", []).append(
                {
                    "code": exc.code,
                    "message": str(exc),
                    "retryable": exc.retryable,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            self._save_run(run)
            self._emit_stage(
                run["id"],
                "generate",
                "warning",
                f"Candidate {candidate['label']} retry failed: {exc}",
                candidate=candidate["label"],
                candidate_status="failed",
                code=exc.code,
            )
            raise RepositoryError(f"Candidate retry failed: {exc}") from exc
        retried = self._persist_candidate(
            run,
            result,
            index=len(run["candidates"]),
            label=f"{candidate['label']} · Retry {retries}",
            model_key=model_key,
        )
        retried["retry_parent_id"] = candidate_id
        run["candidates"].append(retried)
        run["candidate_ids"].append(retried["id"])
        self._qa_candidate(run, retried, provider)
        self._rank(run)
        run["status"] = "awaiting_human"
        run["estimated_cost"] = round(
            float(run.get("estimated_cost") or 0) + float(retried.get("estimated_cost") or 0), 4
        )
        run["reported_cost"] = self._candidate_cost(run)
        self._save_run(run)
        self._emit_stage(
            run["id"],
            "generate",
            "complete",
            f"Candidate {candidate['label']} retry generated with {model['display_name']}.",
            candidate=retried["label"],
            candidate_status="complete",
            model=self._model_presentation(model_key, expose_id=False),
        )
        self._emit_stage(
            run["id"],
            "qa",
            "complete",
            f"Candidate {retried['label']} checked.",
            candidate=retried["label"],
            candidate_status="complete",
            qa_status=retried["qa_status"],
            completed=1,
            total=1,
        )
        self._emit_stage(run["id"], "human_review", "active", "Ready for your approval.")
        self._emit(run["id"], "candidate", f"Candidate {candidate['label']} retry received and reviewed.")
        return self.get(run["id"])

    def repair(self, candidate_id: str, request: RepairRequest, *, should_cancel: Callable[[], bool] | None = None) -> dict[str, Any]:
        run, candidate = self._find_candidate(candidate_id)
        if should_cancel and should_cancel():
            self._cancel_run(run["id"], "Before repair")
        if not candidate.get("image_path"):
            raise RepositoryError("Only a generated candidate can be repaired")
        failures = request.failures or [
            str(item.get("check")) for item in candidate.get("qa_findings", []) if item.get("status") != "Pass"
        ]
        if not failures:
            raise RepositoryError("No repair issues were selected")
        repair_number = max(
            int(candidate.get("repair_number") or 0) + 1,
            1 + sum(1 for item in run["candidates"] if item.get("repair_parent_id") == candidate_id),
        )
        mode = request.model_selection
        if mode == "same":
            model_key = candidate["model"]
        else:
            model_key, _ = self.registry.select(
                StoryBrief.model_validate(run["story_brief"]),
                mode,
                reference_count=len(run["reference_paths"]),
                repair_attempt=repair_number,
                allow_pro=request.confirm_pro,
            )
        if model_key == "nano_banana_pro" and not request.confirm_pro:
            raise RepositoryError("Nano Banana Pro repair requires explicit budget confirmation")
        self._preflight(model_key, 1, confirm_pro=request.confirm_pro)
        edit_recipe = self.art_review.edit_prompt(
            EditPromptRequest(
                failures=failures,
                notes=request.notes,
                unchanged="Keep the entire image unchanged outside the named issue regions.",
                edit_attempts=repair_number - 1,
            )
        )
        run["status"] = "repairing"
        self._save_run(run)
        repair_model = self.registry.get(model_key)
        issue_label = failures[0] if len(failures) == 1 else f"{len(failures)} selected issues"
        self._emit_stage(
            run["id"],
            "repair",
            "active",
            f"Preparing edit for Candidate {candidate['label']}: {issue_label}.",
            candidate=candidate["label"],
            repair_step="preparing_edit",
            issue=issue_label,
            model=self._model_presentation(model_key, expose_id=False),
        )
        self._emit(
            run["id"],
            "repair",
            f"Repair {repair_number} started with {repair_model['display_name']}.",
        )
        provider = self.provider_factory()
        self._emit_stage(
            run["id"],
            "repair",
            "active",
            f"Submitting Candidate {candidate['label']} repair with {repair_model['display_name']}.",
            candidate=candidate["label"],
            repair_step="submitting_repair",
            issue=issue_label,
            model=self._model_presentation(model_key, expose_id=False),
        )
        try:
            result = provider.edit(
                prompt=edit_recipe["edit_prompt"],
                model_key=model_key,
                source_path=self.repository.path(candidate["image_path"]),
                reference_paths=[self.repository.path(path) for path in run["reference_paths"]],
                aspect_ratio=run["aspect_ratio"],
                image_size=self.registry.get(model_key)["default_resolution"],
            )
            if should_cancel and should_cancel():
                self._cancel_run(run["id"], "During repair provider request")
        except ImageProviderError as exc:
            failure = {
                "repair_number": repair_number,
                "model": model_key,
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
                "created_at": datetime.now(UTC).isoformat(),
            }
            candidate.setdefault("repair_failures", []).append(failure)
            run["status"] = "awaiting_human"
            run.setdefault("warnings", []).append(
                f"Repair {repair_number} failed; the original candidate was preserved."
            )
            self._save_run(run)
            self._emit(
                run["id"],
                "warning",
                f"Repair {repair_number} failed. The original candidate remains available.",
                failure,
                level="warning",
            )
            self._emit_stage(
                run["id"],
                "repair",
                "warning",
                f"Repair failed: {exc}. The original candidate remains available.",
                candidate=candidate["label"],
                repair_step="failed",
                issue=issue_label,
                code=exc.code,
            )
            self._emit_stage(run["id"], "human_review", "active", "Ready for your decision.")
            raise RepositoryError(f"Repair failed: {exc}") from exc
        self._emit_stage(
            run["id"],
            "repair",
            "active",
            f"Repair received for Candidate {candidate['label']}.",
            candidate=candidate["label"],
            repair_step="repair_received",
            issue=issue_label,
        )
        repaired = self._persist_candidate(
            run,
            result,
            index=len(run["candidates"]),
            label=f"{candidate['label']} · Repair {repair_number}",
            repair_parent_id=candidate_id,
            model_key=model_key,
            folder="repairs",
        )
        repaired["repair_prompt"] = edit_recipe["edit_prompt"]
        repaired["repair_number"] = repair_number
        run["candidates"].append(repaired)
        run["candidate_ids"].append(repaired["id"])
        self._save_run(run)
        self._emit_stage(
            run["id"],
            "repair",
            "active",
            "Running QA again…",
            candidate=repaired["label"],
            repair_step="running_qa",
            issue=issue_label,
        )
        self._emit_stage(
            run["id"],
            "qa",
            "active",
            f"Candidate {repaired['label']} checking…",
            candidate=repaired["label"],
            candidate_status="working",
            completed=0,
            total=1,
        )
        self._qa_candidate(run, repaired, provider)
        if should_cancel and should_cancel():
            self._cancel_run(run["id"], "During repair QA")
        self._rank(run)
        run["selected_candidate_id"] = repaired["id"]
        run["status"] = "awaiting_human"
        run["estimated_cost"] = round(float(run.get("estimated_cost") or 0) + float(repaired.get("estimated_cost") or 0), 4)
        run["reported_cost"] = self._candidate_cost(run)
        self._save_run(run)
        self._emit_stage(
            run["id"],
            "qa",
            "complete",
            f"Candidate {repaired['label']} checked after repair.",
            candidate=repaired["label"],
            candidate_status="complete",
            qa_status=repaired["qa_status"],
            completed=1,
            total=1,
        )
        self._emit_stage(
            run["id"],
            "repair",
            "complete",
            f"Repair {repair_number} completed and re-checked.",
            candidate=repaired["label"],
            repair_step="complete",
            issue=issue_label,
        )
        self._emit_stage(run["id"], "human_review", "active", "Ready for your approval.")
        self._emit(run["id"], "repair", f"Repair {repair_number} received and re-reviewed.")
        return self.get(run["id"])

    def approve(self, run_id: str, approved_by: str) -> dict[str, Any]:
        run = self._load_run(run_id)
        selected = next(
            (item for item in run["candidates"] if item["id"] == run.get("selected_candidate_id")), None
        )
        if not selected or not selected.get("image_path"):
            raise RepositoryError("Select a generated candidate before approval")
        source = self.repository.path(selected["image_path"])
        final_path, layout = self._compose_final_layout(run, source)
        now = datetime.now(UTC).isoformat()
        run.update(
            {
                "status": "approved",
                "approved_at": now,
                "completed_at": now,
                "approved_by": approved_by,
                "final_asset_id": f"asset-{uuid.uuid4().hex[:12]}",
                "final_asset_url": self._asset_url(final_path),
                "original_image_path": self.repository.relative(source),
                "final_image_path": self.repository.relative(final_path),
                "final_layout": layout,
            }
        )
        self._save_run(run)
        self._mark_used(run)
        self._emit_stage(run_id, "human_review", "complete", "Comic approved by the human reviewer.")
        self._emit(run_id, "approval", "Comic approved and saved to History.")
        return self.get(run_id)

    def _compose_final_layout(
        self,
        run: dict[str, Any],
        source: Path,
        *,
        target: Path | None = None,
    ) -> tuple[Path, dict[str, Any]]:
        """Place the original at x=0 and add an exact 20% final-canvas extension on the right."""
        try:
            from PIL import Image
        except ImportError:
            return self._compose_final_layout_macos(run, source, target=target)

        try:
            with Image.open(source) as opened:
                image = opened.convert("RGB")
        except Exception as exc:
            raise RepositoryError("The selected image could not be opened for final layout") from exc

        width, height = image.size
        if width <= 0 or height <= 0:
            raise RepositoryError("The selected image has invalid dimensions")
        final_width = math.ceil(width / 0.8)
        extension_width = final_width - width
        if extension_width <= 0 or width / final_width != 0.8:
            raise RepositoryError("The 80/20 final layout dimensions could not be resolved exactly")

        background, source_name = self._resolve_layout_background(run, image)
        final = Image.new("RGB", (final_width, height), background)
        final.paste(image, (0, 0))
        self._validate_final_layout(image, final, background)

        final_path = target or self._run_dir(str(run["id"])) / "final.png"
        final.save(final_path, format="PNG", optimize=True)
        return final_path, {
            "mode": "extend_right_80_20",
            "original_width": width,
            "original_height": height,
            "final_width": final_width,
            "final_height": height,
            "extension_width": extension_width,
            "original_share": 0.8,
            "extension_share": 0.2,
            "anchor_x": 0,
            "background_rgb": list(background),
            "background_source": source_name,
            "validated": True,
        }

    def _compose_final_layout_macos(
        self,
        run: dict[str, Any],
        source: Path,
        *,
        target: Path | None,
    ) -> tuple[Path, dict[str, Any]]:
        swift = Path("/usr/bin/swift")
        helper = Path(__file__).resolve().parents[3] / "scripts" / "compose_final_layout.swift"
        if not swift.is_file() or not helper.is_file():
            raise RepositoryError("Final layout requires Pillow, or the bundled macOS layout helper")
        final_path = target or self._run_dir(str(run["id"])) / "final.png"
        brief = run.get("story_brief") or {}
        manual = self._parse_color(run.get("layout_background_color") or brief.get("layout_background_color"))
        attempts: list[tuple[tuple[int, int, int] | None, str]] = [(manual, "manual_override")] if manual else [(None, "detected_perimeter")]
        fallback = self._parse_color(brief.get("background_color"))
        if not manual and fallback:
            attempts.append((fallback, "story_brief"))
        last_error = "Final layout failed"
        for color, source_name in attempts:
            value = "-" if color is None else "#" + "".join(f"{channel:02x}" for channel in color)
            completed = subprocess.run(
                [str(swift), "-module-cache-path", "/tmp/dinkly-swift-module-cache", str(helper), str(source), str(final_path), value],
                capture_output=True,
                check=False,
                text=True,
                timeout=120,
                env={
                    **os.environ,
                    "SWIFT_MODULECACHE_PATH": "/tmp/dinkly-swift-module-cache",
                    "CLANG_MODULE_CACHE_PATH": "/tmp/dinkly-clang-module-cache",
                },
            )
            if completed.returncode != 0:
                last_error = completed.stderr.strip() or last_error
                continue
            try:
                payload = json.loads(completed.stdout)
                background = tuple(int(channel) for channel in payload["background"])
                width, height, final_width = int(payload["width"]), int(payload["height"]), int(payload["final_width"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RepositoryError("Final layout helper returned invalid validation data") from exc
            return final_path, {
                "mode": "extend_right_80_20", "original_width": width, "original_height": height,
                "final_width": final_width, "final_height": height, "extension_width": final_width - width,
                "original_share": 0.8, "extension_share": 0.2, "anchor_x": 0,
                "background_rgb": list(background), "background_source": source_name, "validated": True,
            }
        raise RepositoryError(f"Final layout failed: {last_error}")

    def _resolve_layout_background(self, run: dict[str, Any], image: Any) -> tuple[tuple[int, int, int], str]:
        brief = run.get("story_brief") or {}
        override = run.get("layout_background_color") or brief.get("layout_background_color")
        parsed = self._parse_color(override)
        if parsed:
            return parsed, "manual_override"

        width, height = image.size
        perimeter = []
        for x in range(width):
            perimeter.extend((image.getpixel((x, 0)), image.getpixel((x, height - 1))))
        for y in range(1, height - 1):
            perimeter.extend((image.getpixel((0, y)), image.getpixel((width - 1, y))))
        if perimeter:
            from collections import Counter

            detected, count = Counter(perimeter).most_common(1)[0]
            if count / len(perimeter) >= 0.12:
                return tuple(int(channel) for channel in detected), "detected_perimeter"

        parsed = self._parse_color(brief.get("background_color"))
        if parsed:
            return parsed, "story_brief"
        raise RepositoryError("Final layout could not determine a safe non-white background color")

    @staticmethod
    def _parse_color(value: Any) -> tuple[int, int, int] | None:
        if not value:
            return None
        text = str(value).strip().lower()
        if re.fullmatch(r"#[0-9a-f]{6}", text):
            return tuple(int(text[index : index + 2], 16) for index in (1, 3, 5))
        colors = {
            "warm cream": (249, 232, 194), "pastel peach": (246, 196, 175),
            "dusty blue": (177, 205, 221), "soft lavender": (199, 187, 235),
            "mint": (190, 225, 206), "warm sage": (190, 205, 174),
            "butter yellow": (246, 225, 151), "dusty rose": (220, 176, 182),
            "warm sand": (223, 201, 166), "soft coral": (239, 166, 153),
            "powder blue": (177, 215, 239), "pistachio": (207, 224, 174),
            "blush pink": (242, 194, 201),
        }
        return colors.get(text)

    @staticmethod
    def _validate_final_layout(original: Any, final: Any, background: tuple[int, int, int]) -> None:
        original_width, original_height = original.size
        final_width, final_height = final.size
        if (final_width, final_height) != (original_width * 5 // 4, original_height):
            raise RepositoryError("Final layout validation failed: dimensions are not exact 80/20")
        if final.crop((0, 0, original_width, original_height)).tobytes() != original.tobytes():
            raise RepositoryError("Final layout validation failed: original image moved or changed")
        extension = final.crop((original_width, 0, final_width, final_height))
        if extension.getbbox() is None or set(extension.getdata()) != {background}:
            raise RepositoryError("Final layout validation failed: right extension is not a solid background")

    def download_original(self, run_id: str, *, candidate_id: str | None = None) -> ExportArtifact:
        return self.exports.original(self.get(run_id), candidate_id=candidate_id)

    def reject(self, run_id: str, reason: str | None) -> dict[str, Any]:
        run = self._load_run(run_id)
        run.update({"status": "rejected", "rejection_reason": reason, "completed_at": datetime.now(UTC).isoformat()})
        self._save_run(run)
        self._emit_stage(run_id, "human_review", "warning", "Generation run rejected by the human reviewer.")
        self._emit(run_id, "rejection", "Generation run rejected. Candidates remain in History.")
        return self.get(run_id)

    def cancel(self, run_id: str) -> dict[str, Any]:
        run = self._load_run(run_id)
        if run["status"] in TERMINAL_STATUSES | {"awaiting_human"}:
            return self.get(run_id)
        run.update(
            {
                "status": "rejected",
                "rejection_reason": "Cancelled by user",
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )
        self._save_run(run)
        self._emit_stage(run_id, "human_review", "warning", "Run cancelled; completed work remains saved.")
        self._emit(run_id, "rejection", "Cancellation requested. Completed candidates remain saved.")
        return self.get(run_id)

    def history(self) -> list[dict[str, Any]]:
        records = [
            self.get(Path(relative).parent.name)
            for relative in self.repository.list_json(
                "app-data/generation-engine/runs", suffix="/metadata.json"
            )
        ]
        return sorted(records, key=lambda item: item.get("started_at") or "", reverse=True)

    def compare_models(self, request: ModelCompareRequest) -> dict[str, Any]:
        if request.include_pro and not request.confirm_pro:
            raise RepositoryError("Pro comparison requires explicit cost confirmation")
        models = ["nano_banana_2_lite", "nano_banana_2"]
        if request.include_pro:
            models.append("nano_banana_pro")
        total_estimate = sum(float(self._default_provider().estimate_cost(model_key=key) or 0) for key in models)
        self._check_budget(total_estimate)
        if not self.secrets.get_gemini_api_key():
            raise RepositoryError("GEMINI_API_KEY is missing. Add it in Settings → Image Generation.")
        now = datetime.now(UTC).isoformat()
        run_id = f"generation-{uuid.uuid4().hex[:12]}"
        references = self.reference_manifest(request.story_brief)
        prompt_record = self._compile_prompt(request.story_brief)
        run = {
            "id": run_id,
            "concept_id": request.story_brief.concept_id or request.story_brief.id,
            "concept_text": self._concept_label(request.story_brief),
            "story_brief": request.story_brief.model_dump(mode="json"),
            "story_format": request.story_brief.format,
            "status": "generating",
            "provider": "google_gemini",
            "source_channel": "web",
            "source_task_id": None,
            "model_selection_mode": "comparison",
            "selected_model": None,
            "selection_reason": "Same story recipe across selected models.",
            "candidate_count": len(models),
            "candidate_ids": [],
            "candidates": [],
            "selected_candidate_id": None,
            "final_asset_id": None,
            "final_asset_url": None,
            "prompt_id": prompt_record["prompt_id"],
            "prompt_record": prompt_record,
            "prompt_template_version": prompt_record["template_version"],
            "character_rule_version": prompt_record["character_rule_version"],
            "failure_rule_version": prompt_record["failure_rule_version"],
            "brain_refs_used": prompt_record["brain_refs_used"],
            "memory_refs_used": prompt_record["memory_refs_used"],
            "image_model": models,
            "image_model_tier": "comparison",
            "dinko_reference_version": references["dinko_reference_version"],
            "dinka_reference_version": references["dinka_reference_version"],
            "reference_paths": references["relative_paths"],
            "started_at": now,
            "completed_at": None,
            "approved_at": None,
            "runtime_ms": None,
            "estimated_cost": round(total_estimate, 4),
            "reported_cost": None,
            "aspect_ratio": request.aspect_ratio,
            "error": None,
            "warnings": self._budget_warnings(total_estimate),
            "comparison": True,
            "comparison_models": models,
        }
        self._save_run(run)
        self._emit_stage(run_id, "story", "complete", "Story Brief ready for model comparison.")
        self._emit_stage(run_id, "compile", "complete", "Production prompt compiled.")
        self._emit_stage(run_id, "references", "complete", "Official character references loaded.")
        self._emit_stage(
            run_id,
            "generate",
            "active",
            "Preparing model comparison candidates…",
            completed=0,
            total=len(models),
        )
        self._emit(run_id, "comparison", "Model comparison queued.")
        return self.get(run_id)

    def execute_comparison(self, run_id: str) -> None:
        run = self._load_run(run_id)
        provider = self.provider_factory()
        references = [self.repository.path(path) for path in run["reference_paths"]]
        started = datetime.now(UTC)
        for index, model_key in enumerate(run["comparison_models"]):
            model = self.registry.get(model_key)
            self._emit_stage(
                run_id,
                "generate",
                "active",
                f"Generating {model['power_label']} candidate with {model['display_name']}.",
                candidate=model["power_label"],
                candidate_status="working",
                completed=index,
                total=len(run["comparison_models"]),
                model=self._model_presentation(model_key, expose_id=False),
            )
            self._emit(
                run_id,
                "comparison",
                f"Generating {model['power_label']} candidate with {model['display_name']}.",
            )
            try:
                result = provider.generate(
                    prompt=run["prompt_record"]["prompt"],
                    model_key=model_key,
                    reference_paths=references,
                    aspect_ratio=run["aspect_ratio"],
                    image_size=model["default_resolution"],
                )
                candidate = self._persist_candidate(
                    run, result, index=index, label=model["tier_label"], model_key=model_key
                )
                run["candidates"].append(candidate)
                run["candidate_ids"].append(candidate["id"])
                self._save_run(run)
                self._emit_stage(
                    run_id,
                    "qa",
                    "active",
                    f"Checking {model['power_label']} candidate…",
                    candidate=model["power_label"],
                    candidate_status="working",
                    completed=index,
                    total=len(run["comparison_models"]),
                )
                self._qa_candidate(run, candidate, provider)
                self._emit_stage(
                    run_id,
                    "qa",
                    "active",
                    f"{model['power_label']} candidate checked.",
                    candidate=model["power_label"],
                    candidate_status="complete",
                    qa_status=candidate["qa_status"],
                    completed=index + 1,
                    total=len(run["comparison_models"]),
                )
            except ImageProviderError as exc:
                run["candidates"].append(self._failed_candidate(run, index=index, label=model["tier_label"], error=exc, model_key=model_key))
                run["warnings"].append(f"{model['tier_label']}: {exc}")
                self._emit_stage(
                    run_id,
                    "generate",
                    "warning",
                    f"{model['power_label']} candidate failed: {exc}",
                    candidate=model["power_label"],
                    candidate_status="failed",
                    completed=index + 1,
                    total=len(run["comparison_models"]),
                )
            self._save_run(run)
        if any(item.get("image_path") for item in run["candidates"]):
            self._rank(run)
            run["status"] = "awaiting_human"
        else:
            run["status"] = "failed"
            run["error"] = "All comparison candidates failed."
        run["runtime_ms"] = int((datetime.now(UTC) - started).total_seconds() * 1000)
        run["completed_at"] = datetime.now(UTC).isoformat()
        run["reported_cost"] = self._candidate_cost(run)
        self._save_run(run)
        generated = len([item for item in run["candidates"] if item.get("image_path")])
        self._emit_stage(
            run_id,
            "generate",
            "complete" if generated == len(run["comparison_models"]) else "warning",
            f"{generated} / {len(run['comparison_models'])} comparison candidates generated.",
            completed=generated,
            total=len(run["comparison_models"]),
        )
        if generated:
            self._emit_stage(run_id, "qa", "complete", "Comparison candidate QA complete.")
            self._emit_stage(run_id, "repair", "skipped", "No repair requested.")
            self._emit_stage(run_id, "human_review", "active", "Ready for your approval.")
        else:
            self._emit_stage(run_id, "generate", "failed", "All comparison candidates failed.")
        self._emit(run_id, "comparison", "Model comparison complete.")

    def settings(self) -> ImageGenerationSettings:
        payload = self.repository.read_json(SETTINGS_PATH, {})
        return ImageGenerationSettings.model_validate(payload or {})

    def update_settings(self, settings: ImageGenerationSettings) -> dict[str, Any]:
        backup = self.repository.write_json(SETTINGS_PATH, settings.model_dump(mode="json"))
        return {"settings": settings.model_dump(mode="json"), "backup": backup}

    def provider_status(self, *, test: bool = False) -> dict[str, Any]:
        status = self.secrets.get_gemini_status()
        if test and status["configured"]:
            tested = self.provider_factory().health_check()
            result = {**status, **tested, "tested_at": datetime.now(UTC).isoformat()}
            self.repository.write_json("app-data/generation-engine/provider_state.json", result)
            return result
        saved = self.repository.read_json("app-data/generation-engine/provider_state.json", {})
        if status["configured"] and saved:
            return {**status, **{key: value for key, value in saved.items() if key not in {"masked_token", "source"}}}
        return status

    def model_stats(self) -> list[dict[str, Any]]:
        candidates = [candidate for run in self.history() for candidate in run.get("candidates", []) if candidate.get("image_path")]
        output: list[dict[str, Any]] = []
        for model in self.registry.list():
            records = [item for item in candidates if item.get("model") == model["key"]]
            approved_ids = {
                run.get("selected_candidate_id")
                for run in self.history()
                if run.get("status") == "approved"
            }
            output.append(
                {
                    "model": model["key"],
                    "display_name": model["display_name"],
                    "power_label": model["power_label"],
                    "power_level": model["power_level"],
                    "sample_size": len(records),
                    "approval_rate": round(sum(item["id"] in approved_ids for item in records) / len(records), 3) if records else None,
                    "average_repairs": round(sum(bool(item.get("repair_parent_id")) for item in records) / len(records), 2) if records else None,
                    "average_runtime_ms": round(sum(int(item.get("runtime_ms") or 0) for item in records) / len(records)) if records else None,
                    "small_sample_warning": len(records) < 10,
                }
            )
        return output

    def reference_manifest(self, brief: StoryBrief) -> dict[str, Any]:
        combined = self.repository.path("references/dinkly_young.png")
        if not combined.is_file():
            raise RepositoryError("Official DINKLY model sheet is missing")
        version = hashlib.sha256(combined.read_bytes()).hexdigest()[:16]
        needs_boy = brief.left_character == "boy" or "boy" in brief.right_characters
        needs_girl = brief.left_character == "girl" or "girl" in brief.right_characters
        paths: list[Path] = []
        labels: list[str] = []
        if needs_boy:
            paths.append(combined)
            labels.append("Dinko")
        if needs_girl:
            # The locked production sheet currently contains both characters; pass it once while
            # recording independent identity versions for future separate model sheets.
            if combined not in paths:
                paths.append(combined)
            labels.append("Dinka")
        return {
            "paths": paths,
            "relative_paths": [self.repository.relative(path) for path in paths],
            "labels": labels,
            "dinko_reference_version": version if needs_boy else None,
            "dinka_reference_version": version if needs_girl else None,
        }

    def _default_provider(self) -> ImageProvider:
        return GeminiImageProvider(self.secrets.get_gemini_api_key(), self.registry)

    def _compile_prompt(self, brief: StoryBrief) -> dict[str, Any]:
        request = PromptGenerateRequest(
            concept_id=None,
            format=brief.format,
            title_pair={"left": brief.title_left, "right": brief.title_right},
            left_character=brief.left_character,
            left_character_action=brief.left_action,
            left_setting=brief.left_setting,
            left_props=brief.left_props,
            left_emotion=brief.left_emotion,
            right_character_actions=brief.right_action,
            right_setting=brief.right_setting,
            right_props=brief.right_props,
            right_emotion=brief.right_emotion,
            shared_environment=brief.shared_environment,
            environmental_contrast=brief.environmental_contrast,
            emotional_insight=brief.emotional_insight,
            recommended_background_color=brief.background_color,
            recommended_accent_color=brief.accent_color,
            recommended_camera_angle=brief.camera_angle,
            execution_risks=brief.execution_risks,
        )
        compiled = self.prompt_service.generate(request)
        context_query = " ".join(
            part
            for part in (
                brief.title_left,
                brief.title_right,
                brief.emotional_insight,
                brief.left_setting,
                brief.right_setting,
            )
            if part
        )
        agent_context = AgentContextBuilder(self.repository).build(context_query)
        if agent_context["memories"]:
            memory_lines = "\n".join(
                f"- {memory['summary']}"
                for memory in agent_context["memories"][:6]
            )
            compiled["prompt"] += (
                "\n\n## RELEVANT DINKLY MEMORY\n\n"
                "Apply only these evidence-linked constraints when they are relevant to this scene:\n"
                f"{memory_lines}\n"
            )
        if brief.comics:
            beats = "\n".join(
                f"{index}. {beat.get('title', f'Comic {index}')}: {beat.get('scene', '')} "
                f"Setting: {beat.get('setting', '')}. Props: {', '.join(beat.get('props', []))}. "
                f"Emotion: {beat.get('emotion', '')}. Camera: {beat.get('camera_angle', brief.camera_angle)}."
                for index, beat in enumerate(brief.comics, start=1)
            )
            compiled["prompt"] += (
                "\n\n## FIVE-COMIC CONTINUITY\n\n"
                "Create exactly five independently readable comic beats in sequence. Preserve the same locked Dinko and "
                "Dinka models, equal character scale, furniture language, background family, and restrained accent color "
                "throughout. Keep every beat visually simple.\n\n"
                f"{beats}\n"
            )
        now = datetime.now(UTC).isoformat()
        template_path = self.repository.path(f"PROMPT_TEMPLATES/{compiled['template']}")
        record = {
            "prompt_id": f"generation-prompt-{uuid.uuid4().hex[:12]}",
            "template": compiled["template"],
            "template_version": self._file_version(template_path),
            "character_rule_version": self._file_version(self.repository.path("CHARACTER_BIBLE.md")),
            "failure_rule_version": self._file_version(self.repository.path("FAILURES.md")),
            "created_at": now,
            "prompt": compiled["prompt"],
            "rules_included": compiled["rules_included"],
            "brain_refs_used": agent_context["brain_refs_used"],
            "memory_refs_used": agent_context["memory_refs_used"],
        }
        with self._lock:
            records = self.repository.read_json(PROMPTS_PATH, [])
            records.append(record)
            self.repository.write_json(PROMPTS_PATH, records)
        return record

    def _brief_from_record(self, record: dict[str, Any] | None) -> StoryBrief:
        if not record:
            raise RepositoryError("Story record is missing")
        if record.get("format") in {"five_story", "five-comic"}:
            return StoryBrief(
                id=record.get("id"),
                concept_id=record.get("id"),
                format="five_story",
                title_left=str(record.get("story_title") or "FIVE SMALL MOMENTS"),
                title_right=str(record.get("final_payoff") or "US"),
                left_action=str(record.get("emotional_premise") or "A connected five-comic story."),
                right_action=str(record.get("final_payoff") or "The story resolves in togetherness."),
                shared_environment=str(record.get("visual_continuity") or "One continuous DINKLY visual world."),
                environmental_contrast=str(record.get("background_strategy") or "Use one restrained pastel family."),
                background_color=str(record.get("background_color") or "warm cream"),
                accent_color=str(record.get("accent_color") or "muted mustard"),
                camera_angle=str(record.get("camera_angle") or "medium straight-on"),
                execution_risks=list(record.get("execution_risks") or []),
                emotional_insight=str(record.get("emotional_premise") or ""),
                comics=list(record.get("comics") or []),
            )
        return StoryBrief(
            id=record.get("id"),
            concept_id=record.get("concept_id") or record.get("id"),
            format=str(record.get("format") or "x-with-you").replace("with_you", "x-with-you"),
            title_left=str(record.get("title_left") or record.get("title_pair", {}).get("left") or ""),
            title_right=str(record.get("title_right") or record.get("title_pair", {}).get("right") or ""),
            left_character="girl" if record.get("left_character") == "girl" else "boy",
            left_action=str(record.get("left_action") or record.get("left_character_action") or record.get("left_scene") or "Experiences the activity alone."),
            left_setting=str(record.get("left_setting") or "a simple rounded room"),
            left_props=list(record.get("left_props") or []),
            left_emotion=str(record.get("left_emotion") or "Neutral, bored, or gently sad—never happy."),
            right_action=str(record.get("right_action") or record.get("right_character_actions") or record.get("right_scene") or "Share the same activity together."),
            right_setting=str(record.get("right_setting") or record.get("left_setting") or "the same simple rounded room"),
            right_props=list(record.get("right_props") or []),
            right_emotion=str(record.get("right_emotion") or "Warm and connected because the activity is shared."),
            shared_environment=str(record.get("shared_environment") or "The same environment and camera continue across both panels."),
            environmental_contrast=str(record.get("environmental_contrast") or "The activity barely changes; shared presence makes the right side warmer."),
            background_color=str(record.get("background_color") or record.get("recommended_background_color") or "warm cream"),
            accent_color=str(record.get("accent_color") or record.get("recommended_accent_color") or "muted mustard"),
            camera_angle=str(record.get("camera_angle") or record.get("recommended_camera_angle") or "medium straight-on"),
            execution_risks=list(record.get("execution_risks") or []),
            emotional_insight=str(record.get("emotional_insight") or record.get("concept") or "Ordinary life is better together."),
            brand_sensitive=bool(record.get("brand_sensitive") or record.get("brand_friendly")),
        )

    def _generic_brief(self, left: str, right: str) -> StoryBrief:
        activity = re.sub(r"[^A-Z0-9 ]", "", left.upper()).strip() or "ORDINARY MOMENT"
        setting = "a simple rounded home interior"
        left_props: list[str] = []
        right_props: list[str] = []
        if "COFFEE" in activity:
            setting = "a simple rounded breakfast nook with a low coffee table and compact coffee machine"
            left_props = ["one proportional coffee mug", "compact coffee machine", "rounded chair"]
            right_props = ["two proportional coffee mugs", "compact coffee machine", "two rounded chairs"]
        return StoryBrief(
            format="x-with-you",
            title_left=activity,
            title_right=right.rstrip(".").upper() or f"{activity} WITH YOU",
            left_action=f"Boy DINKLY does {activity.lower()} alone with one clear action.",
            left_setting=setting,
            left_props=left_props,
            right_action=f"Boy DINKLY and Girl DINKLY share the same {activity.lower()} routine together.",
            right_setting=setting,
            right_props=right_props,
            shared_environment=f"Both panels share one continuous pastel background and the same {setting}.",
            environmental_contrast="The left is quiet and sparse; the right adds closeness and gentle shared activity without changing the location.",
            execution_risks=["Keep both characters on the floor or visible chair seats.", "Keep props proportional and characters equal in body size."],
            emotional_insight=f"{activity.title()} feels warmer because it is shared.",
        )

    @staticmethod
    def _parse_concept(value: str) -> tuple[str, str]:
        parts = re.split(r"\s*/\s*", value.strip(), maxsplit=1)
        left = parts[0].strip().rstrip(".") if parts else ""
        if not left:
            raise RepositoryError("Enter a concept, such as COFFEE. / COFFEE WITH YOU.")
        right = parts[1].strip().rstrip(".") if len(parts) > 1 else f"{left} WITH YOU"
        return left.upper(), right.upper()

    def _preflight(self, model_key: str, count: int, *, confirm_pro: bool) -> float:
        model = self.registry.get(model_key)
        if model_key == "nano_banana_pro" and not confirm_pro:
            raise RepositoryError("Nano Banana Pro requires explicit cost confirmation")
        provider = self._default_provider()
        estimate = float(provider.estimate_cost(model_key=model_key, image_size=model["default_resolution"]) or 0) * count
        self._check_budget(estimate)
        if not self.secrets.get_gemini_api_key():
            raise RepositoryError("GEMINI_API_KEY is missing. Add it in Settings → Image Generation.")
        return round(estimate, 4)

    def _check_budget(self, estimate: float) -> None:
        settings = self.settings()
        if not settings.enable_paid_generation:
            raise RepositoryError("Paid image generation is disabled in Settings")
        if estimate > settings.maximum_cost_per_run:
            raise RepositoryError("Estimated image cost exceeds the maximum cost per GenerationRun")
        usage = self._usage_summary()
        if usage["daily"] + estimate > settings.daily_image_budget:
            raise RepositoryError("Estimated image cost exceeds the daily image budget")
        if usage["monthly"] + estimate > settings.monthly_image_budget:
            raise RepositoryError("Estimated image cost exceeds the monthly image budget")

    def _budget_warnings(self, estimate: float) -> list[str]:
        settings = self.settings()
        usage = self._usage_summary()
        if not settings.monthly_image_budget:
            return ["Monthly image budget is zero."]
        projected = (usage["monthly"] + estimate) / settings.monthly_image_budget * 100
        if projected >= settings.warn_at_percent:
            return [f"This run may move image usage to {projected:.1f}% of the monthly budget."]
        return []

    def _usage_summary(self) -> dict[str, float]:
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        daily = 0.0
        monthly = 0.0
        for relative in self.repository.list_json(
            "app-data/generation-engine/runs", suffix="/metadata.json"
        ):
            run = self.repository.read_json(relative, {})
            try:
                started = datetime.fromisoformat(str(run.get("started_at", "")).replace("Z", "+00:00"))
            except ValueError:
                started = now - timedelta(days=36500)
            cost = float(run.get("reported_cost") or run.get("estimated_cost") or 0)
            if started >= day_start:
                daily += cost
            if started >= month_start:
                monthly += cost
        return {"daily": round(daily, 4), "monthly": round(monthly, 4)}

    def _persist_candidate(
        self,
        run: dict[str, Any],
        result: Any,
        *,
        index: int,
        label: str,
        repair_parent_id: str | None = None,
        model_key: str | None = None,
        folder: str = "candidates",
    ) -> dict[str, Any]:
        model_key = model_key or run["selected_model"]
        candidate_id = f"candidate-{uuid.uuid4().hex[:12]}"
        extension = ".jpg" if result.mime_type == "image/jpeg" else ".webp" if result.mime_type == "image/webp" else ".png"
        path = self._run_dir(run["id"]) / folder / f"{candidate_id}{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.repository.atomic_write_bytes(path, result.content, create_backup=False)
        estimate = self._default_provider().estimate_cost(model_key=model_key)
        model = self.registry.get(model_key)
        return {
            "id": candidate_id,
            "generation_run_id": run["id"],
            "label": label,
            "image_path": self.repository.relative(path),
            "asset_url": self._asset_url(path),
            "provider": "google_gemini",
            "model": model_key,
            "model_display_name": model["display_name"],
            "model_power_label": model["power_label"],
            "model_power_level": model["power_level"],
            "model_description": model["description"],
            "model_cost_tier": model["cost_tier"],
            "generation_index": index,
            "runtime_ms": result.runtime_ms,
            "qa_status": "Pending",
            "qa_summary": "Waiting for visual QA.",
            "qa_findings": [],
            "rank": None,
            "recommended": False,
            "selected": False,
            "repair_parent_id": repair_parent_id,
            "estimated_cost": estimate,
            "reported_cost": result.reported_cost,
            "created_at": datetime.now(UTC).isoformat(),
            "error": None,
        }

    def _failed_candidate(
        self,
        run: dict[str, Any],
        *,
        index: int,
        label: str,
        error: ImageProviderError,
        model_key: str | None = None,
    ) -> dict[str, Any]:
        key = model_key or run.get("selected_model")
        model = self.registry.get(key) if key else None
        return {
            "id": f"candidate-{uuid.uuid4().hex[:12]}",
            "generation_run_id": run["id"],
            "label": label,
            "image_path": None,
            "asset_url": None,
            "provider": "google_gemini",
            "model": key,
            "model_display_name": model["display_name"] if model else "Unknown",
            "model_power_label": model["power_label"] if model else "UNKNOWN",
            "model_power_level": model["power_level"] if model else 0,
            "model_description": model["description"] if model else "Model unavailable.",
            "model_cost_tier": model["cost_tier"] if model else "unknown",
            "generation_index": index,
            "runtime_ms": None,
            "qa_status": "Fail",
            "qa_summary": str(error),
            "qa_findings": [],
            "rank": None,
            "recommended": False,
            "selected": False,
            "repair_parent_id": None,
            "estimated_cost": 0,
            "reported_cost": None,
            "created_at": datetime.now(UTC).isoformat(),
            "error": {"code": error.code, "message": str(error), "retryable": error.retryable},
        }

    def _qa_candidate(self, run: dict[str, Any], candidate: dict[str, Any], provider: ImageProvider) -> None:
        try:
            result = provider.analyze(
                image_path=self.repository.path(candidate.get("final_image_path") or candidate["image_path"]),
                model_key="nano_banana_2",
                prompt=self._qa_prompt(StoryBrief.model_validate(run["story_brief"])),
            )
            findings = result.get("findings") if isinstance(result.get("findings"), list) else []
            candidate["qa_findings"] = findings
            candidate["qa_status"] = self._qa_status(findings)
            candidate["qa_summary"] = str(result.get("summary") or self._qa_summary(candidate["qa_status"], findings))
            candidate["qa_runtime_ms"] = result.get("runtime_ms")
        except ImageProviderError as exc:
            candidate["qa_status"] = "Unavailable"
            candidate["qa_summary"] = "Automated visual QA unavailable"
            candidate["qa_findings"] = []
            candidate["qa_error"] = {"code": exc.code, "message": str(exc)}

    @staticmethod
    def _qa_prompt(brief: StoryBrief) -> str:
        return (
            "Review this generated DINKLY comic visually. Return JSON only with keys summary and findings. "
            "findings is an array of objects with category, check, status, and detail. status must be Pass, Warning, or Fail. "
            "Check CHARACTER: round bright-yellow bodies, official orange spots, black oval eyes with white highlights, Dinko exactly two hair tufts, "
            "Dinka red bow and connected ponytail, equal body size, tiny nub arms and feet, no legs or human anatomy. "
            f"Check SCENE against left action '{brief.left_action}', right action '{brief.right_action}', settings, required props, "
            f"one continuous {brief.background_color} background, and {brief.camera_angle} composition. "
            f"Check TEXT exactly '{brief.title_left}' and '{brief.title_right}' with no quotation marks. "
            "Check PROP SCALE for mugs, phones, tables, carts, and furniture. Do not predict virality."
        )

    @staticmethod
    def _qa_status(findings: list[dict[str, Any]]) -> str:
        statuses = {str(item.get("status")) for item in findings}
        if "Fail" in statuses:
            return "Fail"
        if "Warning" in statuses:
            return "Warning"
        return "Pass" if findings else "Unavailable"

    @staticmethod
    def _qa_summary(status: str, findings: list[dict[str, Any]]) -> str:
        issues = sum(item.get("status") in {"Warning", "Fail"} for item in findings)
        if status == "Pass":
            return "On-model with no detected production issues."
        if status == "Warning":
            return f"Recommended with {issues} minor fix{'es' if issues != 1 else ''}."
        if status == "Fail":
            return f"Needs repair for {issues} production issue{'s' if issues != 1 else ''}."
        return "Automated visual QA unavailable"

    @staticmethod
    def _rank(run: dict[str, Any]) -> None:
        def penalty(item: dict[str, Any]) -> tuple[int, int, int]:
            if not item.get("image_path"):
                return (999, 999, int(item.get("generation_index") or 0))
            findings = item.get("qa_findings") or []
            fails = sum(finding.get("status") == "Fail" for finding in findings)
            warnings = sum(finding.get("status") == "Warning" for finding in findings)
            unavailable = 1 if item.get("qa_status") == "Unavailable" else 0
            return (fails * 10 + warnings + unavailable * 5, len(findings), int(item.get("generation_index") or 0))

        generated = [item for item in run["candidates"] if item.get("image_path")]
        ordered = sorted(generated, key=penalty)
        for item in run["candidates"]:
            item["rank"] = ordered.index(item) + 1 if item in ordered else None
            item["recommended"] = bool(ordered and item["id"] == ordered[0]["id"])

    def _save_run(self, run: dict[str, Any]) -> None:
        with self._lock:
            path = self._run_dir(run["id"]) / "metadata.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.repository.write_json(self.repository.relative(path), run)

    def _cancel_run(self, run_id: str, stage: str) -> None:
        """Stop from fresh persisted state so in-flight local mutations never leak."""
        persisted = self._load_run(run_id)
        persisted["status"] = "cancelled"
        persisted["cancellation_stage"] = stage
        persisted["completed_at"] = datetime.now(UTC).isoformat()
        persisted.setdefault("warnings", []).append(
            f"Task cancelled at {stage}. Completed candidates were preserved."
        )
        self._save_run(persisted)
        self._emit_stage(run_id, "cancellation", "complete", f"Stopped at {stage}.")
        self._emit(run_id, "task_cancelled", f"Task cancelled at {stage}. Completed candidates were preserved.")
        raise GenerationCancellationRequested(stage)

    def _load_run(self, run_id: str) -> dict[str, Any]:
        path = self._run_dir(run_id) / "metadata.json"
        relative = self.repository.relative(path)
        if not self.repository.json_exists(relative):
            raise RepositoryError("Generation run not found")
        return self.repository.read_json(relative, {})

    def _find_candidate(self, candidate_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for relative in self.repository.list_json(
            "app-data/generation-engine/runs", suffix="/metadata.json"
        ):
            run = self.repository.read_json(relative, {})
            for candidate in run.get("candidates", []):
                if candidate.get("id") == candidate_id:
                    return run, candidate
        raise RepositoryError("Candidate not found")

    def _run_dir(self, run_id: str) -> Path:
        if not re.fullmatch(r"generation-[a-f0-9]{12}", run_id):
            raise RepositoryError("Invalid generation run ID")
        return self.runs_dir / run_id

    def _asset_url(self, path: Path) -> str:
        return self.repository.asset_url(self.repository.relative(path))

    def _emit(
        self,
        run_id: str,
        kind: str,
        message: str,
        data: dict[str, Any] | None = None,
        *,
        level: str = "info",
    ) -> None:
        event = self.runtime.emit(run_id, kind, message, data, level=level)
        self.agent_visual.handle_generation_event(event)

    def _emit_stage(
        self,
        run_id: str,
        stage: str,
        status: str,
        message: str,
        **data: Any,
    ) -> None:
        level = "warning" if status in {"warning", "failed"} else "info"
        event_names = {
            ("story", "active"): "story_brief_started",
            ("generate", "active"): "generation_started",
            ("generate", "complete"): "candidate_received",
            ("layout", "active"): "layout_started",
            ("qa", "active"): "qa_started",
            ("repair", "active"): "repair_started",
            ("human_review", "active"): "awaiting_human",
            ("human_review", "complete"): "run_completed",
        }
        event_name = "run_failed" if status == "failed" else (
            "candidate_received" if stage == "generate" and data.get("candidate_status") == "complete" else event_names.get((stage, status))
        )
        self._emit(
            run_id,
            "progress",
            message,
            {"stage": stage, "status": status, "event_name": event_name, **data},
            level=level,
        )

    def _mark_used(self, run: dict[str, Any]) -> None:
        if not run.get("concept_id"):
            return
        records = self.repository.read_json("data/used_storylines.json", [])
        if any(item.get("generation_ids") and run["id"] in item["generation_ids"] for item in records):
            return
        format_map = {"x-with-you": "with_you", "before-after": "before_after", "five-comic": "five_story"}
        now = datetime.now(UTC).isoformat()
        records.append(
            {
                "id": f"used-{uuid.uuid4().hex[:12]}",
                "concept": run["story_brief"],
                "format": format_map.get(run["story_format"], run["story_format"]),
                "date_generated": run["started_at"],
                "date_approved": now,
                "date_used": now,
                "prompt_ids": [run["prompt_id"]],
                "generation_ids": [run["id"]],
                "published_post_ids": [],
                "performance_data": {},
                "feedback": [],
                "source_batch": "generation-engine",
                "source_trend": None,
                "status": "used",
            }
        )
        self.repository.write_json("data/used_storylines.json", records)

    def _model_presentation(self, key: str, *, expose_id: bool) -> dict[str, Any]:
        model = self.registry.get(key)
        presentation = {
            "id": model["id"],
            "display_name": model["display_name"],
            "power_label": model["power_label"],
            "power_level": model["power_level"],
            "description": model["description"],
            "recommended_for": model["recommended_for"],
            "cost_tier": model["cost_tier"],
        }
        if expose_id:
            presentation["model_id"] = model["model_id"]
        return presentation

    @staticmethod
    def _file_version(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]

    @staticmethod
    def _concept_label(brief: StoryBrief) -> str:
        return " / ".join(value for value in (brief.title_left, brief.title_right) if value)

    @staticmethod
    def _candidate_cost(run: dict[str, Any]) -> float | None:
        generated = [item for item in run["candidates"] if item.get("image_path")]
        if not generated or any(item.get("reported_cost") is None for item in generated):
            return None
        return round(sum(float(item["reported_cost"]) for item in generated), 4)
