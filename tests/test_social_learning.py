from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_social_posts import calculate_ratios, safe_rate, top_posts
from scripts.ingest_social_post import SocialPost, ValidationError, append_post


class SocialLearningTests(unittest.TestCase):
    def test_ratio_calculations(self) -> None:
        post = {
            "views": 1000,
            "shares": 100,
            "likes": 250,
            "comments": 25,
            "saves": 50,
            "follows_generated": 10,
        }
        ratios = calculate_ratios(post)
        self.assertAlmostEqual(ratios["share_rate"], 0.1)
        self.assertAlmostEqual(ratios["like_rate"], 0.25)
        self.assertAlmostEqual(ratios["comment_rate"], 0.025)
        self.assertAlmostEqual(ratios["save_rate"], 0.05)
        self.assertAlmostEqual(ratios["follow_conversion_rate"], 0.01)

    def test_missing_or_zero_views_do_not_create_rates(self) -> None:
        self.assertIsNone(safe_rate(None, 100))
        self.assertIsNone(safe_rate(10, None))
        self.assertIsNone(safe_rate(10, 0))
        self.assertIsNone(safe_rate(-1, 100))

    def test_top_posts_ignores_missing_metrics(self) -> None:
        posts = [
            {"id": "a", "title": "A", "views": None, "shares": 10},
            {"id": "b", "title": "B", "views": 100, "shares": 20},
            {"id": "c", "title": "C", "views": 1000, "shares": 50},
        ]
        ranked = top_posts(posts, "share_rate")
        self.assertEqual([post["id"] for post in ranked], ["b", "c"])

    def test_duplicate_post_prevention_and_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "social_posts.json"
            data_path.write_text("[]\n", encoding="utf-8")
            post = SocialPost.from_mapping(
                {
                    "id": "post-one",
                    "title": "Coffee With You",
                    "platform": "instagram",
                    "post_date": "2026-08-01",
                    "uploaded_asset_reference": "uploads/coffee.png",
                }
            )
            append_post(post, data_path)
            with self.assertRaises(ValidationError):
                append_post(post, data_path)
            records = json.loads(data_path.read_text(encoding="utf-8"))
            self.assertEqual(len(records), 1)
            self.assertIsNone(records[0]["views"])
            self.assertIn("notes", records[0])

    def test_duplicate_fingerprint_rejected_even_with_new_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "social_posts.json"
            data_path.write_text("[]\n", encoding="utf-8")
            base = {
                "title": "Rain With You",
                "platform": "instagram",
                "post_date": "2026-08-02",
                "uploaded_asset_reference": "uploads/rain.png",
            }
            append_post(SocialPost.from_mapping({"id": "one", **base}), data_path)
            with self.assertRaises(ValidationError):
                append_post(SocialPost.from_mapping({"id": "two", **base}), data_path)


if __name__ == "__main__":
    unittest.main()
