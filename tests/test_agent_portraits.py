from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_project import ROOT, validate_agent_portraits

CANONICAL_IDS = (
    "creative-director",
    "concept-generator",
    "prompt-agent",
    "social-intelligence",
    "art-review",
    "brand-integration",
    "motion-director",
)


class AgentPortraitTests(unittest.TestCase):
    def test_all_seven_canonical_portraits_are_valid_pngs(self) -> None:
        self.assertEqual(validate_agent_portraits(ROOT), [])
        for agent_id in CANONICAL_IDS:
            path = ROOT / "app" / "frontend" / "public" / "agents" / f"{agent_id}.png"
            self.assertTrue(path.is_file(), path)
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_missing_portraits_report_a_clear_validation_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            errors = validate_agent_portraits(Path(temporary))
        self.assertEqual(len(errors), 7)
        self.assertIn("Missing canonical agent portrait", errors[0])

    def test_registry_has_no_visible_duplicate_content_agent(self) -> None:
        registry = (ROOT / "app/frontend/lib/agents.ts").read_text(encoding="utf-8")
        canonical_block = registry.split("export const canonicalAgentIds =", 1)[1].split("] as const", 1)[0]
        self.assertNotIn('"content-agent"', canonical_block)
        self.assertIn('"content-agent": "concept-generator"', registry)

    def test_required_ui_surfaces_use_agent_avatar(self) -> None:
        expected = {
            "app/frontend/components/agent-room.tsx": "<AgentAvatar agentId={agent.id}",
            "app/frontend/app/agents/concept-generator/page.tsx": '<AgentAvatar agentId="concept-generator"',
            "app/frontend/app/agents/social-intelligence/page.tsx": '<AgentAvatar agentId={runAgent}',
        }
        for relative, marker in expected.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(marker, source, relative)

    def test_production_public_folder_contains_no_old_agent_art(self) -> None:
        obsolete = {
            "art-reviewer.png",
            "brand-partnerships.png",
            "content-agent.png",
            "prompt-engineer.png",
            "social-learning.png",
        }
        public_names = {path.name for path in (ROOT / "app/frontend/public/agents").glob("*")}
        self.assertTrue(obsolete.isdisjoint(public_names))

    def test_generation_engine_uses_one_visible_agent_persona(self) -> None:
        layout = (ROOT / "app/frontend/app/layout.tsx").read_text(encoding="utf-8")
        agent_bar = (ROOT / "app/frontend/components/dinkly-agent-bar.tsx").read_text(encoding="utf-8")
        generate = (ROOT / "app/frontend/app/generate/page.tsx").read_text(encoding="utf-8")
        progress = (ROOT / "app/frontend/components/generation-progress.tsx").read_text(encoding="utf-8")
        sidebar = (ROOT / "app/frontend/components/app-sidebar.tsx").read_text(encoding="utf-8")
        self.assertIn("<DinklyAgentBar", layout)
        self.assertIn("<DinklyAgentAvatar", agent_bar)
        self.assertNotIn("AgentAvatar", generate)
        self.assertNotIn("AgentAvatar", progress)
        self.assertNotIn("AgentAvatar", sidebar)

    def test_focused_navigation_and_brain_links_are_preserved(self) -> None:
        sidebar = (ROOT / "app/frontend/components/app-sidebar.tsx").read_text(encoding="utf-8")
        agent_registry = (ROOT / "app/frontend/lib/agents.ts").read_text(encoding="utf-8")
        for label in ("DINKLY Agent", "Approvals", "History"):
            self.assertIn(f'label: "{label}"', sidebar)
        for label in (
            "Story Library",
            "Used Storylines",
            "Examples",
            "Failure Library",
            "Knowledge Base",
        ):
            self.assertIn(label, agent_registry)


if __name__ == "__main__":
    unittest.main()
