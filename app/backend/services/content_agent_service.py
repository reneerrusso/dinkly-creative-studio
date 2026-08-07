from __future__ import annotations

import fcntl
import re
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.backend.models.concepts import ConceptCreate
from app.backend.models.content_agent import (
    ContentBatch,
    ContentConcept,
    ContentFeedback,
    ContentFormat,
    ContentPreference,
    ContentSettings,
    UsedStoryline,
)
from app.backend.models.prompts import PromptGenerateRequest, PromptSaveRequest
from app.backend.models.social_intelligence import RunStatus
from app.backend.services.agent_runtime_service import AgentRuntimeService
from app.backend.services.concept_generator_schedule import detect_local_timezone
from app.backend.services.concept_service import ConceptService
from app.backend.services.content_agent import ContentModelProvider, content_provider_from_environment
from app.backend.services.content_agent_workflow import ConceptGeneratorWorkflow
from app.backend.services.prompt_service import PromptService
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.story_library_service import StoryLibraryService

BATCHES_PATH = "data/content_batches.json"
CONCEPTS_PATH = "data/content_concepts.json"
FEEDBACK_PATH = "data/content_feedback.json"
PREFERENCES_PATH = "data/content_agent_preferences.json"
USED_PATH = "data/used_storylines.json"
CHAT_PATH = "app-data/content_agent_chat.json"
SETTINGS_PATH = "app-data/content_agent_settings.json"
MODEL_USAGE_PATH = "app-data/content_provider_usage.json"


