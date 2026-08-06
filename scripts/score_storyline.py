#!/usr/bin/env python3
"""Create a transparent directional creative score for a DINKLY storyline."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEARNINGS = ROOT / "data" / "social_learnings.json"
DEFAULT_SCORES = ROOT / "data" / "storyline_scores.json"
EVALUATION_LABEL = "directional creative evaluation, not a performance prediction"

COMMON_ROUTINES = {
    "coffee", "walk", "walks", "bedtime", "shopping", "movies", "weekends", "laundry",
    "mornings", "errands", "napping", "workout", "reading", "dinner", "moving", "rain",
    "market", "toothbrush", "music", "game", "snacks", "travel", "home",
}
WARMTH_WORDS = {"comfort", "warm", "home", "safe", "together", "care", "quiet", "belong", "shared"}
HIGH_RISK_WORDS = {"table", "chair", "sofa", "bed", "counter", "vanity", "island", "cart"}
OBJECT_RISK_WORDS = {"phone", "toothbrush", "mug", "package", "product", "bottle"}
MOTION_RISK_WORDS = {"walk", "dance", "pour", "pass", "hold", "carry"}
PROHIBITED_WORDS = {"argument", "jealous", "breakup", "violence", "luxury", "status", "sarcasm"}


def clamp(value: float, minimum: int = 1, maximum: int = 10) -> int:
    return max(minimum, min(maximum, round(value)))


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _load_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def _atomic_write(path: Path, payload: Any) -> None:
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


def _matched_learning_ids(payload: dict[str, Any], learnings: list[dict[str, Any]]) -> list[str]:
    combined = " ".join(
        str(payload.get(field) or "")
        for field in ("storyline", "left_scene", "right_scene", "emotional_insight", "why_someone_would_share", "novel_angle")
    )
    concept_tokens = tokens(combined)
    matched: list[str] = []
    for learning in learnings:
        learning_text = f"{learning.get('pattern', '')} {learning.get('recommended_use', '')}"
        meaningful = {token for token in tokens(learning_text) if len(token) > 3}
        if len(concept_tokens & meaningful) >= 2:
            learning_id = learning.get("learning_id")
            if isinstance(learning_id, str):
                matched.append(learning_id)
    supplied = payload.get("relevant_social_learnings") or []
    if isinstance(supplied, list):
        matched.extend(str(item) for item in supplied)
    return list(dict.fromkeys(matched))


def _require_storyline(payload: dict[str, Any]) -> None:
    title_pair = payload.get("title_pair")
    if not isinstance(title_pair, dict) or not str(title_pair.get("left") or "").strip() or not str(title_pair.get("right") or "").strip():
        raise ValueError("title_pair must contain non-empty left and right strings")
    for field in ("left_scene", "right_scene", "emotional_insight"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f"{field} is required and must be a non-empty string")


def score_storyline(
    payload: dict[str, Any],
    learnings: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return an explainable rubric score; it is not a performance forecast."""

    _require_storyline(payload)
    learnings = learnings or []
    now = now or datetime.now(UTC)

    title_pair = {"left": str(payload["title_pair"]["left"]), "right": str(payload["title_pair"]["right"])}
    storyline_id = str(payload.get("storyline_id") or payload.get("id") or f"story-{uuid.uuid4().hex[:10]}")
    storyline = str(payload.get("storyline") or title_pair["left"])
    left_scene = str(payload["left_scene"])
    right_scene = str(payload["right_scene"])
    insight = str(payload["emotional_insight"])
    why_share = str(payload.get("why_someone_would_share") or "")
    novel_angle = str(payload.get("novel_angle") or "")
    props = [str(item) for item in (payload.get("props") or [])]
    risks = [str(item) for item in (payload.get("execution_risks") or [])]
    opportunities = [str(item) for item in (payload.get("brand_placement_opportunities") or [])]
    character_count = int(payload.get("character_count") or 2)

    combined = " ".join((storyline, left_scene, right_scene, insight, why_share, novel_angle)).lower()
    concept_tokens = tokens(combined)
    learning_ids = _matched_learning_ids(payload, learnings)

    emotional_clarity = clamp(5 + bool(left_scene) + bool(right_scene) + 2 * bool(insight) + ("together" in combined or "with you" in combined))
    relatability = clamp(5 + 2 * bool(concept_tokens & COMMON_ROUTINES) + bool(why_share) + bool(concept_tokens & WARMTH_WORDS))
    visual_simplicity = clamp(10 - max(0, len(props) - 3) - max(0, character_count - 2) - min(3, len(risks) // 2))
    brand_fit = clamp(6 + 2 * bool("with you" in combined or "together" in combined) + bool(insight) + (1 if not concept_tokens & PROHIBITED_WORDS else -4))
    originality = clamp(5 + 3 * bool(novel_angle) + bool(payload.get("recommended_camera_angle")) - (2 if storyline.lower() in {"coffee", "movies", "bedtime", "shopping"} and not novel_angle else 0))

    distortion_risk = 1
    distortion_risk += 2 if concept_tokens & HIGH_RISK_WORDS else 0
    distortion_risk += 2 if concept_tokens & OBJECT_RISK_WORDS else 0
    distortion_risk += 1 if concept_tokens & MOTION_RISK_WORDS else 0
    distortion_risk += 2 if len(props) > 5 else 0
    distortion_risk += min(2, len(risks) // 3)
    distortion_risk = clamp(distortion_risk)

    execution_ease = clamp((visual_simplicity + (11 - distortion_risk)) / 2)
    shareability = clamp(4 + 2 * bool(why_share) + bool(title_pair["right"]) + bool(concept_tokens & WARMTH_WORDS) + bool(learning_ids))
    save_potential = clamp(5 + 2 * bool(concept_tokens & WARMTH_WORDS) + bool(payload.get("recommended_background_color")) + bool("season" in combined))
    comment_potential = clamp(4 + bool(why_share) + 2 * bool(concept_tokens & {"favorite", "dialogue", "tag", "question", "always"}))
    scroll_stopping = clamp((emotional_clarity + visual_simplicity + originality) / 3)
    brand_integration = clamp(3 + min(4, len(opportunities) * 2) + bool(concept_tokens & {"coffee", "snack", "book", "game", "travel", "blanket", "drink"}))

    scores = {
        "emotional_clarity": emotional_clarity,
        "relatability": relatability,
        "visual_simplicity": visual_simplicity,
        "scroll_stopping_potential": scroll_stopping,
        "shareability": shareability,
        "save_potential": save_potential,
        "comment_potential": comment_potential,
        "dinkly_brand_fit": brand_fit,
        "originality": originality,
        "brand_integration_potential": brand_integration,
        "nano_banana_execution_ease": execution_ease,
        "risk_of_character_distortion": distortion_risk,
    }

    comparison_scores = {key: value for key, value in scores.items() if key != "risk_of_character_distortion"}
    comparison_scores["character_distortion_safety"] = 11 - distortion_risk
    weakest = min(comparison_scores, key=comparison_scores.get)
    recommendations = {
        "emotional_clarity": "Reduce the concept to one visible emotional change and one action per character.",
        "relatability": "Anchor the scene in a more specific everyday routine or recognizable shared habit.",
        "visual_simplicity": "Remove secondary props or actions and simplify the camera geometry.",
        "scroll_stopping_potential": "Strengthen the silhouette-level contrast while preserving the ordinary activity.",
        "shareability": "Clarify the relationship truth someone would immediately send to their person.",
        "save_potential": "Make the composition more comforting, seasonal, frameable, or useful as an affection message.",
        "comment_potential": "Add a specific recognizable habit without using engagement bait.",
        "dinkly_brand_fit": "Shift the emotional cause back to quiet companionship and an achievable relationship.",
        "originality": "Add a fresh act of care, camera view, or emotional detail instead of changing the setting alone.",
        "brand_integration_potential": "Identify one natural prop a partner product could replace without changing the story.",
        "nano_banana_execution_ease": "Reduce spatial complexity and use fewer high-risk props.",
        "character_distortion_safety": "Simplify furniture, object scale, or movement before prompt generation.",
    }

    positive_values = list(comparison_scores.values())
    directional_total = round(sum(positive_values) / len(positive_values), 2)
    return {
        "score_id": f"score-{uuid.uuid4().hex[:12]}",
        "storyline_id": storyline_id,
        "title_pair": title_pair,
        "format": str(payload.get("format") or "x-with-you"),
        "left_scene": left_scene,
        "right_scene": right_scene,
        "emotional_insight": insight,
        "why_someone_would_share": why_share,
        "relevant_social_learnings": learning_ids,
        "brand_placement_opportunities": opportunities,
        "execution_risks": risks,
        "recommended_background_color": str(payload.get("recommended_background_color") or "pastel peach"),
        "recommended_accent_color": str(payload.get("recommended_accent_color") or "muted sage"),
        "recommended_camera_angle": str(payload.get("recommended_camera_angle") or "medium straight-on"),
        "props": props,
        "character_count": character_count,
        "novel_angle": novel_angle,
        "scores": scores,
        "directional_total": directional_total,
        "weakest_criterion": weakest,
        "improvement_recommendation": recommendations[weakest],
        "evaluation_label": EVALUATION_LABEL,
        "created_at": now.isoformat(timespec="seconds"),
    }


def save_score(record: dict[str, Any], path: Path = DEFAULT_SCORES) -> None:
    scores = _load_list(path)
    if any(item.get("score_id") == record["score_id"] for item in scores):
        raise ValueError(f"Duplicate score_id {record['score_id']}")
    scores.append(record)
    _atomic_write(path, scores)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyline", type=Path, help="JSON storyline object")
    parser.add_argument("--learnings-file", type=Path, default=DEFAULT_LEARNINGS)
    parser.add_argument("--scores-file", type=Path, default=DEFAULT_SCORES)
    parser.add_argument("--no-save", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.storyline.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("storyline input must be one JSON object")
        record = score_storyline(payload, _load_list(args.learnings_file))
        if not args.no_save:
            save_score(record, args.scores_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
