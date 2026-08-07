#!/usr/bin/env python3
"""Generate an evidence-based Markdown report from DINKLY social-post records."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSTS = ROOT / "data" / "social_posts.json"
DEFAULT_REPORT = ROOT / "SOCIAL_LEARNING.md"
GENERATED_START = "<!-- GENERATED:START -->"
GENERATED_END = "<!-- GENERATED:END -->"
RATE_FIELDS = {
    "share_rate": "shares",
    "like_rate": "likes",
    "comment_rate": "comments",
    "save_rate": "saves",
    "follow_conversion_rate": "follows_generated",
}


def safe_rate(numerator: int | float | None, views: int | float | None) -> float | None:
    if numerator is None or views is None or views == 0:
        return None
    if isinstance(numerator, bool) or isinstance(views, bool) or numerator < 0 or views < 0:
        return None
    return numerator / views


def calculate_ratios(post: dict[str, Any]) -> dict[str, float | None]:
    return {name: safe_rate(post.get(metric), post.get("views")) for name, metric in RATE_FIELDS.items()}


def load_posts(path: Path = DEFAULT_POSTS) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def top_posts(posts: Iterable[dict[str, Any]], key: str, limit: int = 5) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for post in posts:
        value = calculate_ratios(post).get(key) if key in RATE_FIELDS else post.get(key)
        if value is None:
            continue
        enriched = dict(post)
        enriched["_rank_value"] = value
        eligible.append(enriched)
    return sorted(eligible, key=lambda item: item["_rank_value"], reverse=True)[:limit]


def _format_value(value: float | int, is_rate: bool) -> str:
    return f"{value:.2%}" if is_rate else f"{int(value):,}"


def _ranking_table(posts: list[dict[str, Any]], key: str) -> str:
    if not posts:
        return "No valid records for this metric."
    rows = ["| Rank | Post | Platform | Value |", "|---:|---|---|---:|"]
    for index, post in enumerate(posts, 1):
        rows.append(
            f"| {index} | {post.get('title') or post.get('id')} | "
            f"{post.get('platform') or 'unknown'} | {_format_value(post['_rank_value'], key in RATE_FIELDS)} |"
        )
    return "\n".join(rows)


def _coverage_table(posts: list[dict[str, Any]]) -> str:
    metrics = ["views", "shares", "likes", "comments", "saves", "follows_generated", "watch_time", "completion_rate"]
    rows = ["| Metric | Present | Missing |", "|---|---:|---:|"]
    for metric in metrics:
        present = sum(post.get(metric) is not None for post in posts)
        rows.append(f"| {metric} | {present} | {len(posts) - present} |")
    return "\n".join(rows)


def _storyline_summary(posts: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        storyline = post.get("storyline")
        if storyline:
            grouped[str(storyline)].append(post)
    if not grouped:
        return "No storyline labels are available yet."

    rows = ["| Storyline | Posts | Mean views when known | Mean share rate when valid |", "|---|---:|---:|---:|"]
    for storyline, records in sorted(grouped.items()):
        known_views = [record["views"] for record in records if record.get("views") is not None]
        rates = [rate for record in records if (rate := safe_rate(record.get("shares"), record.get("views"))) is not None]
        views_text = f"{mean(known_views):,.0f}" if known_views else "unknown"
        rate_text = f"{mean(rates):.2%}" if rates else "unknown"
        rows.append(f"| {storyline} | {len(records)} | {views_text} | {rate_text} |")
    return "\n".join(rows)


def build_generated_report(posts: list[dict[str, Any]], limit: int = 5) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    if not posts:
        return (
            f"Generated {generated_at}.\n\n"
            "No social posts have been ingested. Missing data is not treated as zero."
        )

    sections = [
        f"Generated {generated_at} from {len(posts)} post record(s).",
        "## Measured-data coverage\n\n" + _coverage_table(posts),
    ]
    for label, key in (
        ("Top posts by views", "views"),
        ("Top posts by shares", "shares"),
        ("Top posts by share rate", "share_rate"),
        ("Top posts by saves", "saves"),
        ("Top posts by save rate", "save_rate"),
    ):
        sections.append(f"## {label}\n\n{_ranking_table(top_posts(posts, key, limit), key)}")

    sections.append("## Storyline summary\n\n" + _storyline_summary(posts))
    sections.append(
        "## Automated-analysis boundary\n\n"
        "The tables above are measured facts or valid calculations. They do not explain why a post performed. "
        "A human or Social Learning agent must inspect the assets before recording observed traits or hypotheses."
    )
    return "\n\n".join(sections)


def update_report(report_path: Path, generated: str) -> None:
    current = report_path.read_text(encoding="utf-8")
    if GENERATED_START not in current or GENERATED_END not in current:
        raise ValueError(f"{report_path} is missing generated-section markers")
    prefix, remainder = current.split(GENERATED_START, 1)
    _, suffix = remainder.split(GENERATED_END, 1)
    report_path.write_text(
        f"{prefix}{GENERATED_START}\n{generated}\n{GENERATED_END}{suffix}", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--posts-file", type=Path, default=DEFAULT_POSTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--print", action="store_true", dest="print_report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        print("error: --limit must be at least 1")
        return 2
    try:
        posts = load_posts(args.posts_file)
        generated = build_generated_report(posts, args.limit)
        update_report(args.output, generated)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    if args.print_report:
        print(generated)
    print(f"Analyzed {len(posts)} post(s) and updated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
