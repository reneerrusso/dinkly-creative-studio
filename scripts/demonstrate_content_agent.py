#!/usr/bin/env python3
"""Run the Concept Generator fixture demonstration in an isolated repository.

The legacy filename is retained so existing team commands keep working.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.config import Settings  # noqa: E402
from app.backend.services.concept_generator_service import ConceptGeneratorService  # noqa: E402
from app.backend.services.content_agent import DevelopmentFixtureProvider  # noqa: E402
from app.backend.services.repository_service import RepositoryService  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dinkly-content-demo-") as directory:
        root = Path(directory).resolve()
        for relative in ("data", "app-data", "app-data/backups", "app-data/reports", "app-data/uploads", "app-data/sprites"):
            (root / relative).mkdir(parents=True, exist_ok=True)
        for name in ("content_batches", "content_concepts", "content_feedback", "content_agent_preferences", "used_storylines"):
            (root / "data" / f"{name}.json").write_text("[]\n", encoding="utf-8")
        for name in ("social_posts", "social_learnings", "story_library_v2", "competitor_learnings"):
            source = ROOT / "data" / f"{name}.json"
            shutil.copy2(source, root / "data" / source.name)
        for name in ("concepts", "prompts", "agent_runs", "agent_events", "content_agent_chat"):
            (root / "app-data" / f"{name}.json").write_text("[]\n", encoding="utf-8")
        (root / "app-data" / "content_agent_settings.json").write_text(json.dumps({"generate_daily_automatically": False, "run_time": "08:00", "generate_on_start": False, "last_scheduler_check": None}), encoding="utf-8")
        repository = RepositoryService(Settings(root, "http://127.0.0.1:3000", 5 * 1024 * 1024))
        service = ConceptGeneratorService(repository, DevelopmentFixtureProvider())
        started = service.start_batch()
        service.execute_batch(started["run"]["id"], started["batch"]["id"])
        concepts = service.list_concepts()
        with_you = next(item for item in concepts if item["format"] == "with_you")
        passed = next(item for item in concepts if item["format"] == "before_after")
        five = next(item for item in concepts if item["format"] == "five_story")
        replacement_target = [item for item in concepts if item["format"] == "with_you"][1]
        service.approve(with_you["id"])
        service.pass_concept(passed["id"], "Too repetitive")
        chat = service.chat("Stop giving me coffee ideas.")
        replacement = service.replace(replacement_target["id"])
        single = service.prompt_handoff(with_you["id"])
        service.approve(five["id"])
        story = service.prompt_handoff(five["id"])
        service.mark_used(with_you["id"])
        state = service.state()
        output = {
            "fixture_warning": "Development fixtures only; not actual agent recommendations.",
            "finalists": {name: sum(item["format"] == name for item in concepts) for name in ("with_you", "before_after", "five_story")},
            "events": [event["message"] for event in service.runtime.events(started["run"]["id"])],
            "approved": with_you["id"],
            "passed": {"id": passed["id"], "reason": "Too repetitive"},
            "chat_reply": chat["reply"]["message"],
            "preference": chat["preference"],
            "replacement": {"old": replacement_target["id"], "new": replacement["id"], "slot": replacement["slot"]},
            "single_prompt_handoff": {"prompt_ids": single["prompt_ids"], "href": single["href"]},
            "five_comic_prompt_count": len(story["prompts"]),
            "production_queue_count": len(state["production_queue"]),
            "used_storyline_count": len(state["used_storylines"]),
            "used_absent_from_today": all(item["id"] != with_you["id"] for item in state["today_concepts"]),
        }
        print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
