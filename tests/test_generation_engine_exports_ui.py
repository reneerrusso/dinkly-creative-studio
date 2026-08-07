from __future__ import annotations

import unittest

from scripts.validate_project import ROOT


class GenerationEngineExportUiTests(unittest.TestCase):
    def test_progress_component_exposes_all_real_stages_and_accessibility(self) -> None:
        source = (ROOT / "app/frontend/components/generation-progress.tsx").read_text(encoding="utf-8")
        for stage in ("story", "compile", "references", "generate", "qa", "repair", "human_review"):
            self.assertIn(f'id: "{stage}"', source)
        self.assertIn('aria-label="Generation progress"', source)
        self.assertIn('aria-live="polite"', source)
        self.assertIn("event.data.status", source)

    def test_generate_page_replays_persisted_events_and_candidate_subprogress(self) -> None:
        page = (ROOT / "app/frontend/app/generate/page.tsx").read_text(encoding="utf-8")
        progress = (ROOT / "app/frontend/components/generation-progress.tsx").read_text(encoding="utf-8")
        self.assertIn("dinkly-active-generation-run", page)
        self.assertIn("EventSource", page)
        self.assertIn('"progress"', page)
        self.assertIn("CandidateProgress", progress)
        self.assertIn("QaProgress", progress)
        self.assertIn("RepairProgress", progress)

    def test_story_builder_keeps_library_visible_retries_and_builds_selected_story(self) -> None:
        page = (ROOT / "app/frontend/app/generate/page.tsx").read_text(encoding="utf-8")
        for marker in (
            'htmlFor="generation-story-library"',
            'id="generation-story-library"',
            '"/api/story-library"',
            "timeoutMs: 8_000",
            "storyLoadAttempt < 3",
            "Retry Story Library",
            "void buildStory(nextId)",
            "story_id: selectedStoryId",
            "timeoutMs: 10_000",
            "briefRef.current?.scrollIntoView",
        ):
            self.assertIn(marker, page)
        self.assertNotIn('catch(() => setStories([]))', page)

    def test_model_badges_are_registry_driven_and_accessible(self) -> None:
        badge = (ROOT / "app/frontend/components/model-power-badge.tsx").read_text(encoding="utf-8")
        selector = (ROOT / "app/frontend/components/image-model-selector.tsx").read_text(encoding="utf-8")
        history = (ROOT / "app/frontend/app/history/page.tsx").read_text(encoding="utf-8")
        self.assertIn("Power level:", badge)
        self.assertIn("model.power_level", badge)
        self.assertIn("models.map", selector)
        self.assertNotIn("gemini-3", selector)
        self.assertIn("Employee work log", history)
        self.assertNotIn("charAt", history)

    def test_approved_download_actions_have_accessible_formats_and_reports(self) -> None:
        source = (ROOT / "app/frontend/components/generation-download-actions.tsx").read_text(encoding="utf-8")
        for marker in (
            "Download approved comic as PNG",
            "Download approved comic as JPG",
            "Download all generated candidates as ZIP",
            "Download the QA report as JSON",
            "Download the generation summary as JSON",
            "Download all five-comic story assets as ZIP",
        ):
            self.assertIn(marker, source)

    def test_download_routes_are_present(self) -> None:
        source = (ROOT / "app/backend/routers/generation_engine.py").read_text(encoding="utf-8")
        for endpoint in ("final", "candidates", "qa", "summary", "all"):
            self.assertIn(f'/download/{endpoint}"', source)


if __name__ == "__main__":
    unittest.main()
