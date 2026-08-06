from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CharacterRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.character_bible = (ROOT / "CHARACTER_BIBLE.md").read_text(encoding="utf-8").lower()
        cls.qa = (ROOT / "QA_CHECKLIST.md").read_text(encoding="utf-8").lower()
        cls.x_template = (ROOT / "PROMPT_TEMPLATES" / "XWithYou.md").read_text(encoding="utf-8").lower()
        cls.style = (ROOT / "STYLE_GUIDE.md").read_text(encoding="utf-8").lower()

    def test_two_hair_tuft_rule_is_explicit(self) -> None:
        self.assertIn("exactly two hair tufts", self.character_bible)
        self.assertIn("exactly two hair tufts", self.qa)

    def test_no_visible_legs_rule_is_explicit(self) -> None:
        self.assertIn("no visible legs", self.character_bible)
        self.assertIn("no visible legs", self.qa)

    def test_same_size_rule_is_explicit(self) -> None:
        self.assertIn("same body size", self.character_bible)
        self.assertIn("same body size", self.qa)

    def test_shared_background_rule_is_explicit(self) -> None:
        self.assertIn("one continuous", self.style)
        self.assertIn("one uninterrupted", self.x_template)


if __name__ == "__main__":
    unittest.main()
