from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.models.social_posts import SocialPostInput
from app.backend.services.repository_service import RepositoryError, RepositoryService
from scripts.analyze_social_posts import (
    GENERATED_END,
    GENERATED_START,
    build_generated_report,
    calculate_ratios,
    top_posts,
)
from scripts.ingest_social_post import SocialPost


class SocialLearningService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def posts(self) -> list[dict[str, Any]]:
        records = self.repository.read_json("data/social_posts.json", [])
        return [self.enrich(record) for record in records]

    def get_post(self, post_id: str) -> dict[str, Any]:
        for post in self.posts():
            if post.get("id") == post_id:
                post["linked_learnings"] = [
                    item for item in self.learnings() if post_id in item.get("evidence_post_ids", [])
                ]
                return post
        raise RepositoryError("Social post not found")

    def create_post(self, payload: SocialPostInput) -> tuple[dict[str, Any], str | None]:
        records = self.repository.read_json("data/social_posts.json", [])
        candidate = payload.model_dump(mode="json", exclude={"uploaded_asset_hash"})
        candidate["id"] = payload.id or f"post-{uuid.uuid4().hex[:12]}"
        if candidate.get("post_date"):
            candidate["post_date"] = str(candidate["post_date"])
        post = SocialPost.from_mapping(candidate).to_dict()
        self._reject_duplicate(records, post, payload.uploaded_asset_hash)
        records.append(post)
        backup = self.repository.write_json(
            "data/social_posts.json",
            records,
            schema_relative="schemas/social_post.schema.json",
            validate_each=True,
        )
        return self.enrich(post), backup

    def learnings(self) -> list[dict[str, Any]]:
        return self.repository.read_json("data/social_learnings.json", [])

    def analyze(self) -> dict[str, Any]:
        records = self.repository.read_json("data/social_posts.json", [])
        generated = build_generated_report(records)
        current = self.repository.path("SOCIAL_LEARNING.md").read_text(encoding="utf-8")
        if GENERATED_START not in current or GENERATED_END not in current:
            raise RepositoryError("SOCIAL_LEARNING.md is missing generated report markers")
        prefix, remainder = current.split(GENERATED_START, 1)
        _, suffix = remainder.split(GENERATED_END, 1)
        updated = f"{prefix}{GENERATED_START}\n{generated}\n{GENERATED_END}{suffix}"
        result = self.repository.write_markdown("social-learning", updated)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        report_relative = f"app-data/reports/social-learning-{timestamp}.md"
        self.repository.atomic_write_bytes(self.repository.path(report_relative), generated.encode(), create_backup=False)
        return {
            "post_count": len(records),
            "generated": generated,
            "report_path": report_relative,
            "backup": result.get("backup"),
        }

    def reports(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.repository.settings.reports_dir.glob("*.md"), reverse=True):
            records.append(
                {
                    "name": path.name,
                    "path": self.repository.relative(path),
                    "created_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                    "content": path.read_text(encoding="utf-8"),
                }
            )
        return records

    def patterns(self) -> dict[str, Any]:
        posts = self.posts()
        return {
            "sample_size": len(posts),
            "top_by_views": top_posts(posts, "views"),
            "top_by_shares": top_posts(posts, "shares"),
            "top_by_share_rate": top_posts(posts, "share_rate"),
            "themes": self._counts(posts, "emotional_theme"),
            "formats": self._counts(posts, "format"),
            "backgrounds": self._counts(posts, "background_color"),
            "camera_angles": self._counts(posts, "camera_angle"),
            "prop_counts": self._prop_counts(posts),
            "causation_warning": "Associations are descriptive and do not establish causation.",
        }

    def enrich(self, record: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(record)
        enriched["rates"] = calculate_ratios(record)
        metrics = ["views", "shares", "likes", "comments", "saves"]
        known = sum(record.get(metric) is not None for metric in metrics)
        enriched["metric_completeness"] = {"known": known, "total": len(metrics), "percent": known / len(metrics)}
        return enriched

    def _reject_duplicate(
        self, records: list[dict[str, Any]], candidate: dict[str, Any], supplied_hash: str | None
    ) -> None:
        for record in records:
            if record.get("id") == candidate["id"]:
                raise RepositoryError("A post with this ID already exists")
            comparable = (
                candidate.get("platform"),
                candidate.get("post_date"),
                candidate.get("title"),
            )
            existing = (record.get("platform"), record.get("post_date"), record.get("title"))
            if all(comparable) and comparable == existing:
                raise RepositoryError("Likely duplicate: platform, date, and title already exist")
            if supplied_hash and record.get("uploaded_asset_reference"):
                path = self.repository.path(record["uploaded_asset_reference"])
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == supplied_hash:
                    raise RepositoryError("Likely duplicate: this uploaded image already belongs to a post")

    @staticmethod
    def _counts(posts: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for post in posts:
            value = post.get(field)
            if value:
                counts[str(value)] = counts.get(str(value), 0) + 1
        return [{"value": value, "count": count} for value, count in sorted(counts.items(), key=lambda item: -item[1])]

    @staticmethod
    def _prop_counts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for post in posts:
            props = post.get("props")
            if isinstance(props, list):
                label = f"{len(props)} props"
                counts[label] = counts.get(label, 0) + 1
        return [{"value": value, "count": count} for value, count in sorted(counts.items(), key=lambda item: -item[1])]
