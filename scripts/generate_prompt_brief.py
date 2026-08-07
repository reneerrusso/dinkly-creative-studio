#!/usr/bin/env python3
"""Render a concise Nano Banana prompt from a DINKLY storyline JSON record."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "PROMPT_TEMPLATES"
DEFAULT_CHARACTER_REFERENCE = "references/dinkly_young.png"
TEMPLATE_MAP = {
    "split": "SplitComic.md",
    "split-comic": "SplitComic.md",
    "x-with-you": "XWithYou.md",
    "x with you": "XWithYou.md",
    "before-after": "BeforeAfter.md",
    "before and after": "BeforeAfter.md",
    "single": "SinglePanel.md",
    "single-panel": "SinglePanel.md",
    "close-up": "CloseUp.md",
    "closeup": "CloseUp.md",
    "brand": "BrandPlacement.md",
    "brand-placement": "BrandPlacement.md",
    "image-edit": "ImageEdit.md",
    "edit": "ImageEdit.md",
    "social-learning-analysis": "SocialLearningAnalysis.md",
}

CHARACTER_LOCK = (
    "Dinka and Dinko keep the exact round proportions, bright-yellow color, orange spots, black oval eyes "
    "with white highlights, thick clean black outlines, tiny nub arms, and nub feet from the model sheet. "
    "They remain the same body size. Dinko has exactly two hair tufts. Dinka has the bright-red bow and "
    "connected ponytail. No visible legs, knees, human arms, hands, fingers, clothing, shoes, human lips, "
    "human noses, or altered eye styles."
)

BOY_LEFT_LOCK = (
    "Left panel: Boy DINKLY matches the official reference exactly, including exactly two hair tufts, "
    "tiny nub arms, and tiny nub feet. He has no visible legs, fingers, clothing, or shoes."
)
GIRL_LEFT_LOCK = (
    "Left panel: Girl DINKLY matches the official reference exactly, including the exact bright-red bow, "
    "connected ponytail, tiny nub arms, and tiny nub feet. She has no visible legs, fingers, clothing, or shoes."
)
RIGHT_PAIR_LOCK = (
    "Right panel: Boy DINKLY and Girl DINKLY appear together at equal body size. Boy keeps exactly two hair "
    "tufts; Girl keeps the exact bright-red bow and connected ponytail. Both retain official bright-yellow "
    "round bodies, orange spots, black oval eyes with white highlights, thick clean black outlines, nub arms, "
    "and nub feet with no visible legs, hands, fingers, clothing, or shoes."
)


def choose_template(format_name: str, override: str | None = None) -> Path:
    if override:
        path = TEMPLATE_DIR / override
    else:
        path = TEMPLATE_DIR / TEMPLATE_MAP.get(format_name.lower().strip(), "SplitComic.md")
    if not path.exists():
        raise ValueError(f"Prompt template does not exist: {path}")
    return path


def relevant_failure_prevention(payload: dict[str, Any]) -> str:
    combined = " ".join(str(value) for value in payload.values()).lower()
    rules: list[str] = []
    if any(word in combined for word in ("table", "counter", "vanity", "island")):
        rules.append(
            "Keep every character grounded on the floor; tables and counters remain secondary props, "
            "and no character sits or stands on them."
        )
    elif any(word in combined for word in ("chair", "sofa", "bed")):
        rules.append(
            "Place seated or resting bodies directly on the visible chair seat, sofa cushion, or bed surface; "
            "do not make them float or add visible legs."
        )
    if "cart" in combined:
        rules.append("Characters stand on the floor beside the shopping cart; only groceries belong inside it.")
    if "phone" in combined:
        rules.append("Show exactly one crisp phone, approximately the size of Dinko's face and no more than 8–10% of the canvas.")
    if "toothbrush" in combined:
        rules.append("Each toothbrush is narrower than one eye and shorter than one-third of a character body width.")
    if any(word in combined for word in ("mug", "coffee", "cup")):
        rules.append(
            "Cups or mugs stay proportional to the round bodies, do not cover eyes or mouths, "
            "and do not create hands or fingers."
        )
    if any(word in combined for word in ("brand", "product", "package", "bottle")):
        rules.append("Character references control characters only; product references control products only. Use a placeholder-first pass if packaging harms character accuracy.")
    if any(word in combined for word in ("walk", "dance", "run")):
        rules.append("Imply motion through body lean and spacing; do not create visible legs, knees, or long limbs.")
    if not rules:
        rules.append("Keep both characters grounded, on-model, equal in size, and unobscured by props.")
    return " ".join(rules[:3])


def build_replacements(payload: dict[str, Any]) -> dict[str, str]:
    title_pair = payload.get("title_pair") or {}
    if not isinstance(title_pair, dict):
        title_pair = {}
    if not title_pair:
        title_pair = {
            "left": payload.get("title_left") or "",
            "right": payload.get("title_right") or "",
        }
    product_refs = payload.get("product_references") or []
    if isinstance(product_refs, str):
        product_refs = [product_refs]
    opportunities = payload.get("brand_placement_opportunities") or []
    if isinstance(opportunities, str):
        opportunities = [opportunities]

    left_character = "girl" if str(payload.get("left_character") or "boy").lower() == "girl" else "boy"
    left_character_display = "Girl DINKLY" if left_character == "girl" else "Boy DINKLY"
    left_props = payload.get("left_props") or []
    right_props = payload.get("right_props") or []
    if isinstance(left_props, str):
        left_props = [item.strip() for item in left_props.split(",") if item.strip()]
    if isinstance(right_props, str):
        right_props = [item.strip() for item in right_props.split(",") if item.strip()]

    left_scene = str(payload.get("left_scene") or "").strip()
    right_scene = str(payload.get("right_scene") or "").strip()
    scene = str(payload.get("scene") or right_scene or left_scene or "").strip()
    left_text = str(title_pair.get("left") or payload.get("left_text") or "").strip()
    right_text = str(title_pair.get("right") or payload.get("right_text") or "").strip()
    single_text = str(payload.get("text") or right_text or "").strip()
    has_any_text = bool(left_text or right_text or single_text)
    has_source_analysis = bool(payload.get("scene_reference_analysis") or payload.get("scene_reference_path"))
    source_basis = (
        "the supplied source-comic analysis or other composition notes"
        if has_source_analysis
        else "a simple, relatable everyday routine"
    )

    left_scene_instruction = left_scene or (
        f"Create a simple ordinary-alone moment from {source_basis}. "
        f"{left_character_display} is neutral, bored, or gently sad—never happy."
    )
    right_scene_instruction = right_scene or (
        f"Create a warmer together version from {source_basis}. "
        "Dinka and Dinko share one clear action."
    )
    single_scene_instruction = scene or (
        f"Create one clear DINKLY moment from {source_basis}. "
        "Keep the composition minimal and emotionally readable."
    )

    def caption_instruction(value: str, location: str) -> str:
        if value:
            return f"Render this {location} caption exactly, without quotation marks or added punctuation: {value}"
        return f"Do not render a caption, placeholder, punctuation, or any other text in the {location}."

    left_action = str(payload.get("left_character_action") or left_scene_instruction).strip()
    right_actions = str(payload.get("right_character_actions") or right_scene_instruction).strip()
    left_setting = str(payload.get("left_setting") or "A minimal setting consistent with the activity and shared environment.").strip()
    right_setting = str(payload.get("right_setting") or left_setting).strip()
    shared_environment = str(
        payload.get("shared_environment")
        or f"Both panels use the same {left_setting.lower()} with consistent floor, main furniture, prop scale, and camera view."
    ).strip()
    environmental_contrast = str(
        payload.get("environmental_contrast")
        or "The left panel feels quiet and sparse. The right panel keeps the same activity and location but feels warmer through shared interaction and a few purposeful prop changes."
    ).strip()
    left_emotion = str(
        payload.get("left_emotion")
        or "Neutral, bored, or gently sad—never happy, devastated, or dramatic."
    ).strip()
    right_emotion = str(
        payload.get("right_emotion")
        or "Warm and connected because the ordinary moment is shared, not unrealistically perfect."
    ).strip()
    scene_aware_lock = f"{GIRL_LEFT_LOCK if left_character == 'girl' else BOY_LEFT_LOCK} {RIGHT_PAIR_LOCK}"

    replacements = {
        "CHARACTER_REFERENCE": str(payload.get("character_reference") or DEFAULT_CHARACTER_REFERENCE),
        "CAMERA_ANGLE": str(payload.get("recommended_camera_angle") or payload.get("camera_angle") or "medium straight-on"),
        "BACKGROUND_COLOR": str(payload.get("recommended_background_color") or payload.get("background_color") or "pastel peach"),
        "ACCENT_COLOR": str(payload.get("recommended_accent_color") or payload.get("accent_color") or "muted sage"),
        "LEFT_SCENE": left_scene_instruction,
        "RIGHT_SCENE": right_scene_instruction,
        "LEFT_CHARACTER_DISPLAY": left_character_display,
        "LEFT_ACTION": left_action,
        "LEFT_SETTING": left_setting,
        "LEFT_PROPS": "; ".join(str(item) for item in left_props) or "No extra props beyond those required by the action.",
        "LEFT_EMOTION": left_emotion,
        "RIGHT_CHARACTERS_DISPLAY": "Boy DINKLY and Girl DINKLY",
        "RIGHT_ACTIONS": right_actions,
        "RIGHT_SETTING": right_setting,
        "RIGHT_PROPS": "; ".join(str(item) for item in right_props) or "Use only the purposeful props required by the shared activity.",
        "RIGHT_EMOTION": right_emotion,
        "SHARED_ENVIRONMENT": shared_environment,
        "ENVIRONMENTAL_CONTRAST": environmental_contrast,
        "SCENE_AWARE_CHARACTER_LOCK": scene_aware_lock,
        "LEFT_TEXT": left_text,
        "RIGHT_TEXT": right_text,
        "LEFT_CAPTION_INSTRUCTION": caption_instruction(left_text, "left panel"),
        "RIGHT_CAPTION_INSTRUCTION": caption_instruction(right_text, "right panel"),
        "TEXT_STYLE_INSTRUCTION": (
            "Use Bubblebody Neue Regular for supplied captions and keep the bottom caption zone clear."
            if has_any_text
            else "Do not add captions, labels, dialogue, quotation marks, or decorative writing anywhere."
        ),
        "TEXT_QUALITY_CHECK": (
            "Verify all supplied captions are exact and contain no quotation marks or added punctuation."
            if has_any_text
            else "Verify the artwork contains no caption, placeholder, punctuation, or other writing."
        ),
        "CHARACTER_LOCK": str(payload.get("character_lock") or CHARACTER_LOCK),
        "FAILURE_PREVENTION": relevant_failure_prevention(payload),
        "SCENE": single_scene_instruction,
        "TEXT": single_text,
        "TEXT_INSTRUCTION": caption_instruction(single_text, "image"),
        "BRAND_REFERENCE": ", ".join(str(item) for item in product_refs) or "no product reference supplied",
        "PRODUCT_PLACEMENT": "; ".join(str(item) for item in opportunities) or str(payload.get("product_placement") or "No product placement specified."),
        "EDIT_REGION": str(payload.get("edit_region") or "the specified error region"),
        "UNCHANGED": str(payload.get("unchanged") or "Leave all unaffected areas completely unchanged."),
        "CHANGE": str(payload.get("change") or "Apply only the requested correction."),
        "DO_NOT_INTRODUCE": str(payload.get("do_not_introduce") or "Do not introduce new text, props, colors, anatomy, or character changes."),
        "SOCIAL_EVIDENCE": str(payload.get("social_evidence") or "No evidence records supplied."),
    }
    return replacements


def render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for name, value in replacements.items():
        rendered = rendered.replace(f"{{{{{name}}}}}", value)
    unresolved = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", rendered)))
    if unresolved:
        raise ValueError(f"Unresolved template field(s): {', '.join(unresolved)}")
    return rendered.strip() + "\n"


def generate_prompt(payload: dict[str, Any], template_override: str | None = None) -> tuple[Path, str]:
    format_name = str(payload.get("format") or "split-comic")
    template_path = choose_template(format_name, template_override)
    template = template_path.read_text(encoding="utf-8")
    return template_path, render_template(template, build_replacements(payload))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyline", type=Path, help="JSON storyline or edit brief")
    parser.add_argument("--template", help="Explicit template filename from PROMPT_TEMPLATES")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.storyline.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("storyline input must be one JSON object")
        template_path, prompt = generate_prompt(payload, args.template)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(prompt, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2

    print(prompt)
    print(f"Template: {template_path.relative_to(ROOT)}")
    if args.output:
        print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
