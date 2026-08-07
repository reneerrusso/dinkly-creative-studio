from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContentFormat(StrEnum):
    WITH_YOU = "with_you"
    BEFORE_AFTER = "before_after"
    FIVE_STORY = "five_story"


ContentStatus = Literal["candidate", "approved", "prompt_ready", "in_production", "used", "published", "passed", "archived"]


class ComicBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    scene: str = Field(min_length=12)
    characters: list[str] = Field(min_length=1)
    setting: str = Field(min_length=2)
    props: list[str] = Field(default_factory=list, max_length=5)
    emotion: str = Field(min_length=2)
    camera_angle: str = "medium straight-on"


class ContentConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    batch_id: str
    format: ContentFormat
    status: ContentStatus = "candidate"
    slot: int = Field(ge=1, le=10)
    title_left: str | None = None
    title_right: str | None = None
    story_title: str | None = None
    left_character: Literal["boy", "girl"] = "boy"
    left_action: str | None = None
    left_setting: str | None = None
    left_props: list[str] = Field(default_factory=list, max_length=5)
    left_emotion: str | None = None
    right_action: str | None = None
    right_characters: list[Literal["boy", "girl"]] = Field(default_factory=lambda: ["boy", "girl"])
    right_setting: str | None = None
    right_props: list[str] = Field(default_factory=list, max_length=5)
    right_emotion: str | None = None
    shared_environment: str | None = None
    environmental_contrast: str | None = None
    background_color: str = "warm cream"
    accent_color: str = "muted mustard"
    camera_angle: str = "medium straight-on"
    emotional_insight: str | None = None
    emotional_premise: str | None = None
    why_it_may_work: str
    timely_signal: str | None = None
    social_learning_ids: list[str] = Field(default_factory=list)
    preference_matches: list[str] = Field(default_factory=list)
    execution_risks: list[str] = Field(default_factory=list)
    transformation: str | None = None
    before_state: str | None = None
    after_state: str | None = None
    comics: list[ComicBeat] = Field(default_factory=list)
    final_payoff: str | None = None
    visual_continuity: str | None = None
    background_strategy: str | None = None
    approved_at: datetime | None = None
    used_at: datetime | None = None
    prompt_ids: list[str] = Field(default_factory=list)
    source_trend: str | None = None
    development_fixture: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_format_shape(self) -> ContentConcept:
        if self.format == ContentFormat.FIVE_STORY:
            if not self.story_title or len(self.comics) != 5 or not self.final_payoff:
                raise ValueError("Five-comic stories require a title, exactly five comics, and a final payoff")
        elif not all((self.title_left, self.title_right, self.left_action, self.right_action)):
            raise ValueError("Split concepts require titles and both scene actions")
        return self


class ContentBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    date: str
    created_at: datetime
    status: Literal["generating", "waiting_for_review", "completed", "failed", "supplemental"]
    source_summary: str
    with_you_count: int = 0
    before_after_count: int = 0
    five_story_count: int = 0
    approved_count: int = 0
    used_count: int = 0
    agent_run_id: str
    primary: bool = True
    development_fixture: bool = False
    generation_source: Literal["manual", "scheduled", "catch_up", "scheduler_test"] = "manual"
    scheduled_for: datetime | None = None


class ContentPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    preference_type: Literal["more_of", "less_of", "avoid", "prefer", "format_preference", "character_preference", "visual_preference", "tone_preference", "seasonal_preference", "brand_preference"]
    topic: str
    value: str
    strength: Literal["weak", "medium", "strong"]
    source: Literal["content_agent_chat", "concept_generator_chat", "approved_concepts", "behavior_inference", "user_edit"]
    source_reference: str | None = None
    confidence: Literal["low", "medium", "high"] = "high"
    created_at: datetime
    updated_at: datetime
    active: bool = True


class ContentFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept_id: str
    batch_id: str
    format: ContentFormat
    action: Literal["approved", "rejected", "skipped", "used", "published"]
    feedback_note: str | None = None
    timestamp: datetime


class UsedStoryline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    concept: dict[str, Any]
    format: ContentFormat
    date_generated: datetime
    date_approved: datetime | None = None
    date_used: datetime
    prompt_ids: list[str] = Field(default_factory=list)
    generation_ids: list[str] = Field(default_factory=list)
    published_post_ids: list[str] = Field(default_factory=list)
    performance_data: dict[str, Any] = Field(default_factory=dict)
    feedback: list[str] = Field(default_factory=list)
    source_batch: str
    source_trend: str | None = None
    status: Literal["used", "published"] = "used"


class BatchRequest(BaseModel):
    mode: Literal["primary", "replace_unreviewed", "supplemental"] = "primary"


class ConceptActionRequest(BaseModel):
    reason: str | None = None


class ConceptEditRequest(BaseModel):
    changes: dict[str, Any]


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)


class PreferenceUpdateRequest(BaseModel):
    topic: str | None = None
    value: str | None = None
    strength: Literal["weak", "medium", "strong"] | None = None
    active: bool | None = None


class ContentSettings(BaseModel):
    generate_daily_automatically: bool = False
    run_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "America/New_York"
    schedule_days: Literal["every_day", "weekdays"] = "every_day"
    catch_up_on_wake: bool = True
    catch_up_on_start: bool = True
    generate_on_start: bool = False  # Legacy alias retained for preserved settings.
    enable_paid_model_calls: bool = False
    maximum_automatic_batch_cost: float = Field(default=1.0, ge=0, le=1000)
    maximum_manual_batch_cost: float = Field(default=5.0, ge=0, le=1000)
    daily_model_budget: float = Field(default=5.0, ge=0, le=10000)
    monthly_model_budget: float = Field(default=25.0, ge=0, le=100000)
    last_scheduler_check: str | None = None

    @model_validator(mode="after")
    def validate_timezone_and_budgets(self) -> ContentSettings:
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        if self.monthly_model_budget < self.daily_model_budget:
            raise ValueError("monthly model budget cannot be lower than daily model budget")
        return self


class ContentProviderInput(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)
    model: str = Field(default="gpt-5.6-luna", min_length=2, max_length=120)
