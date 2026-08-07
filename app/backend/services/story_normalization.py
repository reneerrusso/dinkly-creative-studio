from __future__ import annotations

import re
from typing import Any, Literal

SceneRichness = Literal["Sparse", "Balanced", "Detailed"]


def infer_left_character(record: dict[str, Any]) -> Literal["boy", "girl"]:
    supplied = str(record.get("left_character") or "").lower()
    if supplied in {"boy", "girl"}:
        return supplied  # type: ignore[return-value]
    scene = str(record.get("left_scene") or record.get("left_character_action") or "").lower()
    clearly_girl = ("girl dinkly" in scene or "dinka" in scene) and "dinko" not in scene and "boy dinkly" not in scene
    return "girl" if clearly_girl else "boy"


def scene_richness(record: dict[str, Any]) -> SceneRichness:
    left_props = _strings(record.get("left_props"))
    right_props = _strings(record.get("right_props"))
    left_setting = str(record.get("left_setting") or "").strip()
    right_setting = str(record.get("right_setting") or "").strip()
    total_props = len(left_props) + len(right_props)
    if not left_setting or not right_setting or total_props < 2:
        return "Sparse"
    multiple_settings = any(
        marker in f"{left_setting} {right_setting}".lower()
        for marker in ("multiple locations", "several rooms", "then moves to", "and then")
    )
    if len(left_props) > 5 or len(right_props) > 5 or multiple_settings:
        return "Detailed"
    return "Balanced"


def scene_warnings(record: dict[str, Any]) -> list[str]:
    richness = scene_richness(record)
    if richness == "Sparse":
        return ["This concept may not contain enough visual context to tell the story without text."]
    if richness == "Detailed":
        return ["This scene may contain too many competing props for consistent image generation."]
    return []


def normalize_story_record(
    record: dict[str, Any], *, category: str | None = None, source: str | None = None
) -> dict[str, Any]:
    title_left, title_right = _titles(record)
    left_character = infer_left_character(record)
    left_action = str(
        record.get("left_character_action")
        or record.get("left_scene")
        or record.get("concept")
        or "Experiences the ordinary activity alone."
    ).strip()
    right_actions = str(
        record.get("right_character_actions")
        or record.get("right_scene")
        or record.get("concept")
        or "Share the same ordinary activity together."
    ).strip()
    left_setting = str(record.get("left_setting") or "").strip()
    right_setting = str(record.get("right_setting") or "").strip()
    left_props = _strings(record.get("left_props"))
    right_props = _strings(record.get("right_props"))
    left_emotion = str(record.get("left_emotion") or "Neutral, bored, or gently sad—never happy.").strip()
    right_emotion = str(record.get("right_emotion") or "Warm and connected because the moment is shared.").strip()
    shared_environment = str(
        record.get("shared_environment")
        or record.get("visual_distinction")
        or "The same simple environment, camera, and main furniture continue across both panels."
    ).strip()
    environmental_contrast = str(
        record.get("environmental_contrast")
        or "The left remains quiet and sparse; the right adds warmth and gentle activity without changing the core location."
    ).strip()
    background = str(
        record.get("background_color")
        or record.get("recommended_background_color")
        or "warm cream"
    ).strip()
    accent = str(record.get("accent_color") or record.get("recommended_accent_color") or "muted mustard").strip()
    camera = str(record.get("camera_angle") or record.get("recommended_camera_angle") or "medium straight-on").strip()
    normalized = {
        **record,
        "id": str(record.get("id") or "story-normalized"),
        "title_left": title_left,
        "title_right": title_right,
        "format": str(record.get("format") or "x-with-you"),
        "category": str(record.get("category") or category or "Everyday routines"),
        "left_character": left_character,
        "left_character_action": left_action,
        "left_setting": left_setting,
        "left_props": left_props,
        "left_emotion": left_emotion,
        "right_characters": "boy_and_girl",
        "right_character_actions": right_actions,
        "right_setting": right_setting,
        "right_props": right_props,
        "right_emotion": right_emotion,
        "shared_environment": shared_environment,
        "environmental_contrast": environmental_contrast,
        "background_color": background,
        "accent_color": accent,
        "camera_angle": camera,
        "prop_count": max(len(left_props), len(right_props)),
        "brand_friendly": bool(record.get("brand_friendly")),
        "brand_categories": _strings(record.get("brand_categories")),
        "execution_risks": _strings(record.get("execution_risks")),
        "notes": record.get("notes"),
        "status": str(record.get("status") or ("Approved" if record.get("approved") else "Draft")),
        "migration_version": 2,
        "source": source or record.get("source") or "normalized",
    }
    normalized["title_pair"] = {"left": title_left, "right": title_right}
    normalized["title"] = str(record.get("title") or title_left.title())
    normalized["title_direction"] = str(record.get("title_direction") or f"{title_left} / {title_right}")
    normalized["left_scene"] = str(record.get("left_scene") or _compose_left(normalized))
    normalized["right_scene"] = str(record.get("right_scene") or _compose_right(normalized))
    normalized["concept"] = str(
        record.get("concept")
        or record.get("emotional_insight")
        or f"{left_emotion} The same moment feels warmer together."
    )
    normalized["visual_distinction"] = str(record.get("visual_distinction") or environmental_contrast)
    normalized["approved"] = normalized["status"] == "Approved"
    normalized["scene_richness"] = scene_richness(normalized)
    normalized["scene_warnings"] = scene_warnings(normalized)
    return normalized


def _titles(record: dict[str, Any]) -> tuple[str, str]:
    pair = record.get("title_pair") if isinstance(record.get("title_pair"), dict) else {}
    left = str(record.get("title_left") or pair.get("left") or "").strip()
    right = str(record.get("title_right") or pair.get("right") or "").strip()
    if (not left or not right) and record.get("title_direction"):
        parts = re.split(r"\s*/\s*", str(record["title_direction"]), maxsplit=1)
        left = left or parts[0].strip()
        right = right or (parts[1].strip() if len(parts) > 1 else "")
    left = left or str(record.get("title") or "UNTITLED").upper()
    right = right or f"{left} WITH YOU"
    return left, right


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _compose_left(record: dict[str, Any]) -> str:
    name = "Boy DINKLY" if record["left_character"] == "boy" else "Girl DINKLY"
    props = ", ".join(record["left_props"]) or "no unnecessary props"
    return (
        f"{name} {record['left_character_action']} Setting: {record['left_setting'] or 'a minimal environment'}. "
        f"Purposeful props: {props}. Emotion: {record['left_emotion']}"
    )


def _compose_right(record: dict[str, Any]) -> str:
    props = ", ".join(record["right_props"]) or "no unnecessary props"
    return (
        f"Boy DINKLY and Girl DINKLY {record['right_character_actions']} "
        f"Setting: {record['right_setting'] or 'the same minimal environment'}. "
        f"Purposeful props: {props}. Emotion: {record['right_emotion']}"
    )
