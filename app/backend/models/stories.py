from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LeftCharacter = Literal["boy", "girl"]
RightCharacters = Literal["boy_and_girl"]
StoryStatus = Literal["Draft", "Needs refinement", "Approved", "Archived"]


class StoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_left: str = Field(min_length=1, max_length=90)
    title_right: str = Field(min_length=1, max_length=90)
    format: str = "x-with-you"
    category: str = Field(min_length=1)
    left_character: LeftCharacter = "boy"
    left_character_action: str = Field(min_length=3)
    left_setting: str = Field(min_length=3)
    left_props: list[str] = Field(default_factory=list)
    left_emotion: str = Field(min_length=3)
    right_characters: RightCharacters = "boy_and_girl"
    right_character_actions: str = Field(min_length=3)
    right_setting: str = Field(min_length=3)
    right_props: list[str] = Field(default_factory=list)
    right_emotion: str = Field(min_length=3)
    shared_environment: str = Field(min_length=3)
    environmental_contrast: str = Field(min_length=3)
    background_color: str = Field(min_length=1)
    accent_color: str = Field(min_length=1)
    camera_angle: str = Field(min_length=1)
    prop_count: int = Field(default=0, ge=0)
    brand_friendly: bool = False
    brand_categories: list[str] = Field(default_factory=list)
    execution_risks: list[str] = Field(default_factory=list)
    notes: str | None = None
    status: StoryStatus = "Draft"
    migration_version: Literal[2] = 2

    @model_validator(mode="after")
    def calculate_prop_count(self) -> StoryCreate:
        self.prop_count = max(len(self.left_props), len(self.right_props))
        return self

