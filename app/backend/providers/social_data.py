from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from statistics import median
from typing import Any
from urllib.parse import quote

import httpx

from app.backend.services.handle_utils import normalize_handle


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        self.retry_after = retry_after


class SocialDataProvider(ABC):
    name: str
    platform: str

    @abstractmethod
    def validate_credentials(self) -> dict: ...

    @abstractmethod
    def validate_handle(self, handle: str) -> dict: ...

    @abstractmethod
    def estimate_run_cost(self, handles: int, posts_per_handle: int, usage_history: list[dict]) -> dict: ...

    @abstractmethod
    def fetch_profile(self, handle: str) -> dict: ...

    @abstractmethod
    def fetch_recent_posts(self, handle: str, limit: int) -> list[dict]: ...

    @abstractmethod
    def fetch_post_details(self, post_id: str) -> dict: ...

    @abstractmethod
    def normalize_profile(self, raw: dict, handle: str) -> dict: ...

    @abstractmethod
    def normalize_post(self, raw: dict, handle: str) -> dict: ...

    @abstractmethod
    def get_usage(self) -> dict: ...

    @abstractmethod
    def get_provider_status(self) -> dict: ...

    @abstractmethod
    def cancel_active_request(self) -> bool: ...

    @abstractmethod
    def health_check(self) -> dict: ...


class NotConfiguredProvider(SocialDataProvider):
    name = "not-configured"
    platform = "unknown"

    def __init__(self, name: str, platform: str, instructions: str) -> None:
        self.name = name
        self.platform = platform
        self.instructions = instructions

    def _state(self) -> dict:
        return {
            "provider": self.name,
            "platform": self.platform,
            "state": "NotConfigured",
            "configured": False,
            "message": self.instructions,
        }

    def validate_credentials(self) -> dict:
        return self._state()

    def validate_handle(self, handle: str) -> dict:
        try:
            username = normalize_handle(handle)
        except ValueError as exc:
            return {**self._state(), "valid": False, "message": str(exc)}
        return {**self._state(), "valid": True, "username": username}

    def estimate_run_cost(self, handles: int, posts_per_handle: int, usage_history: list[dict]) -> dict:
        return {
            "estimated_cost_low": None,
            "estimated_cost_high": None,
            "currency": "USD",
            "source": "unknown",
            "requires_confirmation": True,
            "message": self.instructions,
        }

    def fetch_profile(self, handle: str) -> dict:
        raise ProviderError("not_configured", self.instructions)

    def fetch_recent_posts(self, handle: str, limit: int) -> list[dict]:
        raise ProviderError("not_configured", self.instructions)

    def fetch_post_details(self, post_id: str) -> dict:
        raise ProviderError("not_configured", self.instructions)

    def normalize_profile(self, raw: dict, handle: str) -> dict:
        return {}

    def normalize_post(self, raw: dict, handle: str) -> dict:
        return {}

    def get_usage(self) -> dict:
        return {"actual_cost": None, "usage_source": "unknown"}

    def get_provider_status(self) -> dict:
        return self._state()

    def cancel_active_request(self) -> bool:
        return False

    def health_check(self) -> dict:
        return self._state()


