from __future__ import annotations

import unittest
from datetime import UTC, datetime

from scripts.generate_prompt_brief import generate_prompt
from scripts.score_storyline import EVALUATION_LABEL, score_storyline


def sample_storyline() -> dict:
    return {
        "storyline_id": "rainy-walk-001",
        "storyline": "rainy walk",
        "title_pair": {"left": "RAIN", "right": "RAIN WITH YOU"},
        "format": "x-with-you",
        "left_scene": "Dinko stands under one umbrella on a curved path, neutral and grounded.",
        "right_scene": "Dinka and Dinko stand close under the same umbrella on the same path.",
        "emotional_insight": "Shared shelter turns ordinary rain into comfort and togetherness.",
        "why_someone_would_share": "It resembles a familiar small act of care between partners.",
        "brand_placement_opportunities": ["umbrella", "travel drink"],
        "execution_risks": ["long walking legs", "oversized umbrella"],
        "recommended_background_color": "powder blue",
        "recommended_accent_color": "muted coral",
        "recommended_camera_angle": "profile medium-wide",
        "props": ["umbrella", "path", "tree"],
        "character_count": 2,
        "novel_angle": "The shared umbrella tilts toward Dinko as a visible act of care.",
    }


class StorylineScoringTests(unittest.TestCase):
    def test_directional_score_has_complete_bounded_output(self) -> None:
        learning = {
            "learning_id": "learn-rain-care",
            "pattern": "rainy walks with a visible act of care",
            "recommended_use": "Test shared shelter and physical closeness",
        }
        record = score_storyline(
            sample_storyline(),
            [learning],
            now=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(record["evaluation_label"], EVALUATION_LABEL)
        self.assertIn("learn-rain-care", record["relevant_social_learnings"])
        self.assertIn("weakest_criterion", record)
        self.assertTrue(record["improvement_recommendation"])
        self.assertGreaterEqual(record["directional_total"], 1)
        self.assertLessEqual(record["directional_total"], 10)
        for value in record["scores"].values():
            self.assertGreaterEqual(value, 1)
            self.assertLessEqual(value, 10)

    def test_complex_props_increase_risk_and_reduce_simplicity(self) -> None:
        simple = sample_storyline()
        complex_story = sample_storyline()
        complex_story["props"] = ["table", "chairs", "phone", "cart", "mugs", "counter", "shelf"]
        complex_story["left_scene"] += " A phone, cart, table, and chairs crowd the scene."
        simple_score = score_storyline(simple)
        complex_score = score_storyline(complex_story)
        self.assertGreater(
            complex_score["scores"]["risk_of_character_distortion"],
            simple_score["scores"]["risk_of_character_distortion"],
        )
        self.assertLess(
            complex_score["scores"]["visual_simplicity"],
            simple_score["scores"]["visual_simplicity"],
        )

    def test_prompt_generation_selects_x_with_you_and_resolves_fields(self) -> None:
        template, prompt = generate_prompt(sample_storyline())
        self.assertEqual(template.name, "XWithYou.md")
        self.assertIn("RAIN WITH YOU", prompt)
        self.assertIn("exactly two hair tufts", prompt)
        self.assertNotIn("{{", prompt)


if __name__ == "__main__":
    unittest.main()
