from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.backend.services.repository_service import RepositoryError, RepositoryService

EMOTION_WORDS = {
    "affection",
    "celebration",
    "comfort",
    "companionship",
    "friendship",
    "fun",
    "happiness",
    "joy",
    "love",
    "romance",
    "sadness",
    "smile",
    "togetherness",
}


class ReferenceAnalysisService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def analyze(self, relative_path: str) -> dict[str, Any]:
        image = self.repository.path(relative_path)
        if not image.is_file() or not self.repository.relative(image).startswith("app-data/uploads/"):
            raise RepositoryError("Reference analysis requires an uploaded local image")
        script = self.repository.path("scripts/analyze_reference_image.swift")
        module_cache = Path(tempfile.gettempdir()) / "dinkly-swift-module-cache"
        module_cache.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/xcrun",
                    "swift",
                    "-module-cache-path",
                    str(module_cache),
                    str(script),
                    str(image),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )
            signals = json.loads(completed.stdout)
        except subprocess.TimeoutExpired as exc:
            raise RepositoryError("Local reference analysis timed out; try a smaller PNG or JPG") from exc
        except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise RepositoryError(f"Could not analyze the reference image locally: {detail.strip()[:240]}") from exc
        warnings = signals.get("analysis_warnings") or []
        warning = None
        if warnings:
            warning = (
                "Some on-device detectors were unavailable ("
                + ", ".join(str(item) for item in warnings)
                + "). Review and correct the written brief."
            )
        return {
            "signals": signals,
            "scene_brief": self._scene_brief(signals, image),
            "analysis_warning": warning,
        }

    def _scene_brief(self, signals: dict[str, Any], image: Path) -> str:
        orientation = str(signals.get("orientation") or "unknown")
        width = signals.get("width")
        height = signals.get("height")
        labels = [
            str(item.get("label"))
            for item in signals.get("classification_labels", [])
            if isinstance(item, dict) and item.get("label")
        ]
        text_items = [
            item
            for item in signals.get("recognized_text", [])
            if isinstance(item, dict) and str(item.get("text", "")).strip()
        ]
        figures = signals.get("faces") or signals.get("human_figures") or []
        positions = [
            f"{item.get('horizontal', 'center')} {item.get('vertical', 'middle')}"
            for item in figures
            if isinstance(item, dict)
        ]
        environment = ", ".join(labels[:8]) or "no reliable setting label detected"
        recognized = " | ".join(str(item["text"]).strip() for item in text_items[:12]) or "no readable text detected"
        emotions = sorted({label for label in labels if label.lower() in EMOTION_WORDS})
        emotion_line = ", ".join(emotions) if emotions else "preserve the visible facial-expression and closeness contrast shown in the source"
        placement = (
            ", ".join(positions[:6])
            if positions
            else "no reliable figure boxes detected; rely on user corrections or other detected cues instead of inventing precise placement"
        )
        average = str(signals.get("average_color") or "not detected")
        return (
            f"Local scene analysis for {image.name}: {orientation} {width}×{height} composition. "
            f"Detected visual and setting cues: {environment}. "
            f"Detected focal-figure placement: {placement}. "
            f"Readable source text and storyline cues: {recognized}. "
            f"Detected emotional cues: {emotion_line}. "
            f"Average source color: {average}; treat this only as evidence about the source environment, not as permission to replace official DINKLY character colors. "
            "Translate these cues into one clean DINKLY scene while preserving the source's apparent camera framing, environment hierarchy, interaction, and emotional beat. "
            "This written analysis is self-contained; the original reference image will not accompany the final generation prompt."
        )
