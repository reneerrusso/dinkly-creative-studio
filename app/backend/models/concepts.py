from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ConceptStatus = Literal["Draft", "Needs refinement", "Approved", "Prompt generated", "Published", "Archived"]
LeftCharacter = Literal["boy", "girl"]
RightCharacters = Literal["boy_and_girl"]


class TitlePair(BaseModel):
    left: str = Field(min_length=1, max_length=90)
    right: str = Field(min_length=1, max_length=90)


class ConceptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = "x-with-you"
    title_pair: TitlePair
    left_scene: str = Field(min_length=8)
    right_scene: str = Field(min_length=8)
    emotional_insight: str = Field(min_length=8)
    emotional_theme: str = "companionship"
    category: str = "Everyday routines"
    left_character: LeftCharacter = "boy"
    left_character_action: str = ""
    left_setting: str = ""
    left_props: list[str] = Field(default_factory=list)
    left_emotion: str = "Neutral, bored, or gently sad—never happy."
    right_characters: RightCharacters = "boy_and_girl"
    right_character_actions: str = ""
    right_setting: str = ""
    right_props: list[str] = Field(default_factory=list)
    right_emotion: str = "Warm and connected because the moment is shared."
    shared_environment: str = ""
    environmental_contrast: str = ""
    recommended_background_color: str = "warm cream"
    recommended_accent_color: str = "muted mustard"
    recommended_camera_angle: str = "medium straight-on"
    brand_friendly: bool = False
    potential_product_category: str | None = None
    notes: str | None = None
    why_someone_would_share: str = "It reflects an ordinary relationship moment people recognize."
    props: list[str] = Field(default_factory=list)
    execution_risks: list[str] = Field(default_factory=list)
    brand_placement_opportunities: list[str] = Field(default_factory=list)
    brand_categories: list[str] = Field(default_factory=list)
    natural_product_placement: str | None = None
    novel_angle: str = ""
    status: ConceptStatus = "Draft"
    migration_version: Literal[2] = 2


class ConceptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str | None = None
    title_pair: TitlePair | None = None
    left_scene: str | None = None
    right_scene: str | None = None
    emotional_insight: str | None = None
    emotional_theme: str | None = None
    category: str | None = None
    left_character: LeftCharacter | None = None
    left_character_action: str | None = None
    left_setting: str | None = None
    left_props: list[str] | None = None
    left_emotion: str | None = None
    right_characters: RightCharacters | None = None
    right_character_actions: str | None = None
    right_setting: str | None = None
    right_props: list[str] | None = None
    right_emotion: str | None = None
    shared_environment: str | None = None
    environmental_contrast: str | None = None
    recommended_background_color: str | None = None
    recommended_accent_color: str | None = None
    recommended_camera_angle: str | None = None
    brand_friendly: bool | None = None
    potential_product_category: str | None = None
    notes: str | None = None
    why_someone_would_share: str | None = None
    props: list[str] | None = None
    execution_risks: list[str] | None = None
    brand_placement_opportunities: list[str] | None = None
    brand_categories: list[str] | None = None
    natural_product_placement: str | None = None
    novel_angle: str | None = None
    status: ConceptStatus | None = None


class ConceptRecord(ConceptCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    score: dict | None = None
    source: str = "app"


class ConceptScoreRequest(BaseModel):
    save: bool = True
