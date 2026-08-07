from __future__ import annotations

import hashlib
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.backend.services.repository_service import RepositoryError


class ObjectStorage(ABC):
    @abstractmethod
    def upload(self, storage_path: str, content: bytes, *, content_type: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def download(self, storage_path: str) -> bytes: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...


class LocalFilesystemObjectStorage(ObjectStorage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_path: str) -> Path:
        candidate = (self.root / storage_path.lstrip("/")).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise RepositoryError("Invalid local object storage path") from exc
        return candidate

    def upload(self, storage_path: str, content: bytes, *, content_type: str | None = None) -> dict[str, Any]:
        destination = self._path(storage_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return {
            "bucket": "local",
            "path": storage_path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "content_type": content_type or mimetypes.guess_type(storage_path)[0] or "application/octet-stream",
        }

    def download(self, storage_path: str) -> bytes:
        path = self._path(storage_path)
        if not path.is_file():
            raise RepositoryError("Local asset not found")
        return path.read_bytes()

    def health(self) -> dict[str, Any]:
        return {"status": "healthy", "provider": "local_filesystem"}
