from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.models.concepts import ConceptCreate, ConceptUpdate
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.story_normalization import normalize_story_record
from scripts.score_storyline import score_storyline


class ConceptService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def list(self, include_archived: bool = False) -> list[dict[str, Any]]:
        app_concepts_raw = self.repository.read_json("app-data/concepts.json", [])
        app_concepts = [normalize_story_record(item, source="app") for item in app_concepts_raw]
        seeded_scores = self.repository.read_json("data/storyline_scores.json", [])
        concepts = list(app_concepts)
        app_ids = {item.get("id") for item in app_concepts_raw}
        for score in seeded_scores:
            storyline_id = score.get("storyline_id")
            if storyline_id in app_ids:
                continue
            concepts.append(self._seed_to_concept(score))
        if not include_archived:
            concepts = [item for item in concepts if item.get("status") != "Archived"]
        return sorted(concepts, key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)

    def get(self, concept_id: str) -> dict[str, Any]:
        for concept in self.list(include_archived=True):
            if concept.get("id") == concept_id:
                return concept
        raise RepositoryError("Concept not found")

    def create(self, payload: ConceptCreate) -> tuple[dict[str, Any], str | None]:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        record = payload.model_dump(mode="json")
        record.update({"id": f"concept-{uuid.uuid4().hex[:12]}", "created_at": now, "updated_at": now, "score": None, "source": "app"})
        records = self.repository.read_json("app-data/concepts.json", [])
        records.append(record)
        backup = self.repository.write_json("app-data/concepts.json", records)
        return normalize_story_record(record, source="app"), backup

    def update(self, concept_id: str, payload: ConceptUpdate) -> tuple[dict[str, Any], str | None]:
        records = self.repository.read_json("app-data/concepts.json", [])
        for index, record in enumerate(records):
            if record.get("id") == concept_id:
                changes = payload.model_dump(mode="json", exclude_none=True)
                record.update(changes)
                record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
                records[index] = record
                backup = self.repository.write_json("app-data/concepts.json", records)
                return normalize_story_record(record, source="app"), backup
        raise RepositoryError("Only app-created concepts can be edited; duplicate a seeded concept first")

    def archive(self, concept_id: str) -> tuple[dict[str, Any], str | None]:
        return self.update(concept_id, ConceptUpdate(status="Archived"))

    def delete(self, concept_id: str) -> tuple[dict[str, Any], list[str]]:
        app_records = self.repository.read_json("app-data/concepts.json", [])
        score_records = self.repository.read_json("data/storyline_scores.json", [])
        deleted = next((record for record in app_records if record.get("id") == concept_id), None)

        backups: list[str] = []
        if deleted is not None:
            app_backup = self.repository.write_json(
                "app-data/concepts.json",
                [record for record in app_records if record.get("id") != concept_id],
            )
            if app_backup:
                backups.append(app_backup)

            related_scores = [record for record in score_records if record.get("storyline_id") == concept_id]
            if related_scores:
                score_backup = self.repository.write_json(
                    "data/storyline_scores.json",
                    [record for record in score_records if record.get("storyline_id") != concept_id],
                    schema_relative="schemas/storyline_score.schema.json",
                    validate_each=True,
                )
                if score_backup:
                    backups.append(score_backup)
            return deleted, backups

        matching_scores = [record for record in score_records if record.get("storyline_id") == concept_id]
        if matching_scores:
            deleted = self._seed_to_concept(matching_scores[0])
            score_backup = self.repository.write_json(
                "data/storyline_scores.json",
                [record for record in score_records if record.get("storyline_id") != concept_id],
                schema_relative="schemas/storyline_score.schema.json",
                validate_each=True,
            )
            if score_backup:
                backups.append(score_backup)
            return deleted, backups

        raise RepositoryError("Concept not found")

    def duplicate(self, concept_id: str) -> tuple[dict[str, Any], str | None]:
        source = self.get(concept_id)
        fields = ConceptCreate.model_fields
        payload = ConceptCreate(**{key: source.get(key) for key in fields if key in source})
        payload.status = "Draft"
        payload.notes = f"Duplicated from {concept_id}. {payload.notes or ''}".strip()
        return self.create(payload)

    def score(self, concept_id: str, save: bool = True) -> tuple[dict[str, Any], str | None]:
        concept = self.get(concept_id)
        learnings = self.repository.read_json("data/social_learnings.json", [])
        score = score_storyline(self._score_payload(concept), learnings)
        backup: str | None = None
        if save:
            scores = self.repository.read_json("data/storyline_scores.json", [])
            scores.append(score)
            backup = self.repository.write_json(
                "data/storyline_scores.json",
                scores,
                schema_relative="schemas/storyline_score.schema.json",
                validate_each=True,
            )
            if concept.get("source") == "app":
                records = self.repository.read_json("app-data/concepts.json", [])
                for record in records:
                    if record.get("id") == concept_id:
                        record["score"] = score
                        record["status"] = "Needs refinement" if score["directional_total"] < 7 else "Approved"
                        record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
                self.repository.write_json("app-data/concepts.json", records)
        return score, backup

    def _seed_to_concept(self, score: dict[str, Any]) -> dict[str, Any]:
        concept = {
            "id": score.get("storyline_id"),
            "format": score.get("format", "x-with-you"),
            "title_pair": score.get("title_pair", {}),
            "left_scene": score.get("left_scene", ""),
            "right_scene": score.get("right_scene", ""),
            "emotional_insight": score.get("emotional_insight", ""),
            "emotional_theme": "companionship",
            "recommended_background_color": score.get("recommended_background_color", "warm cream"),
            "recommended_accent_color": score.get("recommended_accent_color", "muted mustard"),
            "recommended_camera_angle": score.get("recommended_camera_angle", "medium straight-on"),
            "brand_friendly": bool(score.get("brand_placement_opportunities")),
            "potential_product_category": None,
            "notes": "Seeded from the directional storyline score library.",
            "why_someone_would_share": score.get("why_someone_would_share", ""),
            "props": score.get("props", []),
            "left_character": score.get("left_character", "boy"),
            "left_character_action": score.get("left_character_action", ""),
            "left_setting": score.get("left_setting", ""),
            "left_props": score.get("left_props", []),
            "left_emotion": score.get("left_emotion", ""),
            "right_characters": "boy_and_girl",
            "right_character_actions": score.get("right_character_actions", ""),
            "right_setting": score.get("right_setting", ""),
            "right_props": score.get("right_props", []),
            "right_emotion": score.get("right_emotion", ""),
            "shared_environment": score.get("shared_environment", ""),
            "environmental_contrast": score.get("environmental_contrast", ""),
            "execution_risks": score.get("execution_risks", []),
            "brand_placement_opportunities": score.get("brand_placement_opportunities", []),
            "novel_angle": score.get("novel_angle", ""),
            "status": "Prompt generated",
            "created_at": score.get("created_at"),
            "updated_at": score.get("created_at"),
            "score": score,
            "source": "storyline_scores",
        }
        return normalize_story_record(concept, source="storyline_scores")

    def _score_payload(self, concept: dict[str, Any]) -> dict[str, Any]:
        return {
            "storyline_id": concept.get("id"),
            "storyline": concept.get("title_pair", {}).get("left", ""),
            "title_pair": concept.get("title_pair"),
            "format": concept.get("format"),
            "left_scene": concept.get("left_scene"),
            "right_scene": concept.get("right_scene"),
            "emotional_insight": concept.get("emotional_insight"),
            "why_someone_would_share": concept.get("why_someone_would_share"),
            "brand_placement_opportunities": concept.get("brand_placement_opportunities", []),
            "execution_risks": concept.get("execution_risks", []),
            "recommended_background_color": concept.get("recommended_background_color"),
            "recommended_accent_color": concept.get("recommended_accent_color"),
            "recommended_camera_angle": concept.get("recommended_camera_angle"),
            "props": concept.get("props", []),
            "left_character": concept.get("left_character", "boy"),
            "left_character_action": concept.get("left_character_action", ""),
            "left_setting": concept.get("left_setting", ""),
            "left_props": concept.get("left_props", []),
            "left_emotion": concept.get("left_emotion", ""),
            "right_characters": "boy_and_girl",
            "right_character_actions": concept.get("right_character_actions", ""),
            "right_setting": concept.get("right_setting", ""),
            "right_props": concept.get("right_props", []),
            "right_emotion": concept.get("right_emotion", ""),
            "shared_environment": concept.get("shared_environment", ""),
            "environmental_contrast": concept.get("environmental_contrast", ""),
            "character_count": 2,
            "novel_angle": concept.get("novel_angle", ""),
        }
