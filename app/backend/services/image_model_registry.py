from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.backend.models.generation_engine import StoryBrief
from app.backend.services.repository_service import RepositoryError


class ImageModelRegistry:
    """Canonical Gemini image model registry, verified against Google docs on 2026-08-07."""

    _models: dict[str, dict[str, Any]] = {
        "nano_banana_2_lite": {
            "id": "nano_banana_2_lite",
            "key": "nano_banana_2_lite",
            "selection_mode": "lite",
            "display_name": "Nano Banana 2 Lite",
            "power_label": "FAST",
            "power_level": 1,
            "tier_label": "FAST",
            "description": "Fastest and lowest-cost. Best for simple scenes and high-volume generation.",
            "recommended_for": ["Simple scenes", "Single character", "Fast iteration"],
            "cost_tier": "lowest",
            "provider": "google_gemini",
            "model_id": "gemini-3.1-flash-lite-image",
            "capabilities": ["generate", "edit", "single_reference", "fast"],
            "supports_edit": True,
            "supports_multi_reference": False,
            "supported_resolutions": ["1K"],
            "default_resolution": "1K",
            "estimated_output_cost_usd": {"1K": 0.0336},
            "enabled": True,
        },
        "nano_banana_2": {
            "id": "nano_banana_2",
            "key": "nano_banana_2",
            "selection_mode": "balanced",
            "display_name": "Nano Banana 2",
            "power_label": "BALANCED",
            "power_level": 2,
            "tier_label": "BALANCED",
            "description": "Stronger character consistency and multi-reference generation. Recommended for most Dinko + Dinka comics.",
            "recommended_for": [
                "Dinko + Dinka",
                "Split comics",
                "Multiple references",
                "Most final production",
            ],
            "cost_tier": "standard",
            "provider": "google_gemini",
            "model_id": "gemini-3.1-flash-image",
            "capabilities": ["generate", "edit", "multi_reference", "character_consistency", "4K"],
            "supports_edit": True,
            "supports_multi_reference": True,
            "supported_resolutions": ["0.5K", "1K", "2K", "4K"],
            "default_resolution": "1K",
            "estimated_output_cost_usd": {"0.5K": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151},
            "enabled": True,
        },
        "nano_banana_pro": {
            "id": "nano_banana_pro",
            "key": "nano_banana_pro",
            "selection_mode": "pro",
            "display_name": "Nano Banana Pro",
            "power_label": "MAX",
            "power_level": 3,
            "tier_label": "MAX",
            "description": "Highest-control option for complex generation and difficult repairs.",
            "recommended_for": ["Difficult repairs", "Complex scenes", "High-control final generation"],
            "cost_tier": "highest",
            "provider": "google_gemini",
            "model_id": "gemini-3-pro-image",
            "capabilities": ["generate", "edit", "multi_reference", "precision", "brand_sensitive", "4K"],
            "supports_edit": True,
            "supports_multi_reference": True,
            "supported_resolutions": ["1K", "2K", "4K"],
            "default_resolution": "1K",
            "estimated_output_cost_usd": {"1K": 0.134, "2K": 0.134, "4K": 0.24},
            "enabled": True,
        },
    }

    def list(self, *, expose_ids: bool = True) -> list[dict[str, Any]]:
        records = [deepcopy(item) for item in self._models.values() if item["enabled"]]
        if not expose_ids:
            for record in records:
                record.pop("model_id", None)
        return records

    def get(self, key: str) -> dict[str, Any]:
        if key not in self._models or not self._models[key]["enabled"]:
            raise RepositoryError("Unknown or disabled image model")
        return deepcopy(self._models[key])

    def select(
        self,
        brief: StoryBrief,
        mode: str,
        *,
        reference_count: int,
        repair_attempt: int = 0,
        allow_pro: bool = False,
    ) -> tuple[str, str]:
        manual = {
            "lite": "nano_banana_2_lite",
            "balanced": "nano_banana_2",
            "pro": "nano_banana_pro",
        }
        if mode in manual:
            key = manual[mode]
            if key == "nano_banana_pro" and not allow_pro:
                raise RepositoryError("Nano Banana Pro requires explicit budget confirmation")
            return key, f"Selected manually: {self.get(key)['display_name']}."
        if repair_attempt >= 2:
            if allow_pro:
                return "nano_banana_pro", "Repeated complex repair with approved Pro budget."
            return "nano_banana_2", "Repeated repair; using the stronger non-Pro consistency model."
        if brief.brand_sensitive and allow_pro:
            return "nano_banana_pro", "Brand-sensitive detail with approved Pro budget."
        if brief.format in {"five_story", "five-comic"}:
            return "nano_banana_2", "Five-comic continuity requires stronger scene consistency."
        if reference_count > 1 or len(brief.right_characters) > 1:
            return "nano_banana_2", "Two character references and split-scene consistency."
        return "nano_banana_2_lite", "One character reference and a simple scene."