class ApifyProvider(SocialDataProvider):
    name = "apify"
    base_url = "https://api.apify.com/v2"

    def __init__(
        self,
        token: str,
        actor_id: str,
        platform: str,
        *,
        connection_timeout: float = 10.0,
        read_timeout: float = 30.0,
        download_timeout: float = 20.0,
        actor_timeout: float = 180.0,
        max_retries: int = 2,
        request_guard: Callable[[str], None] | None = None,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self.token = token.strip()
        self.actor_id = actor_id.strip()
        self.platform = platform
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.download_timeout = download_timeout
        self.actor_timeout = actor_timeout
        self.max_retries = max_retries
        self.request_guard = request_guard
        self.client_factory = client_factory
        self.active_run_id: str | None = None
        self._last_usage: dict[str, Any] = {"actual_cost": None, "usage_source": "unknown"}
        self._post_cache: dict[str, dict] = {}

    def validate_credentials(self) -> dict:
        missing = self._missing_configuration()
        if missing:
            return missing
        try:
            response = self._request("GET", "/users/me", phase="credential validation")
            payload = response.json().get("data", {})
            return {
                "provider": self.name,
                "platform": self.platform,
                "state": "Configured",
                "configured": True,
                "connected": True,
                "username": payload.get("username"),
                "message": "Apify connection succeeded.",
            }
        except ProviderError as exc:
            return {
                "provider": self.name,
                "platform": self.platform,
                "state": self._state_for_error(exc.code),
                "configured": True,
                "connected": False,
                "error_code": exc.code,
                "message": exc.safe_message,
            }

    def validate_handle(self, handle: str) -> dict:
        try:
            username = normalize_handle(handle)
        except ValueError as exc:
            return {"valid": False, "message": str(exc), "platform": self.platform}
        return {
            "valid": True,
            "username": username,
            "canonical_url": self._profile_url(username),
            "platform": self.platform,
            "validation": "format",
            "message": "Handle format is valid. Profile existence is confirmed during refresh.",
        }

    def estimate_run_cost(self, handles: int, posts_per_handle: int, usage_history: list[dict]) -> dict:
        comparable: list[float] = []
        for item in usage_history:
            if item.get("provider") != "apify" or item.get("platform") != self.platform:
                continue
            cost = item.get("actual_cost")
            processed = item.get("handles_processed") or 0
            if isinstance(cost, (int, float)) and processed > 0:
                comparable.append(float(cost) / int(processed))
        if comparable:
            per_handle = median(comparable)
            low = max(0.0, per_handle * handles * 0.8)
            high = per_handle * handles * 1.25
            source = "historical provider-reported usage"
            unknown = False
        else:
            # A conservative local range, not a pricing claim. First runs always require confirmation.
            scale = max(1.0, posts_per_handle / 20)
            low = 0.05 * handles * scale
            high = 0.18 * handles * scale
            source = "conservative local estimate; Actor pricing not yet observed"
            unknown = True
        return {
            "estimated_cost_low": round(low, 4),
            "estimated_cost_high": round(high, 4),
            "currency": "USD",
            "source": source,
            "requires_confirmation": unknown,
            "actor_never_run": unknown,
            "expected_provider_runs": handles,
            "label": "Estimated provider cost",
        }

    def fetch_profile(self, handle: str) -> dict:
        posts = self.fetch_recent_posts(handle, 1)
        source = posts[0].get("raw_metadata", {}) if posts else {}
        return self.normalize_profile(source, handle)

    def fetch_recent_posts(self, handle: str, limit: int) -> list[dict]:
        missing = self._missing_configuration()
        if missing:
            raise ProviderError("not_configured", missing["message"])
        username = normalize_handle(handle)
        run = self._start_run(username, limit)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ProviderError("schema_incompatible", "Apify completed without a readable dataset identifier.")
        response = self._request(
            "GET",
            f"/datasets/{quote(str(dataset_id), safe='')}/items",
            phase="dataset download",
            request_timeout=self.download_timeout,
            params={"clean": "true", "format": "json", "limit": str(limit)},
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise ProviderError("schema_incompatible", "The configured Actor returned an incompatible dataset schema.")
        normalized: list[dict] = []
        for item in payload[:limit]:
            if not isinstance(item, dict):
                continue
            post = self.normalize_post(item, username)
            if post.get("platform_post_id"):
                self._post_cache[str(post["platform_post_id"])] = post
                normalized.append(post)
        return normalized

    def fetch_post_details(self, post_id: str) -> dict:
        if post_id in self._post_cache:
            return self._post_cache[post_id]
        raise ProviderError("not_collected", "This post is not available in the current provider result cache.")

    def normalize_profile(self, raw: dict, handle: str) -> dict:
        owner = raw.get("owner") or raw.get("authorMeta") or raw.get("author") or raw.get("user") or {}
        if not isinstance(owner, dict):
            owner = {}
        return {
            "platform_profile_id": self._first(owner, "id", "pk", "userId", "secUid"),
            "username": self._first(owner, "username", "uniqueId") or normalize_handle(handle),
            "display_name": self._first(owner, "fullName", "name", "nickname"),
            "bio": self._first(owner, "biography", "signature", "bio"),
            "profile_image_url": self._first(owner, "profilePicUrl", "avatar", "avatarThumb"),
            "followers": self._integer(owner, "followersCount", "fans", "followerCount", "followers"),
            "following": self._integer(owner, "followsCount", "following", "followingCount"),
            "post_count": self._integer(owner, "postsCount", "videoCount", "postCount"),
            "verified": bool(self._first(owner, "verified", "isVerified") or False),
            "profile_url": self._profile_url(normalize_handle(handle)),
        }

    def normalize_post(self, raw: dict, handle: str) -> dict:
        post_id = self._first(raw, "id", "shortCode", "shortcode", "videoId", "aweme_id")
        caption = self._first(raw, "caption", "text", "description", "desc")
        hashtags = raw.get("hashtags") or []
        if isinstance(hashtags, list):
            hashtags = [str(item.get("name") if isinstance(item, dict) else item).lstrip("#") for item in hashtags]
        else:
            hashtags = []
        timestamp = self._first(raw, "timestamp", "takenAt", "createTimeISO", "createTime", "date")
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp, UTC).isoformat()
        profile = self.normalize_profile(raw, handle)
        return {
            "platform": self.platform,
            "platform_post_id": str(post_id) if post_id is not None else "",
            "post_url": self._first(raw, "url", "webVideoUrl", "postUrl", "displayUrl"),
            "caption": str(caption) if caption is not None else None,
            "hashtags": hashtags,
            "posted_at": str(timestamp) if timestamp is not None else None,
            "media_type": self._first(raw, "type", "mediaType", "format") or "unknown",
            "remote_thumbnail_url": self._first(raw, "displayUrl", "thumbnailUrl", "cover", "videoMeta.coverUrl"),
            "media_url": self._first(raw, "videoUrl", "videoMeta.downloadAddr", "displayUrl"),
            "carousel_item_count": self._carousel_count(raw),
            "duration_seconds": self._number(raw, "duration", "videoDuration"),
            "view_count": self._integer(raw, "videoViewCount", "playCount", "views", "viewCount"),
            "like_count": self._integer(raw, "likesCount", "diggCount", "likes", "likeCount"),
            "comment_count": self._integer(raw, "commentsCount", "commentCount", "comments"),
            "share_count": self._integer(raw, "sharesCount", "shareCount", "shares"),
            "audio_name": self._first(raw, "musicInfo.musicName", "musicMeta.musicName", "audioName"),
            "follower_count": profile.get("followers"),
            "profile": profile,
            "raw_metadata": {"provider_item_keys": sorted(raw.keys()), "provider": "apify"},
        }

    def get_usage(self) -> dict:
        return dict(self._last_usage)

    def get_provider_status(self) -> dict:
        missing = self._missing_configuration()
        return missing or {
            "provider": self.name,
            "platform": self.platform,
            "state": "Configured",
            "configured": True,
            "actor_id": self.actor_id,
        }

    def cancel_active_request(self) -> bool:
        if not self.active_run_id:
            return False
        try:
            self._request("POST", f"/actor-runs/{quote(self.active_run_id, safe='')}/abort", phase="cancellation")
            return True
        except ProviderError:
            return False

    def health_check(self) -> dict:
        return self.validate_credentials()

    def _start_run(self, username: str, limit: int) -> dict:
        payload = self._actor_input(username, limit)
        actor = quote(self.actor_id, safe="~")
        response = self._request("POST", f"/acts/{actor}/runs", phase="Actor start", json=payload)
        run = response.json().get("data", {})
        run_id = run.get("id")
        if not run_id:
            raise ProviderError("schema_incompatible", "Apify did not return an Actor run identifier.")
        self.active_run_id = str(run_id)
        deadline = time.monotonic() + self.actor_timeout
        terminal = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
        while run.get("status") not in terminal:
            if time.monotonic() >= deadline:
                self.cancel_active_request()
                raise ProviderError("timeout", "The Apify Actor run exceeded the configured timeout.")
            time.sleep(1)
            poll = self._request("GET", f"/actor-runs/{quote(str(run_id), safe='')}", phase="Actor status")
            run = poll.json().get("data", {})
        self.active_run_id = None
        if run.get("status") != "SUCCEEDED":
            status = str(run.get("status") or "unknown")
            raise ProviderError("provider_unavailable", f"The Apify Actor finished with status {status}.")
        actual_cost = run.get("usageTotalUsd")
        self._last_usage = {
            "actual_cost": float(actual_cost) if isinstance(actual_cost, (int, float)) else None,
            "currency": "USD",
            "compute_units": (run.get("usage") or {}).get("ACTOR_COMPUTE_UNITS") if isinstance(run.get("usage"), dict) else None,
            "usage_source": "provider_reported" if isinstance(actual_cost, (int, float)) else "estimated",
            "provider_run_id": run_id,
            "dataset_id": run.get("defaultDatasetId"),
        }
        return run

    def _request(self, method: str, path: str, *, phase: str, **kwargs) -> httpx.Response:
        if self.request_guard:
            self.request_guard(phase)
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        request_timeout = float(kwargs.pop("request_timeout", self.read_timeout))
        timeout = httpx.Timeout(request_timeout, connect=self.connection_timeout)
        attempts = 0
        while True:
            cause: Exception | None = None
            try:
                with self.client_factory(timeout=timeout, headers=headers) as client:
                    response = client.request(method, f"{self.base_url}{path}", **kwargs)
            except (httpx.ConnectError, httpx.NetworkError) as exc:
                cause = exc
                error = ProviderError("provider_unavailable", "The provider could not be reached from this machine.", retryable=True)
            except httpx.TimeoutException as exc:
                cause = exc
                error = ProviderError("timeout", "The provider request timed out.", retryable=True)
            else:
                if response.is_success:
                    return response
                error = self._response_error(response)
            if not error.retryable or attempts >= self.max_retries:
                if cause:
                    raise error from cause
                raise error
            attempts += 1
            if self.request_guard:
                self.request_guard(f"retry {attempts}")
            delay = error.retry_after if error.retry_after is not None else min(8.0, 2 ** (attempts - 1) + random.random())
            time.sleep(max(0.0, min(delay, 30.0)))

    def _response_error(self, response: httpx.Response) -> ProviderError:
        text = response.text.lower()[:2000]
        retry_after = response.headers.get("Retry-After")
        retry_value = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else None
        if response.status_code in {402} or any(term in text for term in ("insufficient credit", "spending limit", "billing disabled", "payment required", "subscription inactive", "account suspended")):
            return ProviderError("insufficient_credit", "Apify declined the request because the account has insufficient usage credit. No further provider calls will be attempted.")
        if response.status_code in {401, 403}:
            return ProviderError("authentication", "Apify rejected the configured API token.")
        if response.status_code == 429:
            return ProviderError("rate_limited", "Apify rate limited the request.", retryable=True, retry_after=retry_value)
        if response.status_code == 404:
            return ProviderError("actor_unavailable", "The configured Apify Actor is unavailable. Review the Actor ID in Settings.")
        if response.status_code >= 500:
            return ProviderError("provider_unavailable", "Apify is temporarily unavailable.", retryable=True)
        return ProviderError("provider_error", f"Apify returned HTTP {response.status_code}.")

    def _missing_configuration(self) -> dict | None:
        if not self.token:
            return {
                "provider": self.name,
                "platform": self.platform,
                "state": "NotConfigured",
                "configured": False,
                "message": "Add an Apify API key in Settings or import public post data manually.",
            }
        if not self.actor_id:
            return {
                "provider": self.name,
                "platform": self.platform,
                "state": "NotConfigured",
                "configured": False,
                "message": f"Add an Apify {self.platform.title()} Actor ID in Settings.",
            }
        return None

    def _actor_input(self, username: str, limit: int) -> dict:
        if self.platform == "instagram":
            return {"directUrls": [self._profile_url(username)], "resultsType": "posts", "resultsLimit": limit}
        return {
            "profiles": [username],
            "resultsPerPage": limit,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
        }

    def _profile_url(self, username: str) -> str:
        domain = "instagram.com" if self.platform == "instagram" else "tiktok.com/@"
        return f"https://www.{domain}{username if self.platform == 'tiktok' else '/' + username + '/'}"

    @staticmethod
    def _state_for_error(code: str) -> str:
        return {
            "authentication": "Connection failed",
            "insufficient_credit": "Budget paused",
            "rate_limited": "Rate limited",
            "provider_unavailable": "Provider unavailable",
            "actor_unavailable": "Provider unavailable",
        }.get(code, "Connection failed")

    @staticmethod
    def _first(data: dict, *keys: str) -> Any:
        for key in keys:
            value: Any = data
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    value = None
                    break
                value = value[part]
            if value not in (None, ""):
                return value
        return None

    @classmethod
    def _integer(cls, data: dict, *keys: str) -> int | None:
        value = cls._first(data, *keys)
        if value is None:
            return None
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _number(cls, data: dict, *keys: str) -> float | None:
        value = cls._first(data, *keys)
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _carousel_count(data: dict) -> int | None:
        for key in ("childPosts", "images", "carouselMedia", "imagePost.images"):
            value: Any = data
            for part in key.split("."):
                if not isinstance(value, dict):
                    value = None
                    break
                value = value.get(part)
            if isinstance(value, list):
                return len(value)
        return None


class ApifyInstagramProvider(ApifyProvider):
    def __init__(self, token: str, actor_id: str, **kwargs) -> None:
        super().__init__(token, actor_id, "instagram", **kwargs)


class ApifyTikTokProvider(ApifyProvider):
    def __init__(self, token: str, actor_id: str, **kwargs) -> None:
        super().__init__(token, actor_id, "tiktok", **kwargs)


class ManualImportProvider(NotConfiguredProvider):
    def __init__(self, platform: str = "manual") -> None:
        super().__init__("manual-import", platform, "Import a CSV or JSON file containing public post data.")

    def get_provider_status(self) -> dict:
        return {
            "provider": self.name,
            "platform": self.platform,
            "state": "Available",
            "configured": True,
            "message": "Manual CSV, JSON, and post entry are available without an API key.",
        }


class OfficialInstagramProvider(NotConfiguredProvider):
    def __init__(self) -> None:
        super().__init__("official-instagram", "instagram", "Official Instagram provider is scaffolded but not configured.")


class OfficialTikTokProvider(NotConfiguredProvider):
    def __init__(self) -> None:
        super().__init__("official-tiktok", "tiktok", "Official TikTok provider is scaffolded but not configured.")


class BrightDataProvider(NotConfiguredProvider):
    def __init__(self, platform: str = "unknown") -> None:
        super().__init__("bright-data", platform, "Bright Data provider is scaffolded but not configured.")


class CustomProvider(NotConfiguredProvider):
    def __init__(self, platform: str = "unknown") -> None:
        super().__init__("custom", platform, "Custom provider is scaffolded but not configured.")
