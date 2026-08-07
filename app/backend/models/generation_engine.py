from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ModelSelection = Literal["automatic", "lite", "balanced", "pro"]
RunStatus = Literal[
    "draft",
    "compiling",
    "generating",
    "reviewing",
    "repairing",
    "awaiting_human",
    "approved",
    "rejected",
    "failed",
]


class StoryBrief(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    concept_id: str | None = None
    format: str = "x-with-you"
    title_left: str = ""
    title_right: str = ""
    left_character: Literal["boy", "girl"] = "boy"
    left_action: str = ""
    left_setting: str = ""
    left_props: list[str] = Field(default_factory=list, max_length=6)
    left_emotion: str = "Neutral, bored, or gently sad—never happy."
    right_characters: list[Literal["boy", "girl"]] = Field(default_factory=lambda: ["boy", "girl"])
    right_action: str = ""
    right_setting: str = ""
    right_props: list[str] = Field(default_factory=list, max_length=6)
    right_emotion: str = "Warm and connected because the ordinary moment is shared."
    shared_environment: str = ""
    environmental_contrast: str = ""
    background_color: str = "warm cream"
    accent_color: str = "muted mustard"
    camera_angle: str = "medium straight-on"
    execution_risks: list[str] = Field(default_factory=list)
    emotional_insight: str = ""
    brand_sensitive: bool = False
    comics: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_story_shape(self) -> StoryBrief:
        if self.format in {"five_story", "five-comic"} and len(self.comics) != 5:
            raise ValueError("Five-comic stories require exactly five comic beats")
        if self.format not in {"five_story", "five-comic"} and not (self.title_left or self.title_right):
            raise ValueError("A story brief requires at least one title")
        return self


class StoryBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_text: str | None = Field(default=None, max_length=500)
    story_id: str | None = None
    story_brief: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_source(self) -> StoryBriefRequest:
        if not any((self.concept_text, self.story_id, self.story_brief)):
            raise ValueError("Enter a concept or choose a Story Library record")
        return self


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_brief: StoryBrief
    model_selection_mode: ModelSelection = "automatic"
    candidate_count: int = Field(default=4, ge=1, le=4)
    aspect_ratio: str = "1:1"
    confirm_pro: bool = False


class CandidateSelectRequest(BaseModel):
    selected: bool = True


class CandidateQaRequest(BaseModel):
    manual_findings: list[dict[str, Any]] | None = None


class CandidateRetryRequest(BaseModel):
    confirm_pro: bool = False


class RepairRequest(BaseModel):
    failures: list[str] = Field(default_factory=list)
    notes: str | None = None
    model_selection: Literal["same", "balanced", "pro"] = "same"
    confirm_pro: bool = False


class ApprovalRequest(BaseModel):
    approved_by: str = Field(default="Human reviewer", min_length=2, max_length=120)


class RejectRunRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ModelCompareRequest(BaseModel):
    story_brief: StoryBrief
    include_pro: bool = False
    confirm_pro: bool = False
    aspect_ratio: str = "1:1"


class ImageGenerationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["google_gemini"] = "google_gemini"
    default_selection: ModelSelection = "automatic"
    candidate_count: int = Field(default=4, ge=1, le=4)
    default_aspect_ratio: str = "1:1"
    default_resolution: str = "model_default"
    demo_mode: bool = True
    developer_mode: bool = False
    enable_paid_generation: bool = False
    maximum_cost_per_run: float = Field(default=1.0, ge=0)
    daily_image_budget: float = Field(default=5.0, ge=0)
    monthly_image_budget: float = Field(default=25.0, ge=0)
    automatic_pro_usage: bool = False
    warn_at_percent: int = Field(default=80, ge=1, le=100)
    hard_stop_at_percent: int = Field(default=100, ge=1, le=100)


class GeminiKeyInput(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)