class ConceptGeneratorService:
    def __init__(self, repository: RepositoryService, provider: ContentModelProvider | None = None) -> None:
        self.repository = repository
        self.runtime = AgentRuntimeService(repository)
        self.provider = provider or content_provider_from_environment(repository)
        self.workflow = ConceptGeneratorWorkflow(repository, self.runtime, self.provider)
        self.concepts = ConceptService(repository)
        self.prompts = PromptService(repository, self.concepts)
        self.story_library = StoryLibraryService(repository)

    def state(self) -> dict[str, Any]:
        today = self.local_date().isoformat()
        batches = self.list_batches()
        concepts = self.list_concepts()
        today_batches = [item for item in batches if item["date"] == today]
        active_run = next(
            (
                {**item, "display_agent": "Concept Generator"}
                for item in self.runtime.list_runs()
                if item.get("agent") in {"concept-generator", "content-agent", "content"}
            ),
            None,
        )
        return {
            "provider_configured": self.provider.configured,
            "provider_name": self.provider.name,
            "provider": self.provider.health(),
            "today": today,
            "today_batches": today_batches,
            "batches": batches,
            "today_concepts": [item for item in concepts if item["batch_id"] in {batch["id"] for batch in today_batches} and item["status"] == "candidate"],
            "production_queue": [item for item in concepts if item["status"] in {"approved", "prompt_ready", "in_production"}],
            "passed": [item for item in concepts if item["status"] == "passed"],
            "used_storylines": self.repository.read_json(USED_PATH, []),
            "preferences": self.preferences(),
            "chat": self.repository.read_json(CHAT_PATH, []),
            "settings": self.settings().model_dump(mode="json"),
            "latest_run": active_run,
        }

    def list_batches(self) -> list[dict[str, Any]]:
        return list(reversed(self.repository.read_json(BATCHES_PATH, [])))

    def list_concepts(self) -> list[dict[str, Any]]:
        return self.repository.read_json(CONCEPTS_PATH, [])

    def get_concept(self, concept_id: str) -> dict[str, Any]:
        record = next((item for item in self.list_concepts() if item.get("id") == concept_id), None)
        if not record:
            raise RepositoryError("Concept not found")
        return record

    def local_date(self, now: datetime | None = None) -> date:
        timezone = ZoneInfo(self.settings().timezone)
        value = now or datetime.now(timezone)
        return value.astimezone(timezone).date()

    def has_primary_batch(self, target_date: date) -> bool:
        return any(item["date"] == target_date.isoformat() and item.get("primary") for item in self.list_batches())

    def start_batch(self, mode: str = "primary") -> dict[str, Any]:
        return self.generate_daily_concept_batch(source="manual", mode=mode, execute=False)

    def generate_daily_concept_batch(
        self,
        target_date: date | None = None,
        *,
        source: str = "manual",
        mode: str = "primary",
        scheduled_for: datetime | None = None,
        execute: bool = True,
    ) -> dict[str, Any]:
        """Single source of truth used by manual, scheduled, catch-up, and test runs."""
        day = target_date or self.local_date()
        today = day.isoformat()
        scheduled = source in {"scheduled", "catch_up", "scheduler_test"}
        with self._generation_lock():
            existing = [item for item in self.list_batches() if item["date"] == today and item.get("primary")]
            if existing and mode == "primary":
                if scheduled:
                    return self.record_skipped_run(day, source, ["Today’s primary batch already exists."], scheduled_for=scheduled_for)
                raise RepositoryError("Today already has a primary batch. Choose replace unreviewed or supplemental.")
            if mode == "replace_unreviewed" and not existing:
                raise RepositoryError("There is no primary batch to replace today.")
            preflight = self.generation_preflight(source=source, target_date=day, mode=mode)
            if scheduled and not preflight["ready"]:
                return self.record_skipped_run(day, source, preflight["problems"], scheduled_for=scheduled_for)
            if not preflight["ready"]:
                raise RepositoryError(preflight["problems"][0])
            run = self.runtime.create_run(
                "concept-generator-daily-batch",
                {"date": today, "mode": mode, "source": source, "scheduled_for": scheduled_for.isoformat() if scheduled_for else None},
                agent="concept-generator",
            )
            self.runtime.emit(run["id"], "scheduler" if scheduled else "manual", f"Concept Generator batch triggered by {source.replace('_', ' ')}.", {"source": source, "date": today})
            batch_id = f"batch-{today}-{uuid.uuid4().hex[:8]}"
            batch = ContentBatch(
                id=batch_id,
                date=today,
                created_at=datetime.now(UTC),
                status="generating",
                source_summary="Generation in progress.",
                agent_run_id=run["id"],
                primary=mode != "supplemental",
                development_fixture=self.provider.development_fixture,
                generation_source=source,
                scheduled_for=scheduled_for,
            ).model_dump(mode="json")
            batches = list(reversed(self.list_batches()))
            batches.append(batch)
            self.repository.write_json(BATCHES_PATH, batches)
        started = {"run": run, "batch": batch, "preflight": preflight}
        if execute:
            started["result"] = self.execute_batch(run["id"], batch["id"], mode)
        return started

    def generation_preflight(self, *, source: str, target_date: date, mode: str = "primary") -> dict[str, Any]:
        settings = self.settings()
        scheduled = source in {"scheduled", "catch_up", "scheduler_test"}
        estimate = float(getattr(self.provider, "estimated_batch_cost", 1.0))
        budget = self.model_budget_summary()
        problems: list[str] = []
        if not self.provider.configured:
            problems.append("No AI provider configured.")
        if scheduled and not getattr(self.provider, "real_provider", False):
            problems.append("Production scheduling cannot use fixtures or demo providers.")
        if scheduled and not settings.enable_paid_model_calls:
            problems.append("Paid model calls are disabled for automatic generation.")
        limit = settings.maximum_automatic_batch_cost if scheduled else settings.maximum_manual_batch_cost
        if estimate > limit:
            problems.append(f"Estimated batch cost ${estimate:.2f} exceeds the ${limit:.2f} run limit.")
        if estimate > budget["daily_remaining"]:
            problems.append("Daily AI budget would be exceeded.")
        if estimate > budget["monthly_remaining"]:
            problems.append("Monthly AI budget would be exceeded.")
        if mode == "primary" and self.has_primary_batch(target_date):
            problems.append("Today’s primary batch already exists.")
        return {"ready": not problems, "problems": problems, "estimated_cost": estimate, "budget": budget, "provider": self.provider.health(), "source": source}

    def record_skipped_run(self, target_date: date, source: str, problems: list[str], *, scheduled_for: datetime | None = None) -> dict[str, Any]:
        reason = problems[0] if problems else "Scheduler preflight did not pass."
        run = self.runtime.create_run("concept-generator-daily-batch", {"date": target_date.isoformat(), "source": source, "scheduled_for": scheduled_for.isoformat() if scheduled_for else None}, agent="concept-generator")
        self.runtime.emit(run["id"], "preflight", f"Skipped: {reason}", {"problems": problems}, level="warning")
        completed = self.runtime.update(run["id"], status=RunStatus.SKIPPED.value, summary={"skipped": True, "reason": reason}, error=reason, completed_at=datetime.now(UTC).isoformat())
        return {"status": "skipped", "message": reason, "problems": problems, "run": completed}

    def model_budget_summary(self, now: datetime | None = None) -> dict[str, float]:
        timezone = ZoneInfo(self.settings().timezone)
        local = (now or datetime.now(timezone)).astimezone(timezone)
        day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        records = self.repository.read_json(MODEL_USAGE_PATH, [])
        def amount_since(cutoff: datetime) -> float:
            total = 0.0
            for item in records:
                try:
                    timestamp = datetime.fromisoformat(str(item.get("timestamp", "")).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if timestamp >= cutoff:
                    total += float(item.get("actual_cost") if item.get("actual_cost") is not None else item.get("estimated_cost", 0))
            return total
        daily, monthly = amount_since(day_start), amount_since(month_start)
        settings = self.settings()
        return {"daily_used": round(daily, 4), "daily_remaining": round(max(0.0, settings.daily_model_budget - daily), 4), "monthly_used": round(monthly, 4), "monthly_remaining": round(max(0.0, settings.monthly_model_budget - monthly), 4)}

    def execute_batch(self, run_id: str, batch_id: str, mode: str = "primary") -> dict[str, Any]:
        try:
            self.runtime.emit(run_id, "provider", f"Verified {self.provider.name} provider configuration.", {"provider": self.provider.name, "real_provider": self.provider.real_provider})
            finalists, source = self.workflow.execute(run_id, batch_id)
            concepts = self.list_concepts()
            if mode == "replace_unreviewed":
                today_batch_ids = {item["id"] for item in self.list_batches() if item["date"] == self.local_date().isoformat() and item.get("primary")}
                for item in concepts:
                    if item["batch_id"] in today_batch_ids and item["status"] == "candidate":
                        item["status"] = "archived"
                        item["updated_at"] = datetime.now(UTC).isoformat()
            concepts.extend(finalists)
            self.repository.write_json(CONCEPTS_PATH, concepts)
            batches = list(reversed(self.list_batches()))
            for batch in batches:
                if batch["id"] == batch_id:
                    batch.update({
                        "status": "supplemental" if mode == "supplemental" else "waiting_for_review",
                        "source_summary": self._source_summary(source),
                        "with_you_count": 10,
                        "before_after_count": 10,
                        "five_story_count": 10,
                    })
            self.repository.write_json(BATCHES_PATH, batches)
            self.runtime.update(run_id, status=RunStatus.COMPLETED.value, summary={"batch_id": batch_id, "finalists": 30}, completed_at=datetime.now(UTC).isoformat())
            self.runtime.emit(run_id, "complete", "Daily Concept Generator batch complete.", {"batch_id": batch_id, "finalists": 30})
            usage = self.repository.read_json(MODEL_USAGE_PATH, [])
            usage.append({"run_id": run_id, "batch_id": batch_id, "provider": self.provider.name, "timestamp": datetime.now(UTC).isoformat(), "estimated_cost": float(getattr(self.provider, "estimated_batch_cost", 1.0)), "actual_cost": None})
            self.repository.write_json(MODEL_USAGE_PATH, usage)
            return {"batch_id": batch_id, "finalists": 30}
        except Exception as exc:
            batches = list(reversed(self.list_batches()))
            for batch in batches:
                if batch["id"] == batch_id:
                    batch["status"] = "failed"
                    batch["source_summary"] = str(exc)
            self.repository.write_json(BATCHES_PATH, batches)
            self.runtime.update(run_id, status=RunStatus.FAILED.value, error=str(exc), completed_at=datetime.now(UTC).isoformat())
            self.runtime.emit(run_id, "failed", str(exc), level="warning")
            raise

    def approve(self, concept_id: str) -> dict[str, Any]:
        concept = self.get_concept(concept_id)
        if concept["status"] != "candidate":
            raise RepositoryError("Only active candidates can be approved")
        count = sum(item["batch_id"] == concept["batch_id"] and item["format"] == concept["format"] and item["status"] in {"approved", "prompt_ready", "in_production", "used"} for item in self.list_concepts())
        if count >= 5:
            raise RepositoryError("You already selected 5 from this format. Remove one from Ready to Make before approving another.")
        approved = self._transition(concept_id, "approved", "approved")
        story = self.story_library.add_approved_concept(approved)
        return {**approved, "story_library_id": story["id"]}

    def pass_concept(self, concept_id: str, reason: str | None = None) -> dict[str, Any]:
        result = self._transition(concept_id, "passed", "rejected", reason)
        self._infer_possible_preference(reason)
        return result

    def edit(self, concept_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        protected = {"id", "batch_id", "format", "created_at", "approved_at", "used_at", "prompt_ids"}
        if protected & changes.keys():
            raise RepositoryError("Identity and workflow fields cannot be edited")
        records = self.list_concepts()
        for index, record in enumerate(records):
            if record["id"] == concept_id:
                updated = ContentConcept.model_validate({**record, **changes, "updated_at": datetime.now(UTC).isoformat()}).model_dump(mode="json")
                records[index] = updated
                self.repository.write_json(CONCEPTS_PATH, records)
                return updated
        raise RepositoryError("Concept not found")

    def replace(self, concept_id: str) -> dict[str, Any]:
        original = self.get_concept(concept_id)
        if original["status"] != "candidate":
            raise RepositoryError("Only an active candidate can be replaced")
        run = self.runtime.create_run("concept-generator-replacement", {"concept_id": concept_id}, agent="concept-generator")
        replacement = self.workflow.generate_replacement(run["id"], original["batch_id"], ContentFormat(original["format"]), original["slot"])
        records = self.list_concepts()
        for record in records:
            if record["id"] == concept_id:
                record["status"] = "archived"
                record["updated_at"] = datetime.now(UTC).isoformat()
        records.append(replacement)
        self.repository.write_json(CONCEPTS_PATH, records)
        self._feedback(original, "skipped", "Replaced by user")
        self.runtime.update(run["id"], status=RunStatus.COMPLETED.value, summary={"replacement_id": replacement["id"]}, completed_at=datetime.now(UTC).isoformat())
        return replacement

    def remove_from_queue(self, concept_id: str) -> dict[str, Any]:
        concept = self.get_concept(concept_id)
        if concept["status"] not in {"approved", "prompt_ready", "in_production"}:
            raise RepositoryError("Concept is not in the Production Queue")
        return self._transition(concept_id, "archived", "skipped", "Removed from Production Queue")

    def mark_used(self, concept_id: str) -> dict[str, Any]:
        concept = self.get_concept(concept_id)
        existing = next((item for item in self.repository.read_json(USED_PATH, []) if item.get("concept", {}).get("id") == concept_id), None)
        if existing and concept.get("status") == "used":
            return concept
        now = datetime.now(UTC)
        feedback = [
            f"{item.get('action')}: {item.get('feedback_note')}" if item.get("feedback_note") else str(item.get("action"))
            for item in self.repository.read_json(FEEDBACK_PATH, [])
            if item.get("concept_id") == concept_id
        ]
        used = UsedStoryline(
            id=f"used-{uuid.uuid4().hex[:12]}", concept=concept, format=ContentFormat(concept["format"]),
            date_generated=concept["created_at"], date_approved=concept.get("approved_at"), date_used=now,
            prompt_ids=concept.get("prompt_ids", []), feedback=feedback, source_batch=concept["batch_id"], source_trend=concept.get("source_trend"),
        ).model_dump(mode="json")
        used_records = self.repository.read_json(USED_PATH, [])
        if not existing:
            used_records.append(used)
            self.repository.write_json(USED_PATH, used_records)
        return self._transition(concept_id, "used", "used")

    def duplicate_variation(self, used_id: str) -> dict[str, Any]:
        used = next((item for item in self.repository.read_json(USED_PATH, []) if item["id"] == used_id), None)
        if not used:
            raise RepositoryError("Used storyline not found")
        now = datetime.now(UTC).isoformat()
        source = used["concept"]
        clone = {**source, "id": f"content-{uuid.uuid4().hex[:12]}", "status": "candidate", "approved_at": None, "used_at": None, "prompt_ids": [], "development_fixture": False, "created_at": now, "updated_at": now}
        if clone.get("story_title"):
            clone["story_title"] = f"{clone['story_title']} — INTENTIONAL VARIATION"
        else:
            clone["title_left"] = f"{clone['title_left']} — VARIATION"
            clone["title_right"] = f"{clone['title_right']} — VARIATION"
        validated = ContentConcept.model_validate(clone).model_dump(mode="json")
        records = self.list_concepts()
        records.append(validated)
        self.repository.write_json(CONCEPTS_PATH, records)
        return validated

    def prompt_handoff(self, concept_id: str) -> dict[str, Any]:
        concept = self.get_concept(concept_id)
        if concept["status"] not in {"approved", "prompt_ready", "in_production"}:
            raise RepositoryError("Approve the concept before generating production prompts")
        if concept["format"] == ContentFormat.FIVE_STORY.value:
            generated = [self._generate_comic_prompt(concept, beat, index) for index, beat in enumerate(concept["comics"], 1)]
            prompt_ids = [item["saved"]["id"] for item in generated]
            self._set_prompt_ready(concept_id, prompt_ids)
            self.mark_used(concept_id)
            return {"kind": "five_story", "prompts": [item["generated"] for item in generated], "prompt_ids": prompt_ids, "message": "Five independent continuity-locked prompts generated."}
        app_concept, _ = self.concepts.create(self._to_concept_create(concept))
        generated = self.prompts.generate(PromptGenerateRequest(concept_id=app_concept["id"], format=app_concept["format"]))
        saved, _ = self.prompts.save(PromptSaveRequest(
            title=f"{concept['title_left']} / {concept['title_right']}", format=generated["format"], source_storyline_id=app_concept["id"], template=generated["template"], prompt=generated["prompt"], left_character=concept["left_character"],
        ))
        self._set_prompt_ready(concept_id, [saved["id"]])
        self.mark_used(concept_id)
        return {
            "kind": "single",
            "handoff_agent": "prompt-agent",
            "prompt": generated,
            "prompt_ids": [saved["id"]],
            "href": f"/prompt-builder?concept={app_concept['id']}&autogenerate=1&source=concept-generator&batch={concept['batch_id']}",
        }

    def chat(self, message: str) -> dict[str, Any]:
        preference_type, topic, value, strength, response = self._parse_chat(message)
        now = datetime.now(UTC).isoformat()
        chat = self.repository.read_json(CHAT_PATH, [])
        user_record = {"id": f"chat-{uuid.uuid4().hex[:12]}", "role": "user", "message": message, "created_at": now}
        chat.append(user_record)
        preference = self._upsert_preference(preference_type, topic, value, strength, "concept_generator_chat", user_record["id"], active=True)
        reply = {"id": f"chat-{uuid.uuid4().hex[:12]}", "role": "assistant", "message": response, "created_at": now}
        chat.append(reply)
        self.repository.write_json(CHAT_PATH, chat)
        return {"reply": reply, "preference": preference}

    def preferences(self) -> list[dict[str, Any]]:
        return self.repository.read_json(PREFERENCES_PATH, [])

    def update_preference(self, preference_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        records = self.preferences()
        for index, record in enumerate(records):
            if record["id"] == preference_id:
                updated = ContentPreference.model_validate({**record, **{key: value for key, value in changes.items() if value is not None}, "source": "user_edit", "updated_at": datetime.now(UTC).isoformat()}).model_dump(mode="json")
                records[index] = updated
                self.repository.write_json(PREFERENCES_PATH, records)
                return updated
        raise RepositoryError("Concept Generator preference not found")

    def delete_preference(self, preference_id: str) -> None:
        records = self.preferences()
        if not any(item["id"] == preference_id for item in records):
            raise RepositoryError("Concept Generator preference not found")
        self.repository.write_json(PREFERENCES_PATH, [item for item in records if item["id"] != preference_id])

    def settings(self) -> ContentSettings:
        payload = self.repository.read_json(SETTINGS_PATH, {"run_time": "08:00"})
        if not isinstance(payload, dict):
            raise RepositoryError("Concept Generator settings must be a JSON object")
        if not payload.get("timezone"):
            payload = {**payload, "timezone": detect_local_timezone()}
            self.repository.write_json(SETTINGS_PATH, payload)
        return ContentSettings.model_validate(payload)

    def update_settings(self, settings: ContentSettings) -> dict[str, Any]:
        payload = settings.model_dump(mode="json")
        self.repository.write_json(SETTINGS_PATH, payload)
        return payload

    @contextmanager
    def _generation_lock(self):
        """Serialize primary-batch creation across the API and LaunchAgent processes."""
        path: Path = self.repository.path("app-data/concept_generator_generation.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _transition(self, concept_id: str, status: str, action: str, note: str | None = None) -> dict[str, Any]:
        records = self.list_concepts()
        now = datetime.now(UTC).isoformat()
        target = None
        for index, record in enumerate(records):
            if record["id"] == concept_id:
                record["status"] = status
                record["updated_at"] = now
                if status == "approved":
                    record["approved_at"] = now
                if status == "used":
                    record["used_at"] = now
                target = ContentConcept.model_validate(record).model_dump(mode="json")
                records[index] = target
        if not target:
            raise RepositoryError("Content concept not found")
        self.repository.write_json(CONCEPTS_PATH, records)
        self._feedback(target, action, note)
        self._update_batch_counts(target["batch_id"])
        return target

    def _feedback(self, concept: dict[str, Any], action: str, note: str | None = None) -> None:
        record = ContentFeedback(concept_id=concept["id"], batch_id=concept["batch_id"], format=ContentFormat(concept["format"]), action=action, feedback_note=note, timestamp=datetime.now(UTC)).model_dump(mode="json")
        records = self.repository.read_json(FEEDBACK_PATH, [])
        records.append(record)
        self.repository.write_json(FEEDBACK_PATH, records)

    def _update_batch_counts(self, batch_id: str) -> None:
        concepts = [item for item in self.list_concepts() if item["batch_id"] == batch_id]
        batches = list(reversed(self.list_batches()))
        for batch in batches:
            if batch["id"] == batch_id:
                batch["approved_count"] = sum(item["status"] in {"approved", "prompt_ready", "in_production", "used", "published"} for item in concepts)
                batch["used_count"] = sum(item["status"] in {"used", "published"} for item in concepts)
        self.repository.write_json(BATCHES_PATH, batches)

    def _set_prompt_ready(self, concept_id: str, prompt_ids: list[str]) -> None:
        records = self.list_concepts()
        for record in records:
            if record["id"] == concept_id:
                record["status"] = "prompt_ready"
                record["prompt_ids"] = prompt_ids
                record["updated_at"] = datetime.now(UTC).isoformat()
        self.repository.write_json(CONCEPTS_PATH, records)

    def _generate_comic_prompt(self, concept: dict[str, Any], beat: dict[str, Any], index: int) -> dict[str, Any]:
        continuity = f"Comic {index} of 5. {concept['visual_continuity']} {concept['background_strategy']}"
        payload = PromptGenerateRequest(
            format="single-panel", title_pair={"left": beat["title"], "right": ""}, left_character="boy",
            left_scene=beat["scene"], left_character_action=beat["scene"], left_setting=beat["setting"], left_props=beat["props"], left_emotion=beat["emotion"],
            right_character_actions=beat["scene"], right_setting=beat["setting"], right_props=beat["props"], right_emotion=beat["emotion"], shared_environment=beat["setting"],
            emotional_insight=concept["emotional_premise"], recommended_background_color=concept["background_color"], recommended_accent_color=concept["accent_color"], recommended_camera_angle=beat["camera_angle"], props=beat["props"], execution_risks=concept["execution_risks"], composition_notes=continuity,
        )
        generated = self.prompts.generate(payload)
        saved, _ = self.prompts.save(PromptSaveRequest(title=f"{concept['story_title']} — Comic {index}", format=generated["format"], source_storyline_id=concept["id"], template=generated["template"], prompt=generated["prompt"], left_character="boy", qa_notes=continuity))
        return {"generated": {**generated, "comic_number": index, "title": beat["title"]}, "saved": saved}

    @staticmethod
    def _to_concept_create(concept: dict[str, Any]) -> ConceptCreate:
        return ConceptCreate(
            format="before-after" if concept["format"] == "before_after" else "x-with-you",
            title_pair={"left": concept["title_left"], "right": concept["title_right"]}, left_scene=f"{concept['left_action']} in {concept['left_setting']}.", right_scene=f"{concept['right_action']} in {concept['right_setting']}.",
            emotional_insight=concept["emotional_insight"], left_character=concept["left_character"], left_character_action=concept["left_action"], left_setting=concept["left_setting"], left_props=concept["left_props"], left_emotion=concept["left_emotion"],
            right_character_actions=concept["right_action"], right_setting=concept["right_setting"], right_props=concept["right_props"], right_emotion=concept["right_emotion"], shared_environment=concept["shared_environment"], recommended_background_color=concept["background_color"], recommended_accent_color=concept["accent_color"], recommended_camera_angle=concept["camera_angle"], props=list(dict.fromkeys(concept["left_props"] + concept["right_props"])), execution_risks=concept["execution_risks"], why_someone_would_share=concept["why_it_may_work"], notes=f"Concept Generator batch {concept['batch_id']}.", status="Approved",
        )

    def _parse_chat(self, message: str) -> tuple[str, str, str, str, str]:
        lower = message.lower().strip()
        if "girl" in lower and "left" in lower:
            return "character_preference", "girl alone on the left", "girl_left", "medium", "Noted. I’ll increase Girl-alone concepts on the left while keeping character usage balanced."
        if "brand" in lower:
            return "brand_preference", "natural brand placement", "more_brand_friendly", "medium", "Got it. I’ll favor moments where a product can replace a prop the story already needs."
        if "fun" in lower or "playful" in lower:
            return "tone_preference", "playful concepts", "playful", "medium", "Got it. I’ll give playful, visually simple concepts more weight in the next batch."
        if "summer" in lower:
            return "seasonal_preference", "summer concepts", "summer", "medium", "I’ll prioritize summer routines without labeling evergreen ideas as current trends."
        negative = any(word in lower for word in ("stop", "less", "don't", "do not", "avoid"))
        topic = re.sub(r"\b(stop|giving|give|me|so|many|more|less|please|i|want|do not|don't|avoid|of|this|week)\b", " ", lower)
        topic = " ".join(topic.split()).strip(" .") or "overused topic"
        if negative:
            kind = "avoid" if "stop" in lower or "avoid" in lower else "less_of"
            strength = "strong" if kind == "avoid" else "medium"
            return kind, topic, topic, strength, f"Got it. I’ll reduce {topic} and protect more room for fresher settings in the next batch."
        return "more_of", topic, topic, "medium", f"Noted. I’ll treat {topic} as a positive creative signal for the next batch."

    def _upsert_preference(self, kind: str, topic: str, value: str, strength: str, source: str, source_reference: str | None, *, active: bool) -> dict[str, Any]:
        records = self.preferences()
        now = datetime.now(UTC).isoformat()
        for index, record in enumerate(records):
            if record["preference_type"] == kind and record["topic"].lower() == topic.lower():
                record.update({"value": value, "strength": strength, "source": source, "source_reference": source_reference, "updated_at": now, "active": active})
                records[index] = ContentPreference.model_validate(record).model_dump(mode="json")
                self.repository.write_json(PREFERENCES_PATH, records)
                return records[index]
        record = ContentPreference(id=f"preference-{uuid.uuid4().hex[:12]}", preference_type=kind, topic=topic, value=value, strength=strength, source=source, source_reference=source_reference, confidence="high" if source in {"content_agent_chat", "concept_generator_chat"} else "medium", created_at=now, updated_at=now, active=active).model_dump(mode="json")
        records.append(record)
        self.repository.write_json(PREFERENCES_PATH, records)
        return record

    def _infer_possible_preference(self, reason: str | None) -> None:
        if not reason:
            return
        matches = [item for item in self.repository.read_json(FEEDBACK_PATH, []) if item.get("action") == "rejected" and (item.get("feedback_note") or "").lower() == reason.lower()]
        if len(matches) >= 6 and len({item["batch_id"] for item in matches}) >= 3:
            self._upsert_preference("less_of", reason, reason, "medium", "behavior_inference", None, active=False)

    @staticmethod
    def _source_summary(source: dict[str, Any]) -> str:
        label = "Clearly labeled development fixtures" if source["development_fixture"] else f"Structured output from {source['provider']}"
        return f"{label}; used {source['social_posts']} owned posts, {source['strong_learnings']} strong learnings, {source['used_storylines']} used storylines, and {source['current_trends']} verified current trends."


# Backward-compatible import for integrations written before the consolidation.
ContentAgentService = ConceptGeneratorService
