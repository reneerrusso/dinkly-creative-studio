from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.backend.config import Settings
from app.backend.services.repository_service import RepositoryService

SOURCE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def repository(tmp_path: Path) -> RepositoryService:
    for directory in (
        "data",
        "schemas",
        "app-data",
        "app-data/sprites",
        "app-data/sprites/exports",
        "app-data/sprites/thumbnails",
        "PROMPT_TEMPLATES",
        "references",
        "scripts",
    ):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    for name in (
        "social_posts",
        "social_learnings",
        "storyline_scores",
        "approved_prompts",
        "monitored_handles",
        "competitor_profiles",
        "competitor_posts",
        "competitor_snapshots",
        "competitor_learnings",
        "competitor_concept_directions",
        "provider_usage",
        "content_batches",
        "content_concepts",
        "content_feedback",
        "content_agent_preferences",
        "used_storylines",
    ):
        (tmp_path / "data" / f"{name}.json").write_text("[]\n", encoding="utf-8")
    shutil.copy2(SOURCE_ROOT / "data" / "social_provider_actors.json", tmp_path / "data" / "social_provider_actors.json")
    for schema in (SOURCE_ROOT / "schemas").glob("*.schema.json"):
        shutil.copy2(schema, tmp_path / "schemas" / schema.name)
    for name in ("sprite_characters", "sprite_animations", "sprite_sheets", "sprite_compositions"):
        shutil.copy2(SOURCE_ROOT / "data" / f"{name}.json", tmp_path / "data" / f"{name}.json")
    shutil.copy2(
        SOURCE_ROOT / "scripts" / "sprite_image_worker.py",
        tmp_path / "scripts" / "sprite_image_worker.py",
    )
    for template in (SOURCE_ROOT / "PROMPT_TEMPLATES").glob("*.md"):
        shutil.copy2(template, tmp_path / "PROMPT_TEMPLATES" / template.name)
    for relative in (
        "concepts.json",
        "prompts.json",
        "art_reviews.json",
        "story_library.json",
        "agent_runs.json",
        "agent_events.json",
    ):
        (tmp_path / "app-data" / relative).write_text("[]\n", encoding="utf-8")
    (tmp_path / "app-data" / "provider_states.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "app-data" / "content_agent_chat.json").write_text("[]\n", encoding="utf-8")
    (tmp_path / "app-data" / "content_provider_usage.json").write_text("[]\n", encoding="utf-8")
    (tmp_path / "app-data" / "concept_generator_scheduler_state.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "app-data" / "concept_generator_worker_heartbeat.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "app-data" / "content_agent_settings.json").write_text(
        '{"generate_daily_automatically": false, "run_time": "08:00", "generate_on_start": false, "last_scheduler_check": null}\n',
        encoding="utf-8",
    )
    (tmp_path / "app-data" / "provider_budget.json").write_text(
        (SOURCE_ROOT / "app-data" / "provider_budget.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for relative in ("frames.json", "shared_interactions.json"):
        (tmp_path / "app-data" / "sprites" / relative).write_text("[]\n", encoding="utf-8")
    social_learning = (
        "# DINKLY Social Learning\n\n" + "Purpose and evidence rules for testing. " * 6
        + "\n<!-- GENERATED:START -->\nNothing yet.\n<!-- GENERATED:END -->\n"
    )
    (tmp_path / "SOCIAL_LEARNING.md").write_text(social_learning, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme\n\n" + "Local documentation. " * 10, encoding="utf-8")
    settings = Settings(tmp_path, "http://127.0.0.1:3000", 2 * 1024 * 1024)
    return RepositoryService(settings)


@pytest.fixture
def sample_concept_payload() -> dict:
    return {
        "format": "x-with-you",
        "title_pair": {"left": "RAIN", "right": "RAIN WITH YOU"},
        "left_scene": "Dinko waits under one umbrella with a neutral expression.",
        "right_scene": "Dinka and Dinko stand close under the same umbrella.",
        "emotional_insight": "Shared shelter makes ordinary rain feel warm and safe.",
        "emotional_theme": "care",
        "recommended_background_color": "powder blue",
        "recommended_accent_color": "muted coral",
        "recommended_camera_angle": "medium straight-on",
        "props": ["umbrella"],
        "execution_risks": ["long legs"],
        "brand_placement_opportunities": ["umbrella"],
        "novel_angle": "Dinka tilts the umbrella toward Dinko.",
    }
