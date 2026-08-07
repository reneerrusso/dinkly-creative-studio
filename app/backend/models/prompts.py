from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PromptGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    concept_id: str | None = None
    format: str = "x-with-you"
    title_pair: dict[str, str] = Field(default_factory=dict)
    left_character: Literal["boy", "girl"] | None = None
    left_character_action: str = ""
    left_setting: str = ""
    left_props: list[str] = Field(default_factory=list)
    left_emotion: str = ""
    right_characters: Literal["boy_and_girl"] = "boy_and_girl"
    right_character_actions: str = ""
    right_setting: str = ""
    right_props: list[str] = Field(default_factory=list)
    right_emotion: str = ""
    shared_environment: str = ""
    environmental_contrast: str = ""
    left_scene: str = ""
    right_scene: str = ""
    emotional_insight: str = ""
    recommended_background_color: str = "warm cream"
    recommended_accent_color: str = "muted mustard"
    recommended_camera_angle: str = "medium straight-on"
    props: list[str] = Field(default_factory=list)
    execution_risks: list[str] = Field(default_factory=list)
    brand_placement_opportunities: list[str] = Field(default_factory=list)
    product_references: list[str] = Field(default_factory=list)
    scene_reference_path: str | None = None
    scene_reference_analysis: str | None = None
    scene_reference_notes: str | None = None
    image_edit_mode: bool = False
    unchanged: str | None = None
    edit_region: str | None = None
    change: str | None = None
    do_not_introduce: str | None = None


class PromptSaveRequest(BaseModel):
    title: str = Field(min_length=1)
    format: str
    source_storyline_id: str | None = None
    template: str
    character_reference: str = "references/dinkly_young.png"
    product_references: list[str] = Field(default_factory=list)
    prompt: str = Field(min_length=20)
    status: Literal["draft", "approved", "rejected"] = "draft"
    approved_by: str | None = None
    qa_notes: str | None = None
    left_character: Literal["boy", "girl"] = "boy"


class BrandIntegrationRequest(BaseModel):
    brand: str = Field(min_length=1)
    product_category: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    uploaded_reference: str | None = None
    desired_storyline: str = Field(min_length=5)
    placement_type: Literal[
        "Natural prop", "Hero prop", "Background prop", "Second-pass replacement", "Placeholder-first"
    ] = "Natural prop"
    packaging_accuracy_priority: Literal["low", "medium", "high"] = "medium"
    evergreen_version_needed: bool = True
    usage_notes: str | None = None
