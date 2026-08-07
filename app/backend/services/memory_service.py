from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.models.memory import AgentMemory
from app.backend.services.cloud_persistence import cloud_database
from app.backend.services.repository_service import DOCUMENTS, RepositoryError, RepositoryService

MEMORY_PATH = "app-data/dinkly-agent/memories.json"
PROPOSALS_PATH = "app-data/dinkly-agent/brain-update-proposals.json"
PERFORMANCE_PATH = "app-data/generation-engine/performance-snapshots.json"


class MemoryExtractor:
    """Conservative classifier: chat remains chat unless it contains a durable signal."""

    def classify(self, message: str) -> str:
        lower = " ".join(message.lower().split())
        if re.search(r"\b(?:less|fewer|avoid|stop|don't|do not|more|prefer|always|never)\b", lower):
            return "creative_preference"
        if re.search(r"\b(?:love|like|hate|dislike)\b.*\b(?:style|comic|candidate|scene|look)\b", lower):
            return "feedback"
        if re.search(r"\b(?:keeps? happening|again|oversized|wrong|failure|mistake)\b", lower):
            return "production_learning"
        if re.search(r"\b(?:this|that|number)\s+(?:one|two|three|four|five|\d+)\b", lower):
            return "temporary_context"
        return "not_memory"

    def extract(
        self,
        message: str,
        *,
        source_type: str,
        source_id: str | None,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any] | None:
        classification = self.classify(message)
        if classification in {"temporary_context", "not_memory"}:
            return None
        cleaned = " ".join(message.strip().split())
        memory_type = {
            "creative_preference": "creative_preference",
            "feedback": "concept_preference",
            "production_learning": "failure_pattern",
        }[classification]
        key = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")[:80]
        now = datetime.now(UTC).isoformat()
        return {
            "id": f"memory-{hashlib.sha256(f'{memory_type}:{key}'.encode()).hexdigest()[:16]}",
            "memory_type": memory_type,
            "key": key or f"memory-{uuid.uuid4().hex[:8]}",
            "summary": cleaned,
            "value_json": {"classification": classification, "original_text": cleaned},
            "confidence": "high" if classification in {"creative_preference", "feedback"} else "low",
            "source_type": source_type,
            "source_id": source_id,
            "evidence_ids": evidence_ids or ([source_id] if source_id else []),
            "active": True,
            "created_at": now,
            "updated_at": now,
        }


