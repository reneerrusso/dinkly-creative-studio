from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArtReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_path: str | None = None
    original_prompt: str | None = None
    target_concept_id: str | None = None
    failures: list[str] = Field(default_factory=list)
    notes: str | None = None
    unchanged: str = "Keep all unaffected areas, text, colors, characters, props, and composition unchanged."
    edit_attempts: int = Field(default=0, ge=0)


class EditPromptRequest(BaseModel):
    failures: list[str] = Field(min_length=1)
    notes: str | None = None
    unchanged: str = "Keep all unaffected areas, text, colors, characters, props, and composition unchanged."
    edit_attempts: int = Field(default=0, ge=0)

