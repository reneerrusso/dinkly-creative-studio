from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class HandleCategory(StrEnum):
    OWNED = "Owned account"
    COMPETITOR = "Direct competitor"
    INSPIRATION = "Inspiration"
    PUBLISHER = "Publisher"
    CHARACTER_IP = "Character IP"
    RELATIONSHIP = "Relationship content"
    ILLUSTRATION = "Illustration"
    BRAND = "Brand"
    TREND = "Trend account"
    OTHER = "Other"


class RunStatus(StrEnum):
    RUNNING = "Running"
    COMPLETED = "Completed"
    WARNINGS = "Completed with warnings"
    PARTIAL = "Partial"
    BUDGET_STOPPED = "Budget stopped"
    RATE_LIMITED = "Rate limited"
    PROVIDER_UNAVAILABLE = "Provider unavailable"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    SKIPPED = "Skipped"


class ProviderConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=8, max_length=512)
    instagram_actor_id: str = Field(default="", max_length=200)
    tiktok_actor_id: str = Field(default="", max_length=200)
    instagram_enabled: bool = True
    tiktok_enabled: bool = True

    @field_validator("token")
    @classmethod
    def clean_token(cls, value: str) -> str:
        value = value.strip()
        if any(character.isspace() for character in value):
            raise ValueError("API tokens cannot contain whitespace")
        return value


class ActorIdsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instagram_actor_id: str = Field(default="", max_length=200)
    tiktok_actor_id: str = Field(default="", max_length=200)
    instagram_enabled: bool = True
    tiktok_enabled: bool = True


class BudgetSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_paid_provider_calls: bool = False
    maximum_estimated_cost_per_run: float = Field(default=1.0, ge=0, le=1000)
    daily_provider_budget: float = Field(default=2.0, ge=0, le=10000)
    monthly_provider_budget: float = Field(default=5.0, ge=0, le=100000)
    maximum_handles_per_refresh: int = Field(default=5, ge=1, le=100)
    maximum_posts_per_handle: int = Field(default=20, ge=1, le=100)
    maximum_provider_requests_per_run: int = Field(default=10, ge=1, le=500)
    maximum_retries: int = Field(default=2, ge=0, le=5)
    require_confirmation_above_estimated_cost: float = Field(default=0.5, ge=0, le=1000)
    automatically_pause_at_80_percent: bool = True
    hard_stop_at_100_percent: bool = True
    allow_paid_overage: bool = False
    schedule_enabled: bool = False
    schedule_frequency: Literal["Daily", "Every 3 days", "Weekly"] = "Weekly"
    connection_timeout_seconds: float = Field(default=10.0, ge=1, le=120)
    read_timeout_seconds: float = Field(default=30.0, ge=1, le=300)
    actor_run_timeout_seconds: float = Field(default=180.0, ge=10, le=3600)
    download_timeout_seconds: float = Field(default=20.0, ge=1, le=300)


class MonitoredHandleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform
    username: str = Field(min_length=1, max_length=80)
    category: HandleCategory = HandleCategory.OTHER
    enabled: bool = True
    provider: str = "apify"
    posts_per_refresh: int = Field(default=20, ge=1, le=100)
    refresh_frequency: Literal["Off", "Daily", "Every 3 days", "Weekly"] = "Off"
    notes: str = Field(default="", max_length=1000)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        from app.backend.services.handle_utils import normalize_handle

        return normalize_handle(value)


class MonitoredHandleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: HandleCategory | None = None
    enabled: bool | None = None
    provider: str | None = Field(default=None, max_length=80)
    posts_per_refresh: int | None = Field(default=None, ge=1, le=100)
    refresh_frequency: Literal["Off", "Daily", "Every 3 days", "Weekly"] | None = None
    notes: str | None = Field(default=None, max_length=1000)


class BulkHandleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=20000)
    default_platform: Platform | None = None
    category: HandleCategory = HandleCategory.OTHER


class HandleSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle_ids: list[str] = Field(default_factory=list, max_length=100)
    platforms: list[Platform] = Field(default_factory=list, max_length=2)
    posts_per_handle: int | None = Field(default=None, ge=1, le=100)
    scheduled: bool = False


class RefreshRequest(HandleSelection):
    confirmed: bool = False


class ManualPostInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    handle_id: str = Field(min_length=1, max_length=120)
    platform: Platform
    platform_post_id: str = Field(min_length=1, max_length=300)
    post_url: str | None = Field(default=None, max_length=2000)
    caption: str | None = Field(default=None, max_length=10000)
    hashtags: list[str] = Field(default_factory=list)
    posted_at: str | None = None
    media_type: str | None = Field(default=None, max_length=80)
    thumbnail_path: str | None = None
    remote_thumbnail_url: str | None = None
    media_url: str | None = None
    carousel_item_count: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    follower_count: int | None = Field(default=None, ge=0)
    audio_name: str | None = Field(default=None, max_length=500)
    creative_attributes: dict[str, Any] = Field(default_factory=dict)


class ClassificationOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creative_attributes: dict[str, Any]


class LearningDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str = Field(default="", max_length=2000)


class ConceptDirectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=3, ge=1, le=10)


class ProviderTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["apify"] = "apify"


class ProviderResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool = False

    @model_validator(mode="after")
    def require_confirmation(self) -> ProviderResumeRequest:
        if not self.confirmed:
            raise ValueError("Resuming provider calls requires explicit confirmation")
        return self
