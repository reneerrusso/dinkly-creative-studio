from __future__ import annotations

import base64
import json
import mimetypes
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


class ImageProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ImageResult:
    content: bytes
    mime_type: str
    runtime_ms: int
    reported_cost: float | None = None
    provider_metadata: dict[str, Any] | None = None


class ImageProvider(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        prompt: str,
        model_key: str,
        reference_paths: list[Path],
        aspect_ratio: str,
        image_size: str | None,
    ) -> ImageResult: ...

    @abstractmethod
    def edit(
        self,
        *,
        prompt: str,
        model_key: str,
        source_path: Path,
        reference_paths: list[Path],
        aspect_ratio: str,
        image_size: str | None,
    ) -> ImageResult: ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...

    @abstractmethod
    def estimate_cost(self, *, model_key: str, image_size: str | None = None) -> float | None: ...

    @abstractmethod
    def get_model_info(self, model_key: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_usage(self) -> dict[str, Any]: ...

    def analyze(self, *, image_path: Path, prompt: str, model_key: str) -> dict[str, Any]:
        raise ImageProviderError("Automated visual QA unavailable", code="qa_unavailable")


class GeminiImageProvider(ImageProvider):
    """Google Gemini REST provider. Secrets remain server-side and are sent only as an API header."""

    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, registry: Any, *, timeout_seconds: float = 120.0) -> None:
        self.api_key = api_key.strip()
        self.registry = registry
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        prompt: str,
        model_key: str,
        reference_paths: list[Path],
        aspect_ratio: str,
        image_size: str | None,
    ) -> ImageResult:
        return self._image_request(
            prompt=prompt,
            model_key=model_key,
            images=reference_paths,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )

    def edit(
        self,
        *,
        prompt: str,
        model_key: str,
        source_path: Path,
        reference_paths: list[Path],
        aspect_ratio: str,
        image_size: str | None,
    ) -> ImageResult:
        return self._image_request(
            prompt=prompt,
            model_key=model_key,
            images=[source_path, *reference_paths],
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )

    def health_check(self) -> dict[str, Any]:
        if not self.api_key:
            return {"status": "Not configured", "connected": False, "error": "GEMINI_API_KEY is missing."}
        model = self.registry.get("nano_banana_2_lite")
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(
                    f"{self.base_url}/models/{model['model_id']}",
                    headers={"x-goog-api-key": self.api_key},
                )
            if response.is_success:
                return {"status": "Connected", "connected": True, "model": model["display_name"], "error": None}
            error = self._provider_error(response)
            return {"status": "Error", "connected": False, "error": str(error)}
        except httpx.HTTPError as exc:
            return {"status": "Error", "connected": False, "error": f"Connection failed: {exc}"}

    def estimate_cost(self, *, model_key: str, image_size: str | None = None) -> float | None:
        model = self.registry.get(model_key)
        estimates = model.get("estimated_output_cost_usd", {})
        normalized = image_size or model.get("default_resolution") or "1K"
        return estimates.get(normalized) or estimates.get("1K")

    def get_model_info(self, model_key: str) -> dict[str, Any]:
        return self.registry.get(model_key)

    def get_usage(self) -> dict[str, Any]:
        return {"source": "local generation records", "reported_usage_available": False}

    def analyze(self, *, image_path: Path, prompt: str, model_key: str) -> dict[str, Any]:
        parts = [self._inline_part(image_path), {"text": prompt}]
        payload = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"responseModalities": ["TEXT"]}}
        started = time.monotonic()
        response = self._post(model_key, payload)
        runtime_ms = int((time.monotonic() - started) * 1000)
        text = "".join(
            str(part.get("text", ""))
            for candidate in response.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
        ).strip()
        if not text:
            raise ImageProviderError("Automated QA returned no analysis.", code="empty_qa")
        cleaned = text.removeprefix("```json").removesuffix("```").strip()
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ImageProviderError("Automated QA returned invalid JSON.", code="invalid_qa") from exc
        if not isinstance(result, dict):
            raise ImageProviderError("Automated QA returned an invalid result.", code="invalid_qa")
        result["runtime_ms"] = runtime_ms
        return result

    def _image_request(
        self,
        *,
        prompt: str,
        model_key: str,
        images: list[Path],
        aspect_ratio: str,
        image_size: str | None,
    ) -> ImageResult:
        model = self.registry.get(model_key)
        parts = [self._inline_part(path) for path in images]
        parts.append({"text": prompt})
        image_config: dict[str, str] = {"aspectRatio": aspect_ratio}
        if image_size and image_size in model["supported_resolutions"]:
            image_config["imageSize"] = image_size
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": image_config},
        }
        started = time.monotonic()
        response = self._post(model_key, payload)
        runtime_ms = int((time.monotonic() - started) * 1000)
        for candidate in response.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return ImageResult(
                        content=base64.b64decode(inline["data"]),
                        mime_type=inline.get("mimeType") or inline.get("mime_type") or "image/png",
                        runtime_ms=runtime_ms,
                        provider_metadata={"usage_metadata": response.get("usageMetadata")},
                    )
        raise ImageProviderError("Gemini returned no image.", code="empty_image", retryable=True)

    def _post(self, model_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ImageProviderError("GEMINI_API_KEY is missing.", code="missing_key")
        model = self.registry.get(model_key)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/models/{model['model_id']}:generateContent",
                    headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ImageProviderError("Gemini timed out.", code="timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ImageProviderError(f"Gemini connection failed: {exc}", code="network", retryable=True) from exc
        if not response.is_success:
            raise self._provider_error(response)
        return response.json()

    @staticmethod
    def _inline_part(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ImageProviderError(f"Reference image is missing: {path.name}", code="missing_reference")
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        return {"inlineData": {"mimeType": mime, "data": base64.b64encode(path.read_bytes()).decode("ascii")}}

    @staticmethod
    def _provider_error(response: httpx.Response) -> ImageProviderError:
        try:
            payload = response.json()
            message = payload.get("error", {}).get("message") or response.text
        except ValueError:
            message = response.text
        lowered = message.lower()
        if response.status_code in {401, 403}:
            return ImageProviderError("Gemini rejected the API key or billing access.", code="invalid_key")
        if response.status_code == 429:
            return ImageProviderError("Gemini rate limit or quota reached.", code="rate_limit", retryable=True)
        if response.status_code == 404:
            return ImageProviderError("The selected Gemini model is unavailable.", code="model_unavailable")
        if "safety" in lowered or "blocked" in lowered:
            return ImageProviderError("Gemini rejected the request under its safety policy.", code="safety")
        return ImageProviderError(f"Gemini request failed: {message[:300]}", code="provider_error", retryable=response.status_code >= 500)
