from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CreativeClassifier(ABC):
    @abstractmethod
    def classify(self, post: dict[str, Any]) -> dict[str, Any]: ...


class MetadataClassifier(CreativeClassifier):
    """Conservative local classification from public text metadata only."""

    THEMES = {
        "comfort": ("cozy", "comfort", "home", "blanket", "rest"),
        "companionship": ("together", "with you", "friend", "couple", "love"),
        "routine": ("morning", "coffee", "dinner", "walk", "bedtime", "routine"),
        "playfulness": ("funny", "laugh", "game", "dance", "play"),
        "care": ("care", "help", "support", "safe", "hug"),
    }
    ACTIVITIES = (
        "coffee",
        "walk",
        "breakfast",
        "dinner",
        "shopping",
        "movie",
        "reading",
        "sleep",
        "travel",
        "game",
        "music",
        "rain",
        "workout",
    )

    def classify(self, post: dict[str, Any]) -> dict[str, Any]:
        caption = str(post.get("caption") or "")
        hashtags = " ".join(str(item) for item in post.get("hashtags") or [])
        text = f"{caption} {hashtags}".lower()
        theme = next((name for name, terms in self.THEMES.items() if any(term in text for term in terms)), None)
        activity = next((item for item in self.ACTIVITIES if item in text), None)
        return {
            "format": None,
            "theme": theme,
            "activity": activity,
            "setting": None,
            "hook": caption[:120] if caption else None,
            "text_on_screen": None,
            "caption_style": "short" if caption and len(caption) <= 120 else "long" if caption else None,
            "camera_angle": None,
            "visual_density": None,
            "prop_count": None,
            "character_count": None,
            "physical_closeness": None,
            "emotional_tone": theme,
            "color_family": None,
            "single_panel_or_split": None,
            "trend_reference": None,
            "brand_presence": None,
            "notes": "Partial classification from caption and hashtags only; no full video narrative was inferred.",
            "classification_source": "local public-metadata classifier",
            "classification_confidence": "low",
            "classification_partial": True,
            "input_sources_used": [source for source, value in (("caption", caption), ("hashtags", hashtags)) if value],
            "uncertainties": ["Visual attributes were not inspected.", "Video narrative was not analyzed."],
        }


class ConfiguredModelClassifier(CreativeClassifier):
    """Scaffold for an approved structured-output model integration."""

    def classify(self, post: dict[str, Any]) -> dict[str, Any]:
        return {
            **MetadataClassifier().classify(post),
            "notes": "No approved model classifier is configured; local metadata classification was used.",
        }
