from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.backend.config import DEFAULT_INSTAGRAM_ACTOR_ID, DEFAULT_TIKTOK_ACTOR_ID
from app.backend.services.repository_service import RepositoryError, RepositoryService

REGISTRY_PATH = "data/social_provider_actors.json"
SCHEMA_PATH = "schemas/social_provider_actor.schema.json"
DEFAULT_IDS = {"instagram": DEFAULT_INSTAGRAM_ACTOR_ID, "tiktok": DEFAULT_TIKTOK_ACTOR_ID}


class ActorRegistry:
    """Single source of truth for platform Actors, overrides, and health."""

    def __init__(self, repository: RepositoryService, client_factory: Callable[..., httpx.Client] = httpx.Client) -> None:
        self.repository = repository
        self.client_factory = client_factory

    def records(self) -> list[dict[str, Any]]:
        records = self.repository.read_json(REGISTRY_PATH, [])
        self.repository.validate_records(records, SCHEMA_PATH)
        return records

    def get_default(self, platform: str) -> dict[str, Any]:
        expected = DEFAULT_IDS.get(platform)
        record = next((item for item in self.records() if item["platform"] == platform and item["is_default"]), None)
        if not record or record["actor_id"] != expected:
            raise RepositoryError(f"No valid recommended {platform.title()} Actor is registered")
        return record

    def get_effective(self, platform: str, override: str = "") -> dict[str, Any]:
        default = self.get_default(platform)
        clean = override.strip()
        return {**default, "actor_id": clean or default["actor_id"], "source": "override" if clean else "recommended"}

    def set_enabled(self, instagram: bool, tiktok: bool) -> None:
        records = self.records()
        for record in records:
            if record["is_default"]:
                record["enabled"] = instagram if record["platform"] == "instagram" else tiktok
        self.repository.write_json(REGISTRY_PATH, records, schema_relative=SCHEMA_PATH, validate_each=True)

    def platform_status(self, platform: str, override: str = "") -> dict[str, Any]:
        record = self.get_effective(platform, override)
        return {
            "platform": platform,
            "enabled": record["enabled"],
            "source": record["source"],
            "actor_override": override,
            "last_verified_at": record["last_verified_at"],
            "verification_status": record["verification_status"],
            "actor_name": record["actor_name"],
            "actor_owner": record["actor_owner"],
            "pricing_summary": record["pricing_summary"],
        }

    def verify(self, platform: str, token: str, override: str = "") -> dict[str, Any]:
        if not token.strip():
            return {**self.platform_status(platform, override), "ready": False, "status": "Not configured", "message": "Add an Apify API key."}
        effective = self.get_effective(platform, override)
        actor_id = effective["actor_id"]
        try:
            with self.client_factory(timeout=10.0, headers={"Authorization": f"Bearer {token}"}) as client:
                response = client.get(f"https://api.apify.com/v2/acts/{quote(actor_id, safe='~')}")
            if response.status_code in {401, 403}:
                status, message = "Unavailable", "The API key cannot access this Actor."
            elif response.status_code == 404:
                status, message = "Unavailable", "This Actor no longer exists or is unavailable."
            elif response.is_error:
                status, message = "Unavailable", "Actor health could not be verified."
            else:
                status, message = "Ready", "Actor metadata and token access verified."
                if effective["source"] == "recommended":
                    self._record_verification(platform, "runtime_verified")
            return {**self.platform_status(platform, override), "ready": status == "Ready", "status": status, "message": message}
        except (httpx.TimeoutException, httpx.NetworkError):
            return {**self.platform_status(platform, override), "ready": False, "status": "Unavailable", "message": "Actor health check could not reach Apify."}

    def validate_override(self, platform: str, token: str, override: str) -> dict[str, Any]:
        if not override.strip():
            return self.platform_status(platform)
        result = self.verify(platform, token, override)
        if not result["ready"]:
            raise RepositoryError(f"{platform.title()} Actor override is invalid or unavailable: {result['message']}")
        return result

    def _record_verification(self, platform: str, status: str) -> None:
        records = self.records()
        for record in records:
            if record["platform"] == platform and record["is_default"]:
                record["last_verified_at"] = datetime.now(UTC).isoformat()
                record["verification_status"] = status
        self.repository.write_json(REGISTRY_PATH, records, schema_relative=SCHEMA_PATH, validate_each=True)
