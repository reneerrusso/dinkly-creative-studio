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
    if any(word in combined for word in ("chair", "table", "sofa", "bed", "counter", "vanity", "island")):
        rules.append("Name and preserve the visible support surface; bodies stay on the floor or directly on chair, sofa, or bed seats—never on tabletops or counters.")
    if "cart" in combined:
        rules.append("Characters stand on the floor beside the shopping cart; only groceries belong inside it.")
    if "phone" in combined:
        rules.append("Show exactly one crisp phone, approximately the size of Dinko's face and no more than 8–10% of the canvas.")
    if "toothbrush" in combined:
        rules.append("Each toothbrush is narrower than one eye and shorter than one-third of a character body width.")
    if any(word in combined for word in ("mug", "coffee", "cup")):
        rules.append("Mugs fit close to the round bodies without covering eyes or mouths and do not create hands or fingers.")
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
    product_refs = payload.get("product_references") or []
    if isinstance(product_refs, str):
        product_refs = [product_refs]
    opportunities = payload.get("brand_placement_opportunities") or []
    if isinstance(opportunities, str):
        opportunities = [opportunities]

    scene = str(payload.get("scene") or payload.get("right_scene") or payload.get("left_scene") or "")
    replacements = {
        "CHARACTER_REFERENCE": str(payload.get("character_reference") or DEFAULT_CHARACTER_REFERENCE),
        "CAMERA_ANGLE": str(payload.get("recommended_camera_angle") or payload.get("camera_angle") or "medium straight-on"),
        "BACKGROUND_COLOR": str(payload.get("recommended_background_color") or payload.get("background_color") or "pastel peach"),
        "ACCENT_COLOR": str(payload.get("recommended_accent_color") or payload.get("accent_color") or "muted sage"),
        "LEFT_SCENE": str(payload.get("left_scene") or ""),
        "RIGHT_SCENE": str(payload.get("right_scene") or ""),
        "LEFT_TEXT": str(title_pair.get("left") or payload.get("left_text") or ""),
        "RIGHT_TEXT": str(title_pair.get("right") or payload.get("right_text") or ""),
        "CHARACTER_LOCK": str(payload.get("character_lock") or CHARACTER_LOCK),
        "FAILURE_PREVENTION": relevant_failure_prevention(payload),
        "SCENE": scene,
        "TEXT": str(payload.get("text") or title_pair.get("right") or ""),
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
