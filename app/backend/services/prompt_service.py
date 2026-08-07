from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.models.prompts import BrandIntegrationRequest, PromptGenerateRequest, PromptSaveRequest
from app.backend.services.concept_service import ConceptService
from app.backend.services.repository_service import RepositoryError, RepositoryService
from scripts.generate_prompt_brief import generate_prompt, relevant_failure_prevention


class PromptService:
    def __init__(self, repository: RepositoryService, concepts: ConceptService) -> None:
        self.repository = repository
        self.concepts = concepts

    def list(self) -> list[dict[str, Any]]:
        drafts = self.repository.read_json("app-data/prompts.json", [])
        approved = self.repository.read_json("data/approved_prompts.json", [])
        return sorted(drafts + approved, key=lambda item: item.get("created_at", ""), reverse=True)

    def generate(self, request: PromptGenerateRequest) -> dict[str, Any]:
        payload = request.model_dump(mode="json", exclude_none=True)
        if request.concept_id:
            concept = self.concepts.get(request.concept_id)
            merged = {**concept, **{key: value for key, value in payload.items() if value not in (None, "", [], {})}}
            payload = merged
        payload["left_character"] = payload.get("left_character") or "boy"
        payload["right_characters"] = "boy_and_girl"
        payload["left_scene"] = self._retarget_left_copy(
            str(payload.get("left_scene") or ""), str(payload["left_character"])
        )
        payload["left_character_action"] = self._retarget_left_copy(
            str(payload.get("left_character_action") or ""), str(payload["left_character"])
        )
        if request.image_edit_mode:
            payload["format"] = "image-edit"
        template, prompt = generate_prompt(payload)
        if request.scene_reference_path or request.scene_reference_analysis:
            prompt = self._add_scene_reference(
                prompt,
                request.scene_reference_path,
                request.scene_reference_analysis,
                request.scene_reference_notes,
            )
        return {
            "template": template.name,
            "format": payload.get("format", "split-comic"),
            "prompt": prompt,
            "sections": self._sections(prompt),
            "rules_included": self._rules(payload),
            "character_reference": payload.get("character_reference", "references/dinkly_young.png"),
            "scene_reference_path": request.scene_reference_path,
            "scene_reference_analysis": request.scene_reference_analysis,
            "left_character": payload["left_character"],
        }

    def save(self, request: PromptSaveRequest) -> tuple[dict[str, Any], str | None]:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        record = request.model_dump(mode="json")
        record.update(
            {
                "id": f"prompt-{uuid.uuid4().hex[:12]}",
                "approved_at": now if request.status == "approved" else None,
                "created_at": now,
            }
        )
        if request.status == "approved":
            if not request.approved_by:
                raise RepositoryError("Approved prompts require an approval owner")
            relative = "data/approved_prompts.json"
            schema = "schemas/prompt_record.schema.json"
        else:
            relative = "app-data/prompts.json"
            schema = None
        return self.repository.append_unique(relative, record, id_field="id", schema_relative=schema)

    def update(self, prompt_id: str, request: PromptSaveRequest) -> tuple[dict[str, Any], str | None]:
        for relative in ("app-data/prompts.json", "data/approved_prompts.json"):
            records = self.repository.read_json(relative, [])
            for index, record in enumerate(records):
                if record.get("id") == prompt_id:
                    updated = {**record, **request.model_dump(mode="json")}
                    if updated["status"] == "approved" and not updated.get("approved_by"):
                        raise RepositoryError("Approved prompts require an approval owner")
                    updated["approved_at"] = (
                        updated.get("approved_at") or datetime.now(UTC).isoformat(timespec="seconds")
                        if updated["status"] == "approved"
                        else None
                    )
                    records[index] = updated
                    schema = "schemas/prompt_record.schema.json" if relative.startswith("data/") else None
                    backup = self.repository.write_json(
                        relative, records, schema_relative=schema, validate_each=bool(schema)
                    )
                    return updated, backup
        raise RepositoryError("Prompt not found")

    def generate_brand_integration(self, request: BrandIntegrationRequest) -> dict[str, Any]:
        warnings: list[str] = []
        if request.placement_type == "Hero prop":
            warnings.append("Hero placement can make the scene feel like an advertisement; preserve a complete unbranded story.")
        if request.packaging_accuracy_priority == "high":
            warnings.append("Use a placeholder-first character pass, then replace only the product region.")
        if request.uploaded_reference:
            warnings.append("Label the uploaded file as product identity only; it must not influence character style.")
        base = (
            f"Story first: {request.desired_storyline}. Use {request.product_name} from {request.brand} only as a "
            f"{request.placement_type.lower()} that the scene already needs. Keep Dinka and Dinko as the visual priority."
        )
        placeholder = (
            f"Generate the complete DINKLY scene using one flat {request.product_category.lower()} placeholder with no logo. "
            "Lock character identity, background, text, and composition before product replacement."
        )
        branded = (
            f"Edit only the placeholder product region. Match the supplied {request.brand} {request.product_name} reference. "
            "Do not alter characters, captions, background, composition, or surrounding props."
        )
        evergreen = (
            f"Replace branded packaging with a generic one-color {request.product_category.lower()} prop. "
            "Remove logos and campaign copy while preserving the emotional story."
        )
        return {
            "story_first_summary": base,
            "warnings": warnings,
            "placeholder_prompt": placeholder,
            "branded_prompt": branded,
            "evergreen_prompt": evergreen if request.evergreen_version_needed else None,
            "second_pass_prompt": branded,
        }

    def _sections(self, prompt: str) -> list[dict[str, str]]:
        parts = re.split(r"(?m)^##\s+", prompt)
        sections: list[dict[str, str]] = []
        for part in parts[1:]:
            title, _, content = part.partition("\n")
            sections.append({"title": title.strip(), "content": content.strip()})
        return sections

    def _rules(self, payload: dict[str, Any]) -> list[str]:
        text = relevant_failure_prevention(payload)
        rules = [part.strip() for part in re.split(r"(?<=\.)\s+", text) if part.strip()]
        if payload.get("left_character") == "girl":
            rules.insert(0, "Girl DINKLY is alone in the left panel with her exact bright-red bow and connected ponytail.")
        else:
            rules.insert(0, "Boy DINKLY is alone in the left panel with exactly two hair tufts.")
        rules.insert(1, "The right panel always contains Boy DINKLY and Girl DINKLY together at equal body size.")
        if payload.get("scene_reference_path") or payload.get("scene_reference_analysis"):
            rules.insert(
                0,
                "The written source-comic analysis controls environment, storyline, framing, placement, and emotion only; the official DINKLY model sheet controls every character and the complete art style.",
            )
        return rules

    def _retarget_left_copy(self, value: str, left_character: str) -> str:
        if not value:
            return value
        lowered = value.lower()
        if (
            ("boy dinkly" in lowered and "girl dinkly" in lowered)
            or "boy and girl dinkly" in lowered
            or "girl and boy dinkly" in lowered
            or ("dinko" in lowered and "dinka" in lowered)
        ):
            # A single-panel or five-story beat may intentionally contain the
            # pair. Left-panel identity retargeting must never erase one of them.
            return value
        if left_character == "girl":
            replacements = (
                (r"\bBoy DINKLY\b", "Girl DINKLY"),
                (r"\bDinko\b", "Dinka"),
                (r"\bthe boy\b", "the girl"),
            )
        else:
            replacements = (
                (r"\bGirl DINKLY\b", "Boy DINKLY"),
                (r"\bDinka\b", "Dinko"),
                (r"\bthe girl\b", "the boy"),
            )
        for pattern, replacement in replacements:
            value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
        return value

    def _add_scene_reference(
        self,
        prompt: str,
        relative_path: str | None,
        analysis: str | None,
        notes: str | None,
    ) -> str:
        if relative_path:
            reference = self.repository.path(relative_path)
            if not reference.is_file() or not self.repository.relative(reference).startswith("app-data/uploads/"):
                raise RepositoryError("Scene reference must be an uploaded local image")
        written_analysis = (analysis or "").strip()
        written_notes = (notes or "").strip()
        source_description = written_analysis or written_notes
        if not source_description:
            source_description = (
                "No reliable automatic details were detected. Build a minimal DINKLY composition from the other supplied "
                "concept fields and do not invent a copy of any unknown source character or art style."
            )
        note_line = f"\n\nUser corrections or priorities: {written_notes}" if written_notes and written_notes != source_description else ""
        section = (
            "## SOURCE COMIC ANALYSIS — SELF-CONTAINED DINKLY ADAPTATION\n\n"
            "The original source image will not be available to or attached for the image generator. Use only the complete written "
            "analysis below to reconstruct its scene in the DINKLY universe.\n\n"
            f"Source scene description: {source_description}{note_line}\n\n"
            "Preserve the described environment, storyline, camera framing, relative character placement, physical interaction, and "
            "emotional beat. Preserve the same general pose intention and expressions, translated safely to round DINKLY nub anatomy.\n\n"
            "Do not copy any character identity, species, body design, facial design, anatomy, clothing, hairstyle, illustration style, "
            "rendering, linework, texture, lighting, palette, logos, captions, or decorative color treatment from the scene reference. "
            "Replace every depicted character with the exact official Dinka and Dinko models from references/dinkly_young.png. "
            "Dinka keeps her bright-yellow round body, official orange spots, black oval eyes with white highlights, bright-red bow, and connected ponytail. "
            "Dinko keeps his bright-yellow round body, official orange spots, black oval eyes with white highlights, and exactly two hair tufts. "
            "Both keep thick clean black outlines, equal round proportions, tiny nub arms, and nub feet with no visible legs, hands, fingers, clothing, or human anatomy.\n\n"
            "Rebuild the entire environment in the official DINKLY universe: flat matte 2D vector artwork, soft pastel background, rounded simplified furniture and props, "
            "large negative space, restrained accent colors, and no gradients, realism, 3D rendering, dramatic shadows, complex textures, or copied palette. "
            "If the scene reference conflicts with the official model sheet, DINKLY anatomy, DINKLY colors, or DINKLY visual style, the official DINKLY rules always win.\n"
        )
        priority = re.search(r"(?ms)^## REFERENCE PRIORITY\s*\n.*?(?=^## )", prompt)
        if priority:
            return f"{prompt[:priority.end()].rstrip()}\n\n{section}\n{prompt[priority.end():].lstrip()}"
        return f"{section}\n{prompt}"
