#!/usr/bin/env python3
"""Static safety and completeness checks for versioned SQL migrations."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TABLES = {
    "agent_memories",
    "creative_preferences",
    "used_storylines",
    "prompt_learnings",
    "qa_learnings",
    "generation_learnings",
    "failure_patterns",
    "concept_feedback",
    "conversation_threads",
    "conversation_messages",
    "agent_tasks",
    "agent_events",
    "generation_runs",
    "generation_candidates",
    "approvals",
    "brain_update_proposals",
    "learning_checkpoints",
    "assets",
}
PROHIBITED = ("drop table", "truncate table", "delete from")


def validate() -> list[str]:
    errors: list[str] = []
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    if not migrations:
        return ["No migrations found"]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in migrations).lower()
    for phrase in PROHIBITED:
        if phrase in combined:
            errors.append(f"Destructive statement is not allowed: {phrase}")
    tables = set(re.findall(r"create\s+table\s+if\s+not\s+exists\s+([a-z0-9_]+)", combined))
    for table in sorted(REQUIRED_TABLES - tables):
        errors.append(f"Missing required table: {table}")
    for path in migrations:
        version = path.stem
        if version not in path.read_text(encoding="utf-8"):
            errors.append(f"Migration does not record its version: {path.name}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(errors))
        return 1
    print("Migrations are structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
