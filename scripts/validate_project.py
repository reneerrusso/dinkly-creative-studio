#!/usr/bin/env python3
"""Validate the DINKLY Generation Engine and its preserved Creative Studio sources."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "CREATIVE_BIBLE.md",
    "CHARACTER_BIBLE.md",
    "STYLE_GUIDE.md",
    "VIRAL_FRAMEWORK.md",
    "SOCIAL_LEARNING.md",
    "STORY_LIBRARY.md",
    "NANO_BANANA_RULES.md",
    "QA_CHECKLIST.md",
    "BRAND_INTEGRATIONS.md",
    "FAILURES.md",
    "data/social_posts.json",
    "data/social_learnings.json",
    "data/storyline_scores.json",
    "data/approved_prompts.json",
    "data/generation_learnings.json",
    "data/prompt_learnings.json",
    "data/qa_learnings.json",
    "data/user_preferences.json",
    "data/story_library_v2.json",
    "data/content_batches.json",
    "data/content_concepts.json",
    "data/content_feedback.json",
    "data/content_agent_preferences.json",
    "data/used_storylines.json",
    "data/content_batches.json",
    "data/content_concepts.json",
    "data/content_feedback.json",
    "data/content_agent_preferences.json",
    "data/used_storylines.json",
    "PROMPT_TEMPLATES/SplitComic.md",
    "PROMPT_TEMPLATES/SinglePanel.md",
    "PROMPT_TEMPLATES/CloseUp.md",
    "PROMPT_TEMPLATES/BeforeAfter.md",
    "PROMPT_TEMPLATES/XWithYou.md",
    "PROMPT_TEMPLATES/BrandPlacement.md",
    "PROMPT_TEMPLATES/ImageEdit.md",
    "PROMPT_TEMPLATES/SocialLearningAnalysis.md",
    "EXAMPLES/Coffee.md",
    "EXAMPLES/Walks.md",
    "EXAMPLES/Bedtime.md",
    "EXAMPLES/Shopping.md",
    "EXAMPLES/Movies.md",
    "EXAMPLES/Weekends.md",
    "EXAMPLES/Laundry.md",
    "EXAMPLES/Mornings.md",
    "EXAMPLES/README.md",
    "agents/creative-director.md",
    "agents/social-learning-agent.md",
    "agents/prompt-engineer.md",
    "agents/art-qa-agent.md",
    "agents/brand-integration-agent.md",
    "agents/concept-generator.md",
    "scripts/ingest_social_post.py",
    "scripts/analyze_social_posts.py",
    "scripts/score_storyline.py",
    "scripts/generate_prompt_brief.py",
    "scripts/analyze_reference_image.swift",
    "scripts/validate_project.py",
    "scripts/demonstrate_social_intelligence.py",
    "scripts/demonstrate_content_agent.py",
    "schemas/social_post.schema.json",
    "schemas/social_learning.schema.json",
    "schemas/storyline_score.schema.json",
    "schemas/prompt_record.schema.json",
    "schemas/dinkly_agent_learning.schema.json",
    "schemas/agent_task.schema.json",
    "schemas/agent_conversation.schema.json",
    "schemas/story_record.schema.json",
    "tests/test_social_learning.py",
    "tests/test_storyline_scoring.py",
    "tests/test_character_rules.py",
    "tests/test_project_structure.py",
    "tests/test_agent_portraits.py",
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    ".env.example",
    "Dockerfile.backend",
    "Dockerfile.frontend",
    "migrations/0001_dinkly_cloud.sql",
    "scripts/apply_migrations.py",
    "scripts/migrate_local_to_cloud.py",
    "scripts/validate_migrations.py",
    "scripts/verify_cloud_deployment.py",
    "docs/CLOUD_DEPLOYMENT.md",
    "docs/SUPABASE_SETUP.md",
    "docs/SLACK_CLOUD_SETUP.md",
    "docs/DINKLY_MEMORY.md",
    "docs/DINKLY_LEARNING_ENGINE.md",
    "docs/CLOUD_ACCEPTANCE.md",
    "app/backend/main.py",
    "app/backend/config.py",
    "app/backend/services/repository_service.py",
    "app/backend/services/cloud_persistence.py",
    "app/backend/services/memory_service.py",
    "app/backend/services/learning_engine.py",
    "app/backend/routers/memory.py",
    "app/frontend/app/memory/page.tsx",
    "app/backend/services/social_learning_service.py",
    "app/backend/services/concept_service.py",
    "app/backend/services/prompt_service.py",
    "app/backend/services/reference_analysis_service.py",
    "app/backend/services/story_normalization.py",
    "app/backend/models/content_agent.py",
    "app/backend/models/concept_generator_agent.py",
    "app/backend/services/content_agent.py",
    "app/backend/services/content_agent_workflow.py",
    "app/backend/services/content_agent_service.py",
    "app/backend/services/content_agent_scheduler.py",
    "app/backend/services/concept_generator_agent.py",
    "app/backend/services/concept_generator_workflow.py",
    "app/backend/services/concept_generator_service.py",
    "app/backend/services/concept_generator_scheduler.py",
    "app/backend/services/concept_generator_schedule.py",
    "app/backend/services/concept_generator_background_service.py",
    "app/backend/workers/concept_generator_worker.py",
    "app/backend/routers/concept_generator.py",
    "app/backend/routers/content_agent.py",
    "app/backend/models/stories.py",
    "app/backend/services/art_review_service.py",
    "app/backend/services/markdown_service.py",
    "app/backend/routers/prompt_templates.py",
    "app/frontend/package.json",
    "app/frontend/app/layout.tsx",
    "app/frontend/app/page.tsx",
    "app/frontend/app/concepts/page.tsx",
    "app/frontend/app/concepts/new/page.tsx",
    "app/frontend/app/prompt-builder/page.tsx",
    "app/frontend/app/art-review/page.tsx",
    "app/frontend/app/social-learning/page.tsx",
    "app/frontend/app/social-learning/ingest/page.tsx",
    "app/frontend/app/story-library/page.tsx",
    "app/frontend/app/examples/page.tsx",
    "app/frontend/app/brand-integrations/page.tsx",
    "app/frontend/app/failures/page.tsx",
    "app/frontend/app/knowledge/page.tsx",
    "app/frontend/app/settings/page.tsx",
    "app/frontend/app/agents/[agentId]/page.tsx",
    "app/frontend/app/agents/content/page.tsx",
    "app/frontend/app/agents/concept-generator/page.tsx",
    "app/frontend/app/prompt-templates/page.tsx",
    "app/frontend/app/projects/generated-comics/page.tsx",
    "app/frontend/app/projects/approved-comics/page.tsx",
    "app/frontend/app/projects/exports/page.tsx",
    "app/frontend/components/agent-avatar.tsx",
    "app/frontend/components/agent-room.tsx",
    "app/frontend/components/concept-generator-scheduler-settings.tsx",
    "app/frontend/components/app-sidebar.tsx",
    "app/frontend/components/top-bar.tsx",
    "app/frontend/lib/agents.ts",
    "app/frontend/lib/api.ts",
    "app/frontend/lib/types.ts",
    "app/frontend/lib/schemas.ts",
    "app/frontend/public/dinkly-reference.png",
    "app/frontend/public/social-preview.png",
    "app/frontend/public/agents/creative-director.png",
    "app/frontend/public/agents/prompt-agent.png",
    "app/frontend/public/agents/art-review.png",
    "app/frontend/public/agents/social-intelligence.png",
    "app/frontend/public/agents/brand-integration.png",
    "app/frontend/public/agents/motion-director.png",
    "app/frontend/public/agents/concept-generator.png",
    "docs/AGENT_PORTRAITS.md",
    "app/frontend/tests/agent-portraits.test.tsx",
    "docs/CONCEPT_GENERATOR_AGENT.md",
    "docs/CONCEPT_GENERATOR_AUTOMATION.md",
    "docs/GENERATION_ENGINE.md",
    "app/backend/models/generation_engine.py",
    "app/backend/providers/image_provider.py",
    "app/backend/services/image_model_registry.py",
    "app/backend/services/generation_export_service.py",
    "app/backend/services/story_library_service.py",
    "app/backend/services/generation_engine_service.py",
    "app/backend/models/dinkly_agent.py",
    "app/backend/services/agent_visual_state_service.py",
    "app/backend/services/agent_storage.py",
    "app/backend/services/agent_task_service.py",
    "app/backend/services/agent_channels.py",
    "app/backend/services/agent_schedule_service.py",
    "app/backend/services/agent_background_service.py",
    "app/backend/services/dinkly_agent_runtime.py",
    "app/backend/services/secrets_service.py",
    "app/backend/routers/dinkly_agent.py",
    "app/backend/routers/slack.py",
    "app/backend/workers/dinkly_agent_worker.py",
    "app/backend/tests/test_dinkly_agent.py",
    "app/backend/routers/generation_engine.py",
    "app/backend/tests/test_generation_engine.py",
    "app/frontend/app/generate/page.tsx",
    "app/frontend/app/agent/page.tsx",
    "app/frontend/app/approvals/page.tsx",
    "app/frontend/app/history/page.tsx",
    "app/frontend/app/used-storylines/page.tsx",
    "app/frontend/components/image-generation-settings.tsx",
    "app/frontend/components/generation-progress.tsx",
    "app/frontend/components/dinkly-agent-status.tsx",
    "app/frontend/components/dinkly-agent-avatar.tsx",
    "app/frontend/components/dinkly-agent-bar.tsx",
    "app/frontend/components/dinkly-agent-settings.tsx",
    "app/frontend/components/agent-operations-settings.tsx",
    "app/frontend/components/slack-settings.tsx",
    "app/frontend/components/generation-download-actions.tsx",
    "app/frontend/components/image-model-selector.tsx",
    "app/frontend/components/model-power-badge.tsx",
    "app/frontend/tests/generation-progress.test.tsx",
    "app/frontend/tests/dinkly-agent.test.tsx",
    "docs/DINKLY_AGENT.md",
    "docs/DINKLY_AGENT_RUNTIME.md",
    "docs/SLACK_INTEGRATION.md",
    "docs/CLOUD_DEPLOYMENT.md",
    "docs/AGENT_ARCHITECTURE.md",
    "docs/CONTENT_FORMATS.md",
    "docs/CONTENT_FEEDBACK_LEARNING.md",
    "docs/USED_STORYLINES.md",
    "app/backend/tests/test_content_agent.py",
    "app/backend/tests/test_concept_generator_scheduler.py",
    "app/frontend/tests/concept-generator.test.tsx",
    "app-data/concepts.json",
    "app-data/prompts.json",
    "app-data/art_reviews.json",
    "app-data/story_library.json",
    "app-data/settings.json",
    "app-data/content_agent_settings.json",
    "app-data/content_agent_chat.json",
    "app-data/concept_generator_scheduler_state.json",
    "app-data/concept_generator_worker_heartbeat.json",
    "app-data/content_provider_usage.json",
    "data/sprite_characters.json",
    "data/sprite_animations.json",
    "data/sprite_sheets.json",
    "data/sprite_compositions.json",
    "app-data/sprites/frames.json",
    "app-data/sprites/shared_interactions.json",
    "schemas/sprite_character.schema.json",
    "schemas/sprite_frame.schema.json",
    "schemas/sprite_animation.schema.json",
    "schemas/sprite_sheet.schema.json",
    "schemas/sprite_composition.schema.json",
    "docs/SPRITE_STUDIO.md",
    "docs/SPRITE_CHARACTER_RULES.md",
    "docs/SPRITE_ANIMATION_GUIDE.md",
    "docs/SPRITE_EXPORT_GUIDE.md",
    "scripts/sprite_image_worker.py",
    "scripts/demonstrate_sprite_pipeline.py",
    "requirements-sprites.txt",
    "app/backend/models/sprites.py",
    "app/backend/routers/sprites.py",
    "app/backend/routers/sprite_animations.py",
    "app/backend/routers/sprite_exports.py",
    "app/backend/routers/sprite_compositions.py",
    "app/backend/services/sprite_service.py",
    "app/backend/services/sprite_validation_service.py",
    "app/backend/services/sprite_sheet_service.py",
    "app/backend/services/sprite_composition_service.py",
    "app/backend/services/sprite_export_service.py",
    "app/frontend/app/sprite-studio/page.tsx",
    "app/frontend/app/sprite-studio/new/page.tsx",
    "app/frontend/app/sprite-studio/characters/[characterId]/page.tsx",
    "app/frontend/app/sprite-studio/animations/[animationId]/page.tsx",
    "app/frontend/app/sprite-studio/composer/page.tsx",
    "app/frontend/app/sprite-studio/exports/page.tsx",
    "app/frontend/app/motion-studio/page.tsx",
    "app/frontend/components/sprite-studio/sprite-library.tsx",
    "app/frontend/components/sprite-studio/sprite-card.tsx",
    "app/frontend/components/sprite-studio/frame-timeline.tsx",
    "app/frontend/components/sprite-studio/frame-thumbnail.tsx",
    "app/frontend/components/sprite-studio/sprite-preview.tsx",
    "app/frontend/components/sprite-studio/animation-controls.tsx",
    "app/frontend/components/sprite-studio/onion-skin-preview.tsx",
    "app/frontend/components/sprite-studio/frame-dropzone.tsx",
    "app/frontend/components/sprite-studio/sprite-sheet-preview.tsx",
    "app/frontend/components/sprite-studio/character-selector.tsx",
    "app/frontend/components/sprite-studio/animation-state-selector.tsx",
    "app/frontend/components/sprite-studio/anchor-point-editor.tsx",
    "app/frontend/components/sprite-studio/loop-settings.tsx",
    "app/frontend/components/sprite-studio/export-dialog.tsx",
    "app/frontend/components/sprite-studio/frame-inspector.tsx",
    "app/frontend/components/sprite-studio/layer-composer.tsx",
    "app/frontend/components/sprite-studio/validation-panel.tsx",
    "app/frontend/tests/sprite-studio.test.tsx",
    "tests/test_sprite_models.py",
    "tests/test_sprite_validation.py",
    "tests/test_sprite_sheet_generation.py",
    "tests/test_sprite_exports.py",
    "tests/test_sprite_path_safety.py",
    "data/monitored_handles.json",
    "data/competitor_profiles.json",
    "data/competitor_posts.json",
    "data/competitor_snapshots.json",
    "data/competitor_learnings.json",
    "data/competitor_concept_directions.json",
    "data/provider_usage.json",
    "app-data/provider_budget.json",
    "app-data/provider_states.json",
    "app-data/agent_runs.json",
    "app-data/agent_events.json",
    "schemas/monitored_handle.schema.json",
    "schemas/competitor_profile.schema.json",
    "schemas/competitor_post.schema.json",
    "schemas/competitor_snapshot.schema.json",
    "schemas/competitor_learning.schema.json",
    "schemas/competitor_concept_direction.schema.json",
    "schemas/provider_usage.schema.json",
    "app/backend/models/social_intelligence.py",
    "app/backend/providers/social_data.py",
    "app/backend/routers/social_intelligence.py",
    "app/backend/services/agent_runtime_service.py",
    "app/backend/services/budget_service.py",
    "app/backend/services/circuit_breaker_service.py",
    "app/backend/services/creative_classification_service.py",
    "app/backend/services/handle_utils.py",
    "app/backend/services/secrets_service.py",
    "app/backend/services/social_intelligence_service.py",
    "app/backend/services/social_intelligence_scheduler.py",
    "app/backend/tests/test_social_intelligence.py",
    "app/frontend/app/agents/social-intelligence/page.tsx",
    "app/frontend/components/social-provider-settings.tsx",
    "app/frontend/tests/social-intelligence.test.tsx",
    "docs/SOCIAL_INTELLIGENCE_AGENT.md",
    "docs/SOCIAL_DATA_PROVIDERS.md",
    "docs/APIFY_SETUP.md",
    "docs/PROVIDER_BUDGET_GUARDRAILS.md",
    "docs/LOCAL_SECRET_MANAGEMENT.md",
    "docs/PUBLIC_DATA_LIMITATIONS.md",
    "docs/COMPETITOR_ORIGINALITY_RULES.md",
    "docs/AGENT_RUNTIME.md",
]

JSON_DATA_FILES = [
    "data/social_posts.json",
    "data/social_learnings.json",
    "data/storyline_scores.json",
    "data/approved_prompts.json",
    "data/story_library_v2.json",
    "data/sprite_characters.json",
    "data/sprite_animations.json",
    "data/sprite_sheets.json",
    "data/sprite_compositions.json",
    "app-data/sprites/frames.json",
    "app-data/sprites/shared_interactions.json",
    "data/monitored_handles.json",
    "data/competitor_profiles.json",
    "data/competitor_posts.json",
    "data/competitor_snapshots.json",
    "data/competitor_learnings.json",
    "data/competitor_concept_directions.json",
    "data/provider_usage.json",
    "app-data/agent_runs.json",
    "app-data/agent_events.json",
    "app-data/content_agent_chat.json",
]

SCHEMA_FILES = [
    "schemas/social_post.schema.json",
    "schemas/social_learning.schema.json",
    "schemas/storyline_score.schema.json",
    "schemas/prompt_record.schema.json",
    "schemas/story_record.schema.json",
    "schemas/sprite_character.schema.json",
    "schemas/sprite_frame.schema.json",
    "schemas/sprite_animation.schema.json",
    "schemas/sprite_sheet.schema.json",
    "schemas/sprite_composition.schema.json",
    "schemas/monitored_handle.schema.json",
    "schemas/competitor_profile.schema.json",
    "schemas/competitor_post.schema.json",
    "schemas/competitor_snapshot.schema.json",
    "schemas/competitor_learning.schema.json",
    "schemas/competitor_concept_direction.schema.json",
    "schemas/provider_usage.schema.json",
]

MARKDOWN_FILES = [path for path in REQUIRED_FILES if path.endswith(".md")]
SCRIPT_FILES = [path for path in REQUIRED_FILES if path.startswith("scripts/") and path.endswith(".py")]
REQUIRED_DIRECTORIES = [
    "app-data/sprites/references",
    "app-data/sprites/characters/dinko",
    "app-data/sprites/characters/dinka",
    "app-data/sprites/shared",
    "app-data/sprites/props",
    "app-data/sprites/effects",
    "app-data/sprites/thumbnails",
    "app-data/sprites/previews",
    "app-data/sprites/exports",
]


def validate_required_files(root: Path) -> list[str]:
    errors = [f"Missing required file: {relative}" for relative in REQUIRED_FILES if not (root / relative).is_file()]
    errors.extend(
        f"Missing required directory: {relative}"
        for relative in REQUIRED_DIRECTORIES
        if not (root / relative).is_dir()
    )
    return errors


def validate_json_data(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in JSON_DATA_FILES:
        path = root / relative
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {relative}: {exc}")
            continue
        if not isinstance(payload, list):
            errors.append(f"{relative} must contain a JSON array")
    return errors


def validate_schemas(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in SCHEMA_FILES:
        path = root / relative
        if not path.exists():
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid schema JSON in {relative}: {exc}")
            continue
        for key in ("$schema", "$id", "title", "type", "properties"):
            if key not in schema:
                errors.append(f"{relative} is missing schema key {key}")
        if schema.get("type") != "object":
            errors.append(f"{relative} must describe an object")
        if not isinstance(schema.get("properties"), dict) or not schema.get("properties"):
            errors.append(f"{relative} must define non-empty properties")
        required = schema.get("required")
        if not isinstance(required, list) or not required:
            errors.append(f"{relative} must define required fields")
        elif isinstance(schema.get("properties"), dict):
            unknown_required = sorted(set(required) - set(schema["properties"]))
            if unknown_required:
                errors.append(f"{relative} requires undefined properties: {', '.join(unknown_required)}")
    return errors


def validate_markdown(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in MARKDOWN_FILES:
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if len(text) < 80:
            errors.append(f"Markdown file is empty or placeholder-only: {relative}")
        if not text.startswith("#"):
            errors.append(f"Markdown file must begin with a heading: {relative}")
    return errors


def validate_python(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in SCRIPT_FILES:
        path = root / relative
        if not path.exists():
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            errors.append(f"Syntax error in {relative}: {exc}")
    return errors


def validate_reference(root: Path) -> list[str]:
    path = root / "references" / "dinkly_young.png"
    if not path.is_file():
        return ["Missing locked character reference: references/dinkly_young.png"]
    data = path.read_bytes()
    if len(data) < 100 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ["references/dinkly_young.png is not a valid non-empty PNG"]
    return []


def validate_agent_portraits(root: Path) -> list[str]:
    """Fail clearly when a canonical production portrait is missing or corrupt."""
    errors: list[str] = []
    agent_ids = (
        "creative-director",
        "concept-generator",
        "prompt-agent",
        "social-intelligence",
        "art-review",
        "brand-integration",
        "motion-director",
    )
    for agent_id in agent_ids:
        relative = f"app/frontend/public/agents/{agent_id}.png"
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing canonical agent portrait: {relative}")
            continue
        data = path.read_bytes()
        if len(data) < 100 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append(f"Canonical agent portrait is not a valid non-empty PNG: {relative}")
    return errors


def run_test_suite(root: Path) -> list[str]:
    project_python = root / ".venv" / "bin" / "python"
    command = [str(project_python if project_python.is_file() else Path(sys.executable)), "-m", "pytest", "-q"]
    process = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode == 0:
        return []
    output = "\n".join(part for part in (process.stdout, process.stderr) if part).strip()
    return [f"Test suite failed:\n{output}"]


def validate_project(root: Path = ROOT, run_tests: bool = True) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_required_files(root))
    errors.extend(validate_json_data(root))
    errors.extend(validate_schemas(root))
    errors.extend(validate_markdown(root))
    errors.extend(validate_python(root))
    errors.extend(validate_reference(root))
    errors.extend(validate_agent_portraits(root))
    if run_tests and not errors:
        errors.extend(run_test_suite(root))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--skip-tests", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_project(args.root.resolve(), run_tests=not args.skip_tests)
    if errors:
        print("DINKLY Generation Engine validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("DINKLY Generation Engine validation passed.")
    print(f"Validated {len(REQUIRED_FILES)} required files, JSON data, schemas, Markdown, Python, references, and tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