class MemoryService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.extractor = MemoryExtractor()

    def list(self, *, memory_type: str | None = None, active: bool | None = True) -> list[dict[str, Any]]:
        if self.repository.settings.app_mode == "cloud":
            params = {"order": "updated_at.desc"}
            if memory_type:
                params["memory_type"] = f"eq.{memory_type}"
            if active is not None:
                params["active"] = f"eq.{str(active).lower()}"
            return cloud_database(self.repository.settings).select("agent_memories", params=params)
        records = self.repository.read_json(MEMORY_PATH, [])
        if memory_type:
            records = [item for item in records if item.get("memory_type") == memory_type]
        if active is not None:
            records = [item for item in records if bool(item.get("active", True)) is active]
        return sorted(records, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get(self, memory_id: str) -> dict[str, Any]:
        record = next((item for item in self.list(active=None) if item.get("id") == memory_id), None)
        if not record:
            raise RepositoryError("DINKLY Memory record not found")
        return record

    def upsert(self, record: dict[str, Any]) -> dict[str, Any]:
        validated = AgentMemory.model_validate(record).model_dump(mode="json")
        if self.repository.settings.app_mode == "cloud":
            rows = cloud_database(self.repository.settings).upsert(
                "agent_memories", validated, on_conflict="memory_type,key"
            )
            return rows[0] if rows else validated
        records = self.repository.read_json(MEMORY_PATH, [])
        match = next(
            (
                index
                for index, item in enumerate(records)
                if item.get("id") == validated["id"]
                or (item.get("memory_type"), item.get("key")) == (validated["memory_type"], validated["key"])
            ),
            None,
        )
        if match is None:
            records.append(validated)
        else:
            existing = records[match]
            validated["created_at"] = existing.get("created_at", validated["created_at"])
            validated["evidence_ids"] = list(dict.fromkeys((existing.get("evidence_ids") or []) + validated["evidence_ids"]))
            records[match] = validated
        self.repository.write_json(MEMORY_PATH, records)
        return validated

    def extract_and_store(
        self,
        message: str,
        *,
        source_type: str,
        source_id: str | None,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any] | None:
        record = self.extractor.extract(
            message, source_type=source_type, source_id=source_id, evidence_ids=evidence_ids
        )
        return self.upsert(record) if record else None

    def update(self, memory_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        existing = self.get(memory_id)
        updated = {**existing, **changes, "updated_at": datetime.now(UTC).isoformat()}
        return self.upsert(updated)

    def delete(self, memory_id: str) -> None:
        self.get(memory_id)
        if self.repository.settings.app_mode == "cloud":
            cloud_database(self.repository.settings).delete("agent_memories", filters={"id": f"eq.{memory_id}"})
            return
        self.repository.write_json(
            MEMORY_PATH,
            [item for item in self.repository.read_json(MEMORY_PATH, []) if item.get("id") != memory_id],
        )

    def answer(self, question: str) -> dict[str, Any]:
        relevant = MemoryRetriever(self).retrieve(question, limit=12)
        if not relevant:
            return {"answer": "I do not have evidence-backed memory for that yet.", "memory_refs": []}
        lines = [f"• {item['summary']} ({item['confidence']} confidence)" for item in relevant]
        return {
            "answer": "Here is what I know from stored evidence:\n" + "\n".join(lines),
            "memory_refs": [item["id"] for item in relevant],
            "evidence_ids": list(dict.fromkeys(evidence for item in relevant for evidence in item.get("evidence_ids", []))),
        }


class KnowledgeRetriever:
    ROUTES = {
        "character": ("character-bible",),
        "coffee": ("nano-banana-rules", "failures"),
        "brand": ("brand-integrations",),
        "social": ("social-learning", "viral-framework"),
        "prompt": ("nano-banana-rules", "failures"),
    }

    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def retrieve(self, task: str) -> list[dict[str, Any]]:
        lower = task.lower()
        slugs = {"creative-bible", "character-bible", "style-guide"}
        for token, routed in self.ROUTES.items():
            if token in lower:
                slugs.update(routed)
        records = []
        for slug in sorted(slugs):
            path = self.repository.path(DOCUMENTS[slug])
            if not path.is_file():
                continue
            records.append(
                {"id": slug, "path": DOCUMENTS[slug], "title": self.repository.read_markdown(slug)["title"]}
            )
        return records


class MemoryRetriever:
    def __init__(self, service: MemoryService) -> None:
        self.service = service

    def retrieve(self, task: str, *, limit: int = 8) -> list[dict[str, Any]]:
        lower = task.lower()
        tokens = {token for token in re.findall(r"[a-z0-9]+", lower) if len(token) > 2}
        preferred_types: set[str] = set()
        if any(token in lower for token in ("mistake", "failure", "wrong", "keeps happening")):
            preferred_types.update({"failure_pattern", "qa_learning"})
        if any(token in lower for token in ("perform", "views", "shares", "saves")):
            preferred_types.add("performance_learning")
        if "preference" in lower or "my style" in lower:
            preferred_types.update({"creative_preference", "concept_preference"})
        broad_learning_query = "learned" in lower or "what do you know" in lower
        records = self.service.list(active=True)
        scored = []
        for record in records:
            haystack = json.dumps(record, ensure_ascii=False).lower()
            score = sum(token in haystack for token in tokens)
            if record.get("memory_type") in preferred_types:
                score += 4
            if score or broad_learning_query or record.get("memory_type") == "creative_preference":
                scored.append((score, record.get("updated_at", ""), record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[:limit]]


class AgentContextBuilder:
    def __init__(self, repository: RepositoryService) -> None:
        self.knowledge = KnowledgeRetriever(repository)
        self.memory = MemoryRetriever(MemoryService(repository))

    def build(self, task: str) -> dict[str, Any]:
        brain = self.knowledge.retrieve(task)
        memories = self.memory.retrieve(task)
        return {
            "brain": brain,
            "memories": memories,
            "brain_refs_used": [item["id"] for item in brain],
            "memory_refs_used": [item["id"] for item in memories],
        }
