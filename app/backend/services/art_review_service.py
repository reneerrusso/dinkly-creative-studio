from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.models.reviews import ArtReviewInput, EditPromptRequest
from app.backend.services.repository_service import RepositoryService

STRUCTURAL_FAILURES = {
    "Long legs",
    "Characters different sizes",
    "Standing on furniture",
    "Sitting on table",
    "Inside cart",
    "Floating",
    "Realistic environment",
    "Product distorted",
}
IDENTITY_FAILURES = {"Wrong eyes", "Three hair tufts", "Missing bow", "Wrong ponytail"}

CORRECTIONS = {
    "Wrong eyes": "Restore the exact black oval eyes with white highlights from the official character model.",
    "Long legs": "Remove all visible legs; attach tiny nub feet directly to each round body.",
    "Three hair tufts": "Edit Dinko to have exactly two hair tufts.",
    "Characters different sizes": "Match Dinka and Dinko to the same round body size and depth plane.",
    "Missing bow": "Restore Dinka's bright-red bow without changing her head shape.",
    "Wrong ponytail": "Restore Dinka's connected ponytail silhouette from the model sheet.",
    "Standing on furniture": "Move the character to the floor or a visible seat surface; do not alter furniture design.",
    "Sitting on table": "Move the body from the tabletop to a visible chair seat.",
    "Inside cart": "Place both characters on the floor beside the cart; only products remain inside.",
    "Floating": "Align nub feet to the visible floor baseline with no gap.",
    "Oversized prop": "Scale the affected prop relative to the character without changing other objects.",
    "Busy background": "Remove secondary decorative clutter while keeping the core environment.",
    "White background": "Restore the requested single pastel or dark background across the full canvas.",
    "Wrong background color": "Change only the background to the specified color and preserve all foreground colors.",
    "Realistic environment": "Flatten the environment into clean rounded 2D vector shapes with no texture or dramatic light.",
    "Text error": "Replace only the incorrect caption with the exact supplied text and no quotation marks.",
    "Product distorted": "Replace only the product region using the product reference; preserve character style completely.",
}


class ArtReviewService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def list(self) -> list[dict[str, Any]]:
        return self.repository.read_json("app-data/art_reviews.json", [])

    def create(self, payload: ArtReviewInput) -> tuple[dict[str, Any], str | None]:
        recommendation = self.edit_prompt(
            EditPromptRequest(
                failures=payload.failures,
                notes=payload.notes,
                unchanged=payload.unchanged,
                edit_attempts=payload.edit_attempts,
            )
        )
        record = payload.model_dump(mode="json")
        record.update(
            {
                "id": f"review-{uuid.uuid4().hex[:12]}",
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                **recommendation,
            }
        )
        records = self.list()
        records.append(record)
        backup = self.repository.write_json("app-data/art_reviews.json", records)
        return record, backup

    def edit_prompt(self, payload: EditPromptRequest) -> dict[str, Any]:
        structural_count = len(set(payload.failures) & STRUCTURAL_FAILURES)
        identity_wrong = bool(set(payload.failures) & IDENTITY_FAILURES)
        regenerate = len(payload.failures) > 3 or structural_count >= 2 or identity_wrong or payload.edit_attempts >= 2
        corrections = [CORRECTIONS.get(failure, f"Correct only this issue: {failure}.") for failure in payload.failures]
        prompt = "\n\n".join(
            [
                "EDIT BOUNDARY\nEdit only the affected regions named below. Do not regenerate the full scene.",
                f"KEEP UNCHANGED\n{payload.unchanged}",
                "EXACT CORRECTIONS\n" + "\n".join(f"- {item}" for item in corrections),
                "DO NOT INTRODUCE\nNo new anatomy, props, text, colors, lighting, perspective changes, or character redesigns.",
                f"REVIEW NOTES\n{payload.notes or 'No additional notes.'}",
            ]
        )
        return {
            "recommendation": "full regeneration" if regenerate else "targeted edit",
            "regenerate": regenerate,
            "reason": self._reason(payload.failures, structural_count, identity_wrong, payload.edit_attempts),
            "edit_prompt": prompt,
        }

    @staticmethod
    def _reason(failures: list[str], structural_count: int, identity_wrong: bool, attempts: int) -> str:
        if attempts >= 2:
            return "Two targeted edit attempts have already failed."
        if identity_wrong:
            return "Character identity is significantly off-model."
        if structural_count >= 2:
            return "Multiple structural failures make a local edit unreliable."
        if len(failures) > 3:
            return "More than three failures are selected."
        return "The selected errors appear locally repairable."

