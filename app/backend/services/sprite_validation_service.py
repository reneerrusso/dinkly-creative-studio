from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.backend.services.repository_service import RepositoryError, RepositoryService

SUPPORTED_FRAME_EXTENSIONS = {".png", ".webp"}
PRIMARY_CHECKLIST = [
    "Correct character",
    "Correct body proportions",
    "Correct eye shape",
    "Correct orange spots",
    "Correct outline thickness",
    "Correct mouth",
    "Correct arm length",
    "Correct nub feet",
    "Correct hair",
    "Correct bow",
    "Correct ponytail",
    "Same character scale",
    "No added clothing",
    "No human anatomy",
    "No background artifacts",
    "No cropped body",
]


class SpriteValidationService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.worker = repository.path("scripts/sprite_image_worker.py")

    def _pillow_python(self) -> str:
        candidates = [
            os.getenv("DINKLY_PILLOW_PYTHON"),
            sys.executable,
            "/Users/reneerusso/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
        ]
        for candidate in candidates:
            if not candidate or not Path(candidate).is_file():
                continue
            check = subprocess.run(
                [candidate, "-c", "import PIL"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if check.returncode == 0:
                return candidate
        raise RepositoryError(
            "Pillow is required for sprite image processing. Install project dependencies or set "
            "DINKLY_PILLOW_PYTHON to a Python interpreter with Pillow installed."
        )

    def run_worker(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        process = subprocess.run(
            [self._pillow_python(), str(self.worker), operation],
            input=json.dumps(payload) + "\n",
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if process.returncode != 0:
            detail = process.stderr.strip().splitlines()[-1] if process.stderr.strip() else "Image processing failed"
            raise RepositoryError(detail)
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise RepositoryError("Sprite image processor returned invalid output") from exc
        if not isinstance(result, dict):
            raise RepositoryError("Sprite image processor returned an invalid result")
        return result

    def inspect(self, path: Path) -> dict[str, Any]:
        safe_path = self.repository.path(self.repository.relative(path))
        return self.run_worker("inspect", {"path": str(safe_path)})

    def validate_upload(
        self,
        *,
        filename: str,
        content: bytes,
        character_type: str,
        expected_dimensions: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_FRAME_EXTENSIONS:
            raise RepositoryError("Sprite frames must be PNG or WEBP")
        if not content:
            raise RepositoryError("The uploaded frame is empty")
        if len(content) > self.repository.settings.max_upload_bytes:
            raise RepositoryError("Sprite frame exceeds the configured local upload limit")
        safe_name = Path(filename).name
        if safe_name != filename or ".." in safe_name:
            raise RepositoryError("Unsafe sprite frame filename")
        return {"extension": extension}

    def image_warnings(
        self,
        inspection: dict[str, Any],
        *,
        character_type: str,
        expected_dimensions: tuple[int, int] | None,
    ) -> list[str]:
        warnings: list[str] = []
        if character_type != "effect" and not inspection.get("transparent"):
            warnings.append("Character and prop frames require a transparent background")
        if inspection.get("fully_transparent"):
            warnings.append("Frame is fully transparent")
        if expected_dimensions and (inspection.get("width"), inspection.get("height")) != expected_dimensions:
            warnings.append(
                f"Canvas dimensions differ from the animation standard {expected_dimensions[0]}×{expected_dimensions[1]}"
            )
        if int(inspection.get("width", 0)) < 16 or int(inspection.get("height", 0)) < 16:
            warnings.append("Frame canvas is too small for reliable production use")
        return warnings

    def animation_warnings(self, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if not frames:
            return [{"frame_id": None, "issue": "No frames uploaded", "severity": "warning"}]
        dimensions = {(frame.get("width"), frame.get("height")) for frame in frames}
        if len(dimensions) > 1:
            issues.append({"frame_id": None, "issue": "Canvas dimensions differ between frames", "severity": "error"})
        for frame in frames:
            if not 0 <= float(frame.get("anchor_x", -1)) <= 1 or not 0 <= float(frame.get("anchor_y", -1)) <= 1:
                issues.append({"frame_id": frame.get("id"), "issue": "Anchor is outside normalized 0–1 bounds", "severity": "error"})
            if abs(int(frame.get("offset_y", 0))) > max(8, int(frame.get("height", 0)) * 0.08):
                issues.append({"frame_id": frame.get("id"), "issue": "Feet may drift from the floor line", "severity": "warning"})
            for warning in frame.get("validation_warnings", []):
                issues.append({"frame_id": frame.get("id"), "issue": warning, "severity": "warning"})
        return issues

    def checklist(self, character_type: str) -> list[str]:
        checklist = list(PRIMARY_CHECKLIST)
        if character_type == "dinko":
            checklist.insert(9, "Exactly two hair tufts")
        elif character_type == "dinka":
            checklist.insert(9, "Exact bright red bow")
            checklist.insert(10, "Connected ponytail")
        return checklist

