from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jsonschema import Draft202012Validator

from app.backend.config import Settings, settings

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
DOCUMENTS = {
    "creative-bible": "CREATIVE_BIBLE.md",
    "character-bible": "CHARACTER_BIBLE.md",
    "style-guide": "STYLE_GUIDE.md",
    "viral-framework": "VIRAL_FRAMEWORK.md",
    "social-learning": "SOCIAL_LEARNING.md",
    "nano-banana-rules": "NANO_BANANA_RULES.md",
    "qa-checklist": "QA_CHECKLIST.md",
    "brand-integrations": "BRAND_INTEGRATIONS.md",
    "failures": "FAILURES.md",
    "sprite-studio": "docs/SPRITE_STUDIO.md",
    "sprite-character-rules": "docs/SPRITE_CHARACTER_RULES.md",
    "sprite-animation-guide": "docs/SPRITE_ANIMATION_GUIDE.md",
    "sprite-export-guide": "docs/SPRITE_EXPORT_GUIDE.md",
    "readme": "README.md",
}


class RepositoryError(ValueError):
    pass


class RepositoryService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.root = app_settings.repository_root
        self.settings.ensure_directories()

    def path(self, relative: str | Path) -> Path:
        try:
            path = self.settings.safe_path(relative)
            relative_value = Path(relative).as_posix()
            if (
                self.settings.app_mode == "cloud"
                and not path.exists()
                and relative_value.startswith("app-data/")
                and path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
            ):
                from app.backend.services.cloud_persistence import cloud_storage

                with suppress(RepositoryError):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(cloud_storage(self.settings).download(relative_value))
            return path
        except ValueError as exc:
            raise RepositoryError(str(exc)) from exc

    def relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError as exc:
            raise RepositoryError("Path is outside the repository") from exc

    def read_json(self, relative: str, default: Any | None = None) -> Any:
        fallback = [] if default is None else default
        if self.settings.app_mode == "cloud" and self._cloud_json(relative):
            from app.backend.services.cloud_persistence import cloud_documents

            documents = cloud_documents(self.settings)
            if documents.exists(relative):
                return documents.read(relative, fallback)
            seed = self._read_local_json(relative, fallback)
            documents.write(relative, seed)
            return seed
        return self._read_local_json(relative, fallback)

    def _read_local_json(self, relative: str, default: Any) -> Any:
        path = self.path(relative)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RepositoryError(f"Invalid JSON in {relative}: {exc}") from exc

    def validate_json(self, payload: Any, schema_relative: str) -> None:
        schema = self.read_json(schema_relative)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
        if errors:
            detail = "; ".join(error.message for error in errors[:4])
            raise RepositoryError(f"Schema validation failed: {detail}")

    def validate_records(self, records: list[dict[str, Any]], schema_relative: str) -> None:
        for index, record in enumerate(records):
            try:
                self.validate_json(record, schema_relative)
            except RepositoryError as exc:
                raise RepositoryError(f"Record {index + 1}: {exc}") from exc

    def backup(self, path: Path) -> str | None:
        if not path.exists():
            return None
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        relative = self.relative(path).replace("/", "__")
        backup_path = self.settings.backups_dir / f"{timestamp}__{relative}.bak"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        return self.relative(backup_path)

    def atomic_write_bytes(self, path: Path, content: bytes, *, create_backup: bool = True) -> str | None:
        path = self.path(self.relative(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = self.backup(path) if create_backup else None
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise
        if self.settings.app_mode == "cloud":
            relative = self.relative(path)
            if relative.startswith("app-data/") and path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                from app.backend.services.cloud_persistence import cloud_database, cloud_storage

                stored = cloud_storage(self.settings).upload(relative, content)
                cloud_database(self.settings).upsert(
                    "assets",
                    {
                        "id": f"asset-{hashlib.sha256(relative.encode()).hexdigest()[:16]}",
                        "asset_type": self._asset_type(relative),
                        "storage_bucket": stored["bucket"],
                        "storage_path": stored["path"],
                        "content_type": stored["content_type"],
                        "sha256": stored["sha256"],
                        "size_bytes": stored["size_bytes"],
                        "metadata_json": {"source_path": relative},
                    },
                )
        return backup_path

    def write_json(
        self,
        relative: str,
        payload: Any,
        *,
        schema_relative: str | None = None,
        validate_each: bool = False,
        create_backup: bool = True,
    ) -> str | None:
        if schema_relative:
            if validate_each:
                if not isinstance(payload, list):
                    raise RepositoryError("Expected a JSON array")
                self.validate_records(payload, schema_relative)
            else:
                self.validate_json(payload, schema_relative)
        if self.settings.app_mode == "cloud" and self._cloud_json(relative):
            from app.backend.services.cloud_persistence import cloud_documents

            cloud_documents(self.settings).write(relative, payload)
            return None
        encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()
        return self.atomic_write_bytes(self.path(relative), encoded, create_backup=create_backup)

    def json_exists(self, relative: str) -> bool:
        if self.settings.app_mode == "cloud" and self._cloud_json(relative):
            from app.backend.services.cloud_persistence import cloud_documents

            return cloud_documents(self.settings).exists(relative)
        return self.path(relative).is_file()

    def list_json(self, prefix: str, *, suffix: str | None = None) -> list[str]:
        if self.settings.app_mode == "cloud":
            from app.backend.services.cloud_persistence import cloud_documents

            return cloud_documents(self.settings).keys(prefix, suffix=suffix)
        root = self.path(prefix)
        candidates = [root] if root.is_file() else sorted(root.rglob("*.json")) if root.exists() else []
        values = [self.relative(path) for path in candidates]
        return [value for value in values if not suffix or value.endswith(suffix)]

    def asset_url(self, relative: str | Path) -> str:
        value = Path(relative).as_posix().lstrip("/")
        if self.settings.app_mode == "cloud":
            return f"/api/assets/{quote(value, safe='/')}"
        if value.startswith("app-data/generation-engine/"):
            return f"/generation-assets/{value.split('app-data/generation-engine/', 1)[1]}"
        if value.startswith("app-data/sprites/"):
            return f"/sprite-assets/{value.split('app-data/sprites/', 1)[1]}"
        return f"/{value}"

    @staticmethod
    def _cloud_json(relative: str) -> bool:
        value = Path(relative).as_posix()
        return value.endswith(".json") and not value.startswith("schemas/")

    @staticmethod
    def _asset_type(relative: str) -> str:
        if "/candidates/" in relative:
            return "generation_candidate"
        if "final" in Path(relative).stem:
            return "final_composition"
        if relative.startswith("app-data/uploads/"):
            return "upload"
        return "asset"

    def append_unique(
        self,
        relative: str,
        record: dict[str, Any],
        *,
        id_field: str,
        schema_relative: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        records = self.read_json(relative, [])
        if not isinstance(records, list):
            raise RepositoryError(f"{relative} must contain an array")
        record_id = record.get(id_field)
        if not record_id:
            raise RepositoryError(f"{id_field} is required")
        if any(item.get(id_field) == record_id for item in records if isinstance(item, dict)):
            raise RepositoryError(f"Duplicate {id_field}: {record_id}")
        records.append(record)
        backup = self.write_json(relative, records, schema_relative=schema_relative, validate_each=bool(schema_relative))
        return record, backup

    def read_markdown(self, document: str) -> dict[str, Any]:
        relative = DOCUMENTS.get(document)
        if not relative:
            raise RepositoryError("Unknown knowledge document")
        path = self.path(relative)
        content = path.read_text(encoding="utf-8")
        return {
            "slug": document,
            "title": _first_heading(content) or document.replace("-", " ").title(),
            "path": relative,
            "content": content,
            "last_modified": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
            "headings": _headings(content),
        }

    def write_markdown(self, document: str, content: str) -> dict[str, Any]:
        if not content.strip().startswith("#") or len(content.strip()) < 80:
            raise RepositoryError("Markdown must begin with a heading and contain substantive content")
        relative = DOCUMENTS.get(document)
        if not relative:
            raise RepositoryError("Unknown knowledge document")
        backup = self.atomic_write_bytes(self.path(relative), (content.rstrip() + "\n").encode())
        result = self.read_markdown(document)
        result["backup"] = backup
        return result

    def list_documents(self) -> list[dict[str, Any]]:
        return [self.read_markdown(slug) for slug in DOCUMENTS]

    def save_upload(self, original_name: str, content: bytes) -> dict[str, Any]:
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise RepositoryError("Only PNG, JPG, JPEG, and WEBP images are allowed")
        if not content:
            raise RepositoryError("The uploaded image is empty")
        if len(content) > self.settings.max_upload_bytes:
            max_mb = self.settings.max_upload_bytes // (1024 * 1024)
            raise RepositoryError(f"Image exceeds the {max_mb} MB local limit")
        safe_stem = re.sub(r"[^a-z0-9]+", "-", Path(original_name).stem.lower()).strip("-") or "comic"
        filename = f"{safe_stem}-{uuid.uuid4().hex[:10]}{extension}"
        target = self.settings.uploads_dir / filename
        self.atomic_write_bytes(target, content, create_backup=False)
        return {
            "path": self.relative(target),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
            "original_name": original_name,
        }

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if len(needle) < 2:
            return []
        results: list[dict[str, Any]] = []
        json_sources = {
            "concept": "app-data/concepts.json",
            "social post": "data/social_posts.json",
            "learning": "data/social_learnings.json",
            "prompt": "data/approved_prompts.json",
        }
        for kind, relative in json_sources.items():
            payload = self.read_json(relative, [])
            for item in payload if isinstance(payload, list) else []:
                haystack = json.dumps(item, ensure_ascii=False).lower()
                if needle in haystack:
                    title = item.get("title") or item.get("pattern") or item.get("storyline_id") or "Untitled"
                    results.append({"kind": kind, "title": title, "source": relative, "record": item})
        for slug in DOCUMENTS:
            document = self.read_markdown(slug)
            if needle in document["content"].lower():
                results.append(
                    {"kind": "knowledge", "title": document["title"], "source": document["path"], "slug": slug}
                )
        for directory, kind in (("EXAMPLES", "example"),):
            for path in sorted(self.path(directory).glob("*.md")):
                content = path.read_text(encoding="utf-8")
                if needle in content.lower():
                    results.append({"kind": kind, "title": _first_heading(content) or path.stem, "source": self.relative(path)})
        return results[:50]


def _first_heading(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _headings(content: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for line in content.splitlines():
        match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if match:
            title = match.group(2).strip()
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            headings.append({"level": len(match.group(1)), "title": title, "slug": slug})
    return headings
