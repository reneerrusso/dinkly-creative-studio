from __future__ import annotations

import re
from urllib.parse import urlparse

from app.backend.services.repository_service import RepositoryError

HANDLE_PATTERN = re.compile(r"^[a-zA-Z0-9._]{1,80}$")


def normalize_handle(value: str) -> str:
    candidate = value.strip()
    if "://" in candidate:
        parsed = urlparse(candidate)
        pieces = [piece for piece in parsed.path.split("/") if piece]
        if not pieces:
            raise ValueError("Profile URL does not contain a username")
        candidate = pieces[0]
    candidate = candidate.strip().lstrip("@").strip().lower()
    if not HANDLE_PATTERN.fullmatch(candidate):
        raise ValueError("Use a public username containing only letters, numbers, periods, or underscores")
    return candidate


def parse_bulk_handles(text: str, default_platform: str | None = None) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in text.replace(";", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        platform = default_platform
        value = line
        if "," in line:
            first, rest = line.split(",", 1)
            if first.strip().lower() == "platform" and rest.split(",", 1)[0].strip().lower() in {"handle", "username", "account"}:
                continue
            if first.strip().lower() in {"instagram", "tiktok"}:
                platform, value = first.strip().lower(), rest.split(",", 1)[0].strip()
        if "instagram.com" in value.lower():
            platform = "instagram"
        if "tiktok.com" in value.lower():
            platform = "tiktok"
        if platform not in {"instagram", "tiktok"}:
            raise RepositoryError(f"Choose Instagram or TikTok for {line}")
        try:
            username = normalize_handle(value)
        except ValueError as exc:
            raise RepositoryError(f"Invalid handle {line}: {exc}") from exc
        key = (platform, username)
        if key not in seen:
            seen.add(key)
            records.append({"platform": platform, "username": username})
    return records
