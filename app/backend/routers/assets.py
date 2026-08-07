from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Response

from app.backend.config import settings
from app.backend.services.cloud_persistence import cloud_storage
from app.backend.services.repository_service import RepositoryError

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{storage_path:path}")
def asset(storage_path: str) -> Response:
    if settings.app_mode != "cloud":
        raise RepositoryError("Cloud asset proxy is only available in cloud mode")
    content = cloud_storage(settings).download(storage_path)
    return Response(
        content=content,
        media_type=mimetypes.guess_type(storage_path)[0] or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=300"},
    )
