#!/usr/bin/env python3
"""Validate and safely append DINKLY social-post records."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT / "data" / "social_posts.json"
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "social_post.schema.json"


class ValidationError(ValueError):
    """Raised when an input record violates the social-post contract."""


@dataclass(slots=True)
class SocialPost:
    id: str
    title: str
    platform: str | None = None
    post_date: str | None = None
    views: int | None = None
    shares: int | None = None
    likes: int | None = None
    comments: int | None = None
    saves: int | None = None
    follows_generated: int | None = None
    watch_time: float | None = None
    completion_rate: float | None = None
    format: str | None = None
    storyline: str | None = None
    left_panel_summary: str | None = None
    right_panel_summary: str | None = None
    caption: str | None = None
    text_on_image: list[str] | None = None
    background_color: str | None = None
    accent_color: str | None = None
    camera_angle: str | None = None
    character_count: int | None = None
    props: list[str] | None = None
    emotional_theme: str | None = None
    brand_integration: str | None = None
    uploaded_asset_reference: str | None = None
    notes: str | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "SocialPost":
        allowed = set(cls.__dataclass_fields__)
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValidationError(f"Unknown field(s): {', '.join(unknown)}")

        normalized = dict(payload)
        normalized["id"] = normalized.get("id") or f"post-{uuid.uuid4().hex[:12]}"
        title = normalized.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValidationError("title is required and must be a non-empty string")
        normalized["title"] = title.strip()

        for list_field in ("text_on_image", "props"):
            value = normalized.get(list_field)
            if isinstance(value, str):
                normalized[list_field] = [part.strip() for part in value.split(",") if part.strip()]

        post = cls(**normalized)
        post.validate()
        return post

    def validate(self) -> None:
        if not self.id.strip():
            raise ValidationError("id must be a non-empty string")
        if self.post_date is not None:
            try:
                date.fromisoformat(self.post_date)
            except ValueError as exc:
                raise ValidationError("post_date must use YYYY-MM-DD") from exc

        integer_metrics = {
            "views": self.views,
            "shares": self.shares,
            "likes": self.likes,
            "comments": self.comments,
            "saves": self.saves,
            "follows_generated": self.follows_generated,
            "character_count": self.character_count,
        }
        for name, value in integer_metrics.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValidationError(f"{name} must be a non-negative integer or null")

        if self.watch_time is not None and (
            isinstance(self.watch_time, bool)
            or not isinstance(self.watch_time, (int, float))
            or self.watch_time < 0
        ):
            raise ValidationError("watch_time must be a non-negative number or null")

        if self.completion_rate is not None and (
            isinstance(self.completion_rate, bool)
            or not isinstance(self.completion_rate, (int, float))
            or not 0 <= self.completion_rate <= 1
        ):
            raise ValidationError("completion_rate must be between 0 and 1 or null")

        for list_name, values in (("text_on_image", self.text_on_image), ("props", self.props)):
            if values is not None and (
                not isinstance(values, list) or any(not isinstance(item, str) for item in values)
            ):
                raise ValidationError(f"{list_name} must be a list of strings or null")
            if values is not None and len(values) != len(set(values)):
                raise ValidationError(f"{list_name} must not contain duplicate values")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_records(path: Path = DEFAULT_DATA_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValidationError(f"{path} must contain a JSON array")
    return data


def validate_against_schema_contract(
    record: dict[str, Any], schema_path: Path = DEFAULT_SCHEMA_PATH
) -> None:
    """Validate the record against the checked-in schema subset used by v1.

    Version one intentionally avoids a third-party JSON Schema dependency. This
    validator enforces required fields, additionalProperties, JSON types,
    numeric bounds, array item types, uniqueness, and ISO dates from the schema.
    """

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ValidationError(f"Invalid schema contract: {schema_path}")

    missing = sorted(set(required) - set(record))
    if missing:
        raise ValidationError(f"Schema-required field(s) missing: {', '.join(missing)}")
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(record) - set(properties))
        if unknown:
            raise ValidationError(f"Schema-disallowed field(s): {', '.join(unknown)}")

    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "array": list,
        "object": dict,
        "boolean": bool,
        "null": type(None),
    }
    for name, rules in properties.items():
        value = record.get(name)
        allowed_types = rules.get("type", [])
        if isinstance(allowed_types, str):
            allowed_types = [allowed_types]
        python_types = tuple(type_map[item] for item in allowed_types if item in type_map)
        if not python_types or isinstance(value, bool) and "boolean" not in allowed_types:
            if isinstance(value, bool) and "boolean" not in allowed_types:
                raise ValidationError(f"{name} does not match schema type {allowed_types}")
        elif not isinstance(value, python_types):
            raise ValidationError(f"{name} does not match schema type {allowed_types}")

        if value is None:
            continue
        if "minimum" in rules and value < rules["minimum"]:
            raise ValidationError(f"{name} is below schema minimum {rules['minimum']}")
        if "maximum" in rules and value > rules["maximum"]:
            raise ValidationError(f"{name} exceeds schema maximum {rules['maximum']}")
        if isinstance(value, str) and rules.get("minLength") and len(value) < rules["minLength"]:
            raise ValidationError(f"{name} is shorter than the schema minimum")
        if rules.get("format") == "date" and isinstance(value, str):
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValidationError(f"{name} does not match the schema date format") from exc
        if isinstance(value, list):
            item_type = rules.get("items", {}).get("type")
            if item_type in type_map and any(not isinstance(item, type_map[item_type]) for item in value):
                raise ValidationError(f"{name} contains an item with the wrong schema type")
            if rules.get("uniqueItems") and len(value) != len(set(value)):
                raise ValidationError(f"{name} violates schema uniqueItems")


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def duplicate_reason(existing: Iterable[dict[str, Any]], candidate: dict[str, Any]) -> str | None:
    for record in existing:
        if record.get("id") == candidate["id"]:
            return f"id {candidate['id']} already exists"

        asset_key = (
            candidate.get("platform"),
            candidate.get("post_date"),
            candidate.get("uploaded_asset_reference"),
        )
        existing_asset_key = (
            record.get("platform"),
            record.get("post_date"),
            record.get("uploaded_asset_reference"),
        )
        if all(asset_key) and asset_key == existing_asset_key:
            return "platform, post_date, and uploaded_asset_reference match an existing post"

        title_key = (candidate.get("platform"), candidate.get("post_date"), candidate.get("title"))
        existing_title_key = (record.get("platform"), record.get("post_date"), record.get("title"))
        if all(title_key) and title_key == existing_title_key:
            return "platform, post_date, and title match an existing post"
    return None


def append_post(post: SocialPost, path: Path = DEFAULT_DATA_PATH) -> dict[str, Any]:
    records = load_records(path)
    candidate = post.to_dict()
    validate_against_schema_contract(candidate)
    reason = duplicate_reason(records, candidate)
    if reason:
        raise ValidationError(f"Likely duplicate rejected: {reason}")
    records.append(candidate)
    atomic_write_json(path, records)
    return candidate


def _add_cli_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--id")
    parser.add_argument("--title")
    parser.add_argument("--platform")
    parser.add_argument("--post-date")
    for field in ("views", "shares", "likes", "comments", "saves", "follows-generated", "character-count"):
        parser.add_argument(f"--{field}", type=int)
    parser.add_argument("--watch-time", type=float)
    parser.add_argument("--completion-rate", type=float)
    parser.add_argument("--format")
    parser.add_argument("--storyline")
    parser.add_argument("--left-panel-summary")
    parser.add_argument("--right-panel-summary")
    parser.add_argument("--caption")
    parser.add_argument("--text-on-image", action="append")
    parser.add_argument("--background-color")
    parser.add_argument("--accent-color")
    parser.add_argument("--camera-angle")
    parser.add_argument("--props", action="append")
    parser.add_argument("--emotional-theme")
    parser.add_argument("--brand-integration")
    parser.add_argument("--uploaded-asset-reference")
    parser.add_argument("--notes")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-file", type=Path, help="JSON object containing a social-post record")
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Validate and print without writing")
    _add_cli_fields(parser)
    return parser.parse_args()


def payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.json_file:
        try:
            loaded = json.loads(args.json_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"Unable to read {args.json_file}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValidationError("--json-file must contain one JSON object")
        payload.update(loaded)

    for key, value in vars(args).items():
        if key in {"json_file", "data_file", "dry_run"} or value is None:
            continue
        payload[key] = value
    return payload


def main() -> int:
    args = parse_args()
    try:
        post = SocialPost.from_mapping(payload_from_args(args))
        candidate = post.to_dict()
        validate_against_schema_contract(candidate)
        record = candidate if args.dry_run else append_post(post, args.data_file)
    except ValidationError as exc:
        print(f"error: {exc}")
        return 2

    print(json.dumps(record, indent=2, ensure_ascii=False))
    if args.dry_run:
        print("Validated only; no data was written.")
    else:
        print(f"Added {record['id']} to {args.data_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
