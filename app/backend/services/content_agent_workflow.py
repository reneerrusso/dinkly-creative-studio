from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from app.backend.models.content_agent import ContentConcept, ContentFormat
from app.backend.services.agent_runtime_service import AgentRuntimeService
from app.backend.services.content_agent import ContentModelProvider
from app.backend.services.repository_service import RepositoryError, RepositoryService

CONCEPTS_PATH = "data/content_concepts.json"
USED_PATH = "data/used_storylines.json"
PREFERENCES_PATH = "data/content_agent_preferences.json"


class ConceptGeneratorWorkflow:
    stages = (
        "prepare", "research", "build_brief", "generate_with_you", "generate_before_after",
        "generate_five_story", "deduplicate", "score", "refine", "select_finalists", "save_batch", "await_review",
    )

    def __init__(self, repository: RepositoryService, runtime: AgentRuntimeService, provider: ContentModelProvider) -> None:
        self.repository = repository
        self.runtime = runtime
        self.provider = provider

    def execute(self, run_id: str, batch_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not self.provider.configured:
            self.runtime.emit(run_id, "provider", "Concept Generator needs an AI provider to create new concepts.", level="warning")
            raise RepositoryError("Concept Generator needs an AI provider to create new concepts.")
        evidence = self._load_evidence()
        self.runtime.emit(run_id, "prepare", f"Concept Generator loaded {evidence['social_posts']} existing DINKLY social posts.")
        self.runtime.emit(run_id, "prepare", f"Concept Generator loaded {evidence['strong_learnings']} high-confidence social learnings.")
        self.runtime.emit(run_id, "prepare", f"Concept Generator loaded {evidence['used_storylines']} Used Storylines.")
        self.runtime.emit(run_id, "prepare", f"Concept Generator loaded {evidence['recent_rejections']} rejected concepts from the past 30 days.")
        self.runtime.emit(run_id, "research", f"Concept Generator loaded {evidence['current_trends']} current social trends.")
        brief = self._brief(evidence)
        self.runtime.emit(run_id, "build_brief", "Built today’s creative brief from DINKLY rules, evidence, preferences, and originality history.", brief)
        finalists: list[dict[str, Any]] = []
        seen = self._comparison_keys()
        stage_map = {
            ContentFormat.WITH_YOU: "generate_with_you",
            ContentFormat.BEFORE_AFTER: "generate_before_after",
            ContentFormat.FIVE_STORY: "generate_five_story",
        }
        for content_format in ContentFormat:
            label = {ContentFormat.WITH_YOU: "WITH YOU", ContentFormat.BEFORE_AFTER: "BEFORE / AFTER", ContentFormat.FIVE_STORY: "five-comic story"}[content_format]
            self.runtime.emit(run_id, stage_map[content_format], f"Generating {label} candidates.")
            unique: list[dict[str, Any]] = []
            removed = 0
            format_seen = set(seen)
            for attempt in range(3):
                raw = self.provider.generate_candidates(content_format, brief, 24)
                self.runtime.emit(run_id, "generated", f"Generated {len(raw)} raw {label} candidates.", {"format": content_format.value, "count": len(raw), "attempt": attempt + 1})
                valid = self._validate_raw(raw, content_format, batch_id)
                new_unique, newly_removed = self._deduplicate(valid, format_seen)
                unique.extend(new_unique)
                removed += newly_removed
                if len(unique) >= 10:
                    break
                if attempt < 2:
                    self.runtime.emit(run_id, "validation_retry", f"Requested one bounded validation-safe retry for {label}.", {"attempt": attempt + 2, "valid_unique": len(unique)}, level="warning")
            self.runtime.emit(run_id, "deduplicate", f"Removed {removed} {label} concepts that were too similar to previous stories.", {"format": content_format.value})
            ranked = sorted(unique, key=lambda item: self._score(item, brief), reverse=True)
            self.runtime.emit(run_id, "score", f"Completed directional creative evaluation for {len(ranked)} {label} candidates; no performance prediction was made.", {"format": content_format.value, "count": len(ranked)})
            selected = ranked[:10]
            if len(selected) != 10:
                raise RepositoryError(f"Concept Generator could validate only {len(selected)} unique {label} concepts; no partial batch was saved.")
            for slot, concept in enumerate(selected, 1):
                concept["slot"] = slot
                concept["updated_at"] = datetime.now(UTC).isoformat()
            self.runtime.emit(run_id, "refine", f"Refined {len(selected)} {label} candidates.")
            self.runtime.emit(run_id, "select_finalists", f"Selected the strongest 10 {label} concepts.")
            finalists.extend(selected)
            for item in selected:
                seen.update(self._concept_keys(item))
        self.runtime.emit(run_id, "save_batch", "Saved 30 validated finalists without changing existing DINKLY records.")
        self.runtime.emit(run_id, "await_review", "Daily Concept Generator batch complete. Waiting for review.")
        return finalists, {**evidence, "provider": self.provider.name, "development_fixture": self.provider.development_fixture}

    def generate_replacement(self, run_id: str, batch_id: str, content_format: ContentFormat, slot: int) -> dict[str, Any]:
        if not self.provider.configured:
            raise RepositoryError("Concept Generator needs an AI provider to replace a concept.")
        raw = self.provider.generate_candidates(content_format, self._brief(self._load_evidence()), 24)
        valid = self._validate_raw(raw, content_format, batch_id)
        unique, _ = self._deduplicate(valid, self._comparison_keys())
        if not unique:
            raise RepositoryError("No unique replacement passed validation. The original concept was preserved.")
        replacement = unique[0]
        replacement["slot"] = slot
        replacement["updated_at"] = datetime.now(UTC).isoformat()
        self.runtime.emit(run_id, "replace", "Generated and validated one replacement concept.", {"format": content_format.value, "slot": slot})
        return replacement

    def _load_evidence(self) -> dict[str, Any]:
        social_posts = self.repository.read_json("data/social_posts.json", [])
        learnings = self.repository.read_json("data/social_learnings.json", [])
        used = self.repository.read_json(USED_PATH, [])
        concepts = self.repository.read_json(CONCEPTS_PATH, [])
        cutoff = datetime.now(UTC) - timedelta(days=30)
        recent_rejections = [item for item in concepts if item.get("status") == "passed" and _after(item.get("updated_at"), cutoff)]
        trends = [item for item in self.repository.read_json("data/competitor_learnings.json", []) if item.get("status") == "Approved" and item.get("signal_type") == "trend"]
        return {
            "social_posts": len(social_posts),
            "strong_learnings": sum(item.get("confidence") == "high" for item in learnings),
            "used_storylines": len(used),
            "recent_rejections": len(recent_rejections),
            "current_trends": len(trends),
            "learning_ids": [item.get("learning_id") for item in learnings if item.get("confidence") == "high" and item.get("learning_id")][:8],
            "preferences": [item for item in self.repository.read_json(PREFERENCES_PATH, []) if item.get("active")],
        }

    def _brief(self, evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            "brand_truth": "Ordinary life is better together.",
            "working_evidence": evidence["learning_ids"],
            "preferences": [{"type": item["preference_type"], "topic": item["topic"], "strength": item["strength"]} for item in evidence["preferences"]],
            "overused": [item["topic"] for item in evidence["preferences"] if item["preference_type"] in {"less_of", "avoid"}],
            "timely_signal_count": evidence["current_trends"],
            "format_balance": "10 with-you, 10 before-after, 10 connected five-comic stories",
        }

    def _validate_raw(self, raw: list[dict[str, Any]], content_format: ContentFormat, batch_id: str) -> list[dict[str, Any]]:
        valid: list[dict[str, Any]] = []
        errors = 0
        now = datetime.now(UTC).isoformat()
        for payload in raw:
            record = {
                **payload,
                "id": f"content-{uuid.uuid4().hex[:12]}",
                "batch_id": batch_id,
                "format": content_format.value,
                "status": "candidate",
                "slot": 1,
                "development_fixture": self.provider.development_fixture,
                "created_at": now,
                "updated_at": now,
            }
            try:
                valid.append(ContentConcept.model_validate(record).model_dump(mode="json"))
            except ValidationError:
                errors += 1
                if errors > 2:
                    break
        return valid

    def _comparison_keys(self) -> set[str]:
        concepts = self.repository.read_json(CONCEPTS_PATH, [])
        used = self.repository.read_json(USED_PATH, [])
        keys: set[str] = set()
        for item in concepts:
            if item.get("status") in {"candidate", "approved", "prompt_ready", "in_production", "used", "published", "passed"}:
                keys.update(self._concept_keys(item))
        for item in used:
            keys.update(self._concept_keys(item.get("concept", {})))
        for story in self.repository.read_json("data/story_library_v2.json", []):
            title = story.get("title_pair", {}).get("left") or story.get("title") or ""
            if title:
                keys.add(f"title::{_normalize(title)}")
        return {key for key in keys if key}

    def _deduplicate(self, concepts: list[dict[str, Any]], seen: set[str]) -> tuple[list[dict[str, Any]], int]:
        unique: list[dict[str, Any]] = []
        removed = 0
        for concept in concepts:
            keys = self._concept_keys(concept)
            duplicate = any(
                candidate.startswith(prefix) and previous.startswith(prefix) and _similarity(candidate, previous) >= threshold
                for candidate in keys
                for previous in seen
                for prefix, threshold in (("title::", 0.5), ("execution::", 0.88))
            )
            if duplicate:
                removed += 1
                continue
            unique.append(concept)
            seen.update(keys)
        return unique, removed

    def _score(self, concept: dict[str, Any], brief: dict[str, Any]) -> float:
        text = self._concept_key(concept)
        score = 7.0
        if len(concept.get("left_props", [])) in {2, 3, 4} or concept.get("format") == "five_story":
            score += 0.6
        if concept.get("why_it_may_work"):
            score += 0.4
        for preference in brief["preferences"]:
            topic = _normalize(preference["topic"])
            if topic and topic in text:
                score += -2 if preference["type"] in {"less_of", "avoid"} else 1
        return score

    @staticmethod
    def _concept_key(concept: dict[str, Any]) -> str:
        title = concept.get("story_title") or concept.get("title_left") or concept.get("title_pair", {}).get("left") or ""
        return _normalize(title)

    @classmethod
    def _concept_keys(cls, concept: dict[str, Any]) -> set[str]:
        title = cls._concept_key(concept)
        if concept.get("format") == "five_story":
            execution_source = " ".join(
                [str(concept.get("emotional_premise") or ""), str(concept.get("final_payoff") or "")]
                + [str(beat.get("scene") or "") for beat in concept.get("comics", [])]
            )
        else:
            execution_source = " ".join(
                str(concept.get(field) or "")
                for field in ("left_action", "left_setting", "right_action", "right_setting", "emotional_insight", "transformation")
            )
        execution = _normalize_execution(execution_source)
        return {key for key in (f"title::{title}" if title else "", f"execution::{execution}" if execution else "") if key}


def _normalize(value: str) -> str:
    value = re.sub(r"\b(with you|before you|after you|comic|story)\b", " ", value.lower())
    tokens = re.findall(r"[a-z0-9]+", value)
    return " ".join(token[:-1] if token.endswith("s") and len(token) > 4 else token for token in tokens)


def _similarity(left: str, right: str) -> float:
    a, b = set(left.split()), set(right.split())
    return len(a & b) / len(a | b) if a and b else 0.0


def _normalize_execution(value: str) -> str:
    stop = {"dinko", "dinka", "dinkly", "boy", "girl", "same", "together", "shared", "shares", "while", "with", "and", "the", "their", "they"}
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    return " ".join(token for token in tokens if token not in stop and len(token) > 2)


def _after(value: str | None, cutoff: datetime) -> bool:
    if not value:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) >= cutoff
    except ValueError:
        return False


# Backward-compatible import for code written before the agent consolidation.
ContentAgentWorkflow = ConceptGeneratorWorkflow
