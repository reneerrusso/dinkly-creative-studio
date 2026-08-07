from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.backend.services.image_model_registry import ImageModelRegistry
from app.backend.services.repository_service import RepositoryError, RepositoryService


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    path: Path
    media_type: str
    filename: str


class GenerationExportService:
    """Creates immutable, path-safe exports from persisted Generation Engine runs."""

    def __init__(self, repository: RepositoryService, registry: ImageModelRegistry) -> None:
        self.repository = repository
        self.registry = registry

    def final(self, run: dict[str, Any], output_format: str, *, comic_number: int | None = None) -> ExportArtifact:
        self._require_approved(run)
        normalized = output_format.lower()
        if normalized not in {"png", "jpg"}:
            raise RepositoryError("Final export format must be PNG or JPG")
        source = self._final_source(run, comic_number=comic_number)
        suffix = ".jpg" if normalized == "jpg" else ".png"
        stem = f"dinkly-{self._story_slug(run)}"
        if comic_number is not None:
            stem = f"{stem}-comic-{comic_number:02d}"
        else:
            date = self._date_stamp(run)
            stem = f"{stem}-{date}"
        target = self._unique_export_path(run, f"{stem}{suffix}")
        self._convert_or_copy(source, target, normalized)
        return ExportArtifact(target, "image/jpeg" if normalized == "jpg" else "image/png", target.name)

    def original(self, run: dict[str, Any], *, candidate_id: str | None = None) -> ExportArtifact:
        """Return the selected, unextended generation as an attachment."""
        selected = (
            next((item for item in run.get("candidates", []) if item.get("id") == candidate_id), None)
            if candidate_id
            else self._selected_candidate(run)
        )
        if not selected:
            selected = next((item for item in run.get("candidates", []) if item.get("recommended")), {})
        relative = run.get("original_image_path") or selected.get("image_path")
        if not relative:
            raise RepositoryError("The selected original image is unavailable")
        source = self._asset_path(run, str(relative))
        suffix = source.suffix.lower()
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix)
        if not media_type:
            raise RepositoryError("The selected original image format is unsupported")
        filename = f"dinkly-{self._story_slug(run)}-original{suffix}"
        return ExportArtifact(source, media_type, filename)

    def candidates(self, run: dict[str, Any]) -> ExportArtifact:
        self._require_approved(run)
        archive = io.BytesIO()
        used: set[str] = set()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for candidate in run.get("candidates", []):
                if not candidate.get("image_path"):
                    continue
                source = self._asset_path(run, candidate["image_path"])
                extension = source.suffix.lower()
                if extension == ".webp":
                    converted = self._unique_export_path(
                        run,
                        f".{candidate['id']}-candidate-normalized.png",
                    )
                    self._convert_or_copy(source, converted, "png")
                    source = converted
                    extension = ".png"
                name = self._candidate_filename(run, candidate, extension)
                name = self._unique_archive_name(name, used)
                used.add(name)
                bundle.write(source, arcname=name)
        if not used:
            raise RepositoryError("No successful candidates are available to download")
        filename = f"dinkly-{self._story_slug(run)}-candidates.zip"
        target = self._unique_export_path(run, filename)
        self.repository.atomic_write_bytes(target, archive.getvalue(), create_backup=False)
        return ExportArtifact(target, "application/zip", target.name)

    def qa_report(self, run: dict[str, Any]) -> ExportArtifact:
        self._require_approved(run)
        payload = {
            "run_id": run["id"],
            "concept": run.get("concept_text"),
            "generated_at": datetime.now(UTC).isoformat(),
            "candidates": [
                {
                    "candidate": candidate.get("label"),
                    "model": candidate.get("model_display_name"),
                    "power_label": candidate.get("model_power_label"),
                    "qa_status": candidate.get("qa_status"),
                    "qa_summary": candidate.get("qa_summary"),
                    "qa_findings": candidate.get("qa_findings", []),
                    "repair_parent_id": candidate.get("repair_parent_id"),
                    "repair_number": candidate.get("repair_number"),
                }
                for candidate in run.get("candidates", [])
            ],
        }
        return self._json_artifact(run, f"dinkly-{self._story_slug(run)}-qa-report.json", payload)

    def summary(self, run: dict[str, Any]) -> ExportArtifact:
        self._require_approved(run)
        selected = self._selected_candidate(run)
        model = self._public_model(selected.get("model") or run.get("selected_model"))
        payload = {
            "status": "APPROVED",
            "run_id": run["id"],
            "concept": run.get("concept_text"),
            "story_brief": run.get("story_brief"),
            "prompt_id": run.get("prompt_id"),
            "model": model,
            "candidate_count": len([item for item in run.get("candidates", []) if item.get("image_path")]),
            "automatic_checks": sum(len(item.get("qa_findings", [])) for item in run.get("candidates", [])),
            "repair_count": len([item for item in run.get("candidates", []) if item.get("repair_parent_id")]),
            "human_decisions": 1,
            "runtime_ms": run.get("runtime_ms"),
            "estimated_cost": run.get("estimated_cost"),
            "reported_cost": run.get("reported_cost"),
            "approved_at": run.get("approved_at"),
            "selected_candidate_id": run.get("selected_candidate_id"),
            "reference_versions": {
                "dinko": run.get("dinko_reference_version"),
                "dinka": run.get("dinka_reference_version"),
            },
        }
        return self._json_artifact(run, f"dinkly-{self._story_slug(run)}-generation-summary.json", payload)

    def all_comics(self, run: dict[str, Any]) -> ExportArtifact:
        self._require_approved(run)
        comic_paths = self._comic_paths(run)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            if comic_paths:
                for index, source in enumerate(comic_paths, start=1):
                    extension = source.suffix.lower()
                    if extension == ".webp":
                        converted = self._unique_export_path(run, f".comic-{index:02d}-normalized.png")
                        self._convert_or_copy(source, converted, "png")
                        source = converted
                        extension = ".png"
                    bundle.write(source, arcname=f"dinkly-{self._story_slug(run)}-comic-{index:02d}{extension}")
            else:
                source = self._final_source(run)
                extension = source.suffix.lower()
                bundle.write(source, arcname=f"dinkly-{self._story_slug(run)}-five-comic-story{extension}")
        target = self._unique_export_path(run, f"dinkly-{self._story_slug(run)}-comics.zip")
        self.repository.atomic_write_bytes(target, archive.getvalue(), create_backup=False)
        return ExportArtifact(target, "application/zip", target.name)

    def comic_count(self, run: dict[str, Any]) -> int:
        return len(self._comic_paths(run))

    def _json_artifact(self, run: dict[str, Any], filename: str, payload: dict[str, Any]) -> ExportArtifact:
        target = self._unique_export_path(run, filename)
        content = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()
        self.repository.atomic_write_bytes(target, content, create_backup=False)
        return ExportArtifact(target, "application/json", target.name)

    def _final_source(self, run: dict[str, Any], *, comic_number: int | None = None) -> Path:
        if comic_number is not None:
            comics = self._comic_paths(run)
            if comic_number < 1 or comic_number > len(comics):
                raise RepositoryError("The requested individual comic asset is unavailable")
            return comics[comic_number - 1]
        relative = run.get("final_image_path")
        if not relative:
            raise RepositoryError("The approved final image is unavailable")
        return self._asset_path(run, relative)

    def _comic_paths(self, run: dict[str, Any]) -> list[Path]:
        relative_paths = run.get("comic_asset_paths") or self._selected_candidate(run).get("comic_asset_paths") or []
        if not isinstance(relative_paths, list):
            return []
        return [self._asset_path(run, str(relative)) for relative in relative_paths]

    def _selected_candidate(self, run: dict[str, Any]) -> dict[str, Any]:
        selected_id = run.get("selected_candidate_id")
        return next((item for item in run.get("candidates", []) if item.get("id") == selected_id), {})

    def _asset_path(self, run: dict[str, Any], relative: str) -> Path:
        source = self.repository.path(relative)
        run_dir = self._run_dir(run)
        try:
            source.resolve().relative_to(run_dir.resolve())
        except ValueError as exc:
            raise RepositoryError("Download asset path is outside the generation run") from exc
        if not source.is_file():
            raise RepositoryError("Download asset is missing")
        return source

    def _run_dir(self, run: dict[str, Any]) -> Path:
        run_id = str(run.get("id", ""))
        if not re.fullmatch(r"generation-[a-f0-9]{12}", run_id):
            raise RepositoryError("Invalid generation run ID")
        return self.repository.settings.generation_engine_dir / "runs" / run_id

    def _unique_export_path(self, run: dict[str, Any], filename: str) -> Path:
        safe_name = self._safe_filename(filename)
        export_dir = self._run_dir(run) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        candidate = export_dir / safe_name
        index = 2
        while candidate.exists():
            candidate = export_dir / f"{Path(safe_name).stem}-{index}{Path(safe_name).suffix}"
            index += 1
        return candidate

    def _candidate_filename(self, run: dict[str, Any], candidate: dict[str, Any], extension: str) -> str:
        label = str(candidate.get("label") or candidate.get("generation_index", "candidate"))
        base_label = label.split("·", 1)[0].strip().lower()
        name = f"dinkly-{self._story_slug(run)}-candidate-{self._slug(base_label)}"
        if candidate.get("repair_parent_id"):
            name += f"-repair-{int(candidate.get('repair_number') or 1)}"
        elif candidate.get("retry_parent_id"):
            name += "-retry"
        return f"{name}{extension}"

    def _public_model(self, key: str | None) -> dict[str, Any] | None:
        if not key:
            return None
        model = self.registry.get(key)
        return {
            "id": model["id"],
            "display_name": model["display_name"],
            "power_label": model["power_label"],
            "power_level": model["power_level"],
        }

    @staticmethod
    def _require_approved(run: dict[str, Any]) -> None:
        if run.get("status") != "approved":
            raise RepositoryError("Downloads become available after human approval")

    def _story_slug(self, run: dict[str, Any]) -> str:
        brief = run.get("story_brief") or {}
        source = brief.get("title_right") or brief.get("story_title") or run.get("concept_text") or "comic"
        return self._slug(str(source)) or "comic"

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")[:80]

    @classmethod
    def _safe_filename(cls, value: str) -> str:
        path = Path(value)
        stem = cls._slug(path.stem) or "dinkly-export"
        extension = re.sub(r"[^a-z0-9.]", "", path.suffix.lower())
        if extension not in {".png", ".jpg", ".jpeg", ".zip", ".json"}:
            raise RepositoryError("Unsupported export filename")
        return f"{stem}{extension}"

    @staticmethod
    def _unique_archive_name(name: str, used: set[str]) -> str:
        if name not in used:
            return name
        path = Path(name)
        index = 2
        candidate = f"{path.stem}-{index}{path.suffix}"
        while candidate in used:
            index += 1
            candidate = f"{path.stem}-{index}{path.suffix}"
        return candidate

    @staticmethod
    def _date_stamp(run: dict[str, Any]) -> str:
        value = str(run.get("approved_at") or run.get("started_at") or "")
        return value[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value[:10]) else datetime.now(UTC).date().isoformat()

    @staticmethod
    def _convert_or_copy(source: Path, target: Path, output_format: str) -> None:
        source_format = "jpg" if source.suffix.lower() in {".jpg", ".jpeg"} else source.suffix.lower().lstrip(".")
        if source_format == output_format:
            shutil.copy2(source, target)
            return
        try:
            from PIL import Image

            with Image.open(source) as image:
                if output_format == "jpg":
                    background = Image.new("RGB", image.size, "white")
                    if image.mode in {"RGBA", "LA"}:
                        background.paste(image, mask=image.getchannel("A"))
                    else:
                        background.paste(image.convert("RGB"))
                    background.save(target, format="JPEG", quality=95, subsampling=0, optimize=True)
                else:
                    image.save(target, format="PNG", optimize=True)
            return
        except ImportError:
            converter = Path("/usr/bin/sips")
            if not converter.is_file():
                raise RepositoryError("Image conversion requires Pillow") from None
            completed = subprocess.run(
                [str(converter), "-s", "format", "jpeg" if output_format == "jpg" else "png", str(source), "--out", str(target)],
                capture_output=True,
                check=False,
                text=True,
            )
            if completed.returncode != 0 or not target.is_file():
                raise RepositoryError("Image conversion failed") from None
