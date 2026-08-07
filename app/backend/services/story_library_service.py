from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.backend.services.markdown_service import MarkdownService
from app.backend.services.repository_service import RepositoryService
from app.backend.services.story_normalization import normalize_story_record


class StoryLibraryService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.markdown = MarkdownService(repository)

    def list(self) -> list[dict]:
        stories = [
            normalize_story_record(record, source="data/story_library_v2.json")
            for record in self.repository.read_json("data/story_library_v2.json", [])
        ]
        v2_titles = {(story["title_left"], story["title_right"]) for story in stories}
        for section in self.markdown.sections("STORY_LIBRARY.md"):
            category = section["title"]
            for line in section["content"].splitlines():
                if not line.startswith("|") or "---" in line or "Seed" in line:
                    continue
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) < 3:
                    continue
                parts = re.split(r"\s*/\s*", cells[1], maxsplit=1)
                key = (parts[0], parts[1] if len(parts) > 1 else f"{parts[0]} WITH YOU")
                if key in v2_titles:
                    continue
                legacy = {
                    "id": (
                        "story-"
                        f"{re.sub(r'[^a-z0-9]+', '-', category.lower()).strip('-')}-"
                        f"{re.sub(r'[^a-z0-9]+', '-', cells[0].lower()).strip('-')}"
                    ),
                    "title": cells[0],
                    "title_direction": cells[1],
                    "concept": cells[2],
                    "visual_distinction": cells[3] if len(cells) > 3 else "",
                    "category": category,
                    "format": "x-with-you",
                    "approved": True,
                    "example_available": self.repository.path(f"EXAMPLES/{cells[0]}.md").exists(),
                    "source": "STORY_LIBRARY.md",
                }
                stories.append(normalize_story_record(legacy, category=category, source="STORY_LIBRARY.md"))
        stories.extend(
            normalize_story_record(record, source="app")
            for record in self.repository.read_json("app-data/story_library.json", [])
        )
        return stories

    def get(self, story_id: str) -> dict | None:
        return next((story for story in self.list() if story.get("id") == story_id), None)

    def find_by_titles(self, left: str, right: str) -> dict | None:
        normalized = (left.strip().rstrip(".").upper(), right.strip().rstrip(".").upper())
        return next(
            (
                story
                for story in self.list()
                if (
                    str(story.get("title_left", "")).strip().rstrip(".").upper(),
                    str(story.get("title_right", "")).strip().rstrip(".").upper(),
                )
                == normalized
            ),
            None,
        )

    def add_approved_concept(self, concept: dict[str, Any]) -> dict[str, Any]:
        """Persist one approved Concept Generator idea in the editable Story Library."""
        concept_id = str(concept.get("id") or "").strip()
        if not concept_id:
            raise ValueError("Approved concept is missing its id")

        records = self.repository.read_json("app-data/story_library.json", [])
        existing = next(
            (record for record in records if record.get("source_concept_id") == concept_id),
            None,
        )
        if existing:
            return normalize_story_record(existing, source="concept-generator")

        added_at = datetime.now(UTC).isoformat(timespec="seconds")
        record = self._approved_concept_record(concept, added_at)
        records.append(record)
        self.repository.write_json("app-data/story_library.json", records)
        return normalize_story_record(record, source="concept-generator")

    @staticmethod
    def _approved_concept_record(concept: dict[str, Any], added_at: str) -> dict[str, Any]:
        content_format = str(concept.get("format") or "with_you")
        if content_format == "five_story":
            comics = concept.get("comics") if isinstance(concept.get("comics"), list) else []
            first = comics[0] if comics else {}
            last = comics[-1] if comics else {}
            story_title = str(concept.get("story_title") or "FIVE-COMIC STORY")
            return {
                **concept,
                "id": f"story-concept-{concept['id']}",
                "source_concept_id": concept["id"],
                "source": "concept-generator",
                "title": story_title,
                "title_left": story_title,
                "title_right": "FIVE-COMIC STORY",
                "format": "five-story",
                "category": "Five-comic stories",
                "left_character_action": str(first.get("scene") or "The five-comic story begins."),
                "left_setting": str(first.get("setting") or "A simple DINKLY environment."),
                "left_props": list(first.get("props") or []),
                "left_emotion": str(first.get("emotion") or "Neutral, bored, or gently sad—never happy."),
                "right_character_actions": str(last.get("scene") or "The five-comic story reaches its shared payoff."),
                "right_setting": str(last.get("setting") or first.get("setting") or "The same DINKLY environment."),
                "right_props": list(last.get("props") or []),
                "right_emotion": str(last.get("emotion") or "Warm and connected because the moment is shared."),
                "concept": str(concept.get("emotional_premise") or concept.get("final_payoff") or concept.get("why_it_may_work") or ""),
                "status": "Approved",
                "approved": True,
                "approved_at": concept.get("approved_at") or added_at,
                "created_at": added_at,
                "added_to_library_at": added_at,
            }

        return {
            **concept,
            "id": f"story-concept-{concept['id']}",
            "source_concept_id": concept["id"],
            "source": "concept-generator",
            "title": str(concept.get("title_left") or "Approved concept").title(),
            "format": "before-after" if content_format == "before_after" else "x-with-you",
            "category": "Approved concepts",
            "left_character_action": concept.get("left_action"),
            "right_character_actions": concept.get("right_action"),
            "concept": concept.get("emotional_insight") or concept.get("why_it_may_work"),
            "status": "Approved",
            "approved": True,
            "approved_at": concept.get("approved_at") or added_at,
            "created_at": added_at,
            "added_to_library_at": added_at,
        }
