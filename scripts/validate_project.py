#!/usr/bin/env python3
"""Validate the DINKLY Creative Studio structure, data, schemas, source, and tests."""

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
    "scripts/ingest_social_post.py",
    "scripts/analyze_social_posts.py",
    "scripts/score_storyline.py",
    "scripts/generate_prompt_brief.py",
    "scripts/validate_project.py",
    "schemas/social_post.schema.json",
    "schemas/social_learning.schema.json",
    "schemas/storyline_score.schema.json",
    "schemas/prompt_record.schema.json",
    "tests/test_social_learning.py",
    "tests/test_storyline_scoring.py",
    "tests/test_character_rules.py",
    "tests/test_project_structure.py",
]

JSON_DATA_FILES = [
    "data/social_posts.json",
    "data/social_learnings.json",
    "data/storyline_scores.json",
    "data/approved_prompts.json",
]

SCHEMA_FILES = [
    "schemas/social_post.schema.json",
    "schemas/social_learning.schema.json",
    "schemas/storyline_score.schema.json",
    "schemas/prompt_record.schema.json",
]

MARKDOWN_FILES = [path for path in REQUIRED_FILES if path.endswith(".md")]
SCRIPT_FILES = [path for path in REQUIRED_FILES if path.startswith("scripts/") and path.endswith(".py")]


def validate_required_files(root: Path) -> list[str]:
    return [f"Missing required file: {relative}" for relative in REQUIRED_FILES if not (root / relative).is_file()]


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


def run_test_suite(root: Path) -> list[str]:
    process = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
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
        print("DINKLY Creative Studio validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("DINKLY Creative Studio validation passed.")
    print(f"Validated {len(REQUIRED_FILES)} required files, JSON data, schemas, Markdown, Python, references, and tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
