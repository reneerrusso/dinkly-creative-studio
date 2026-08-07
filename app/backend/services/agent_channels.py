from __future__ import annotations

import json
import mimetypes
import socket
import ssl
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol

from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.repository_service import RepositoryError
from app.backend.services.tls_service import TlsConfigurationError, create_verified_ssl_context


class SlackTransport(Protocol):
    def call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class SlackWebApiTransport:
    """Small official Slack Web API client; tokens remain backend-only."""

    def __init__(self, bot_token: str, *, timeout: int = 15, ssl_context: ssl.SSLContext | None = None) -> None:
        self.bot_token = bot_token
        self.timeout = timeout
        try:
            self.ssl_context = ssl_context or create_verified_ssl_context()
        except (OSError, ssl.SSLError, TlsConfigurationError) as exc:
            raise RepositoryError(f"Slack TLS configuration error: {exc}") from exc

    def call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"https://slack.com/api/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.bot_token}", "Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RepositoryError(f"Slack API HTTP error: {exc.code}") from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
                message = "Could not verify Slack’s HTTPS certificate from the local Python environment"
            elif isinstance(reason, socket.gaierror):
                message = "Slack API DNS lookup failed"
            elif isinstance(reason, (TimeoutError, socket.timeout)):
                message = "Slack API request timed out"
            else:
                message = f"Slack API unavailable: {type(reason).__name__}"
            raise RepositoryError(message) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise RepositoryError(f"Slack API response failed: {type(exc).__name__}") from exc
        if not result.get("ok"):
            raise RepositoryError(f"Slack API error: {result.get('error', 'unknown_error')}")
        return result

    def upload_file(
        self,
        path: Path,
        *,
        channel_id: str,
        thread_ts: str,
        title: str,
        initial_comment: str | None = None,
    ) -> dict[str, Any]:
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise RepositoryError("Slack image file is unavailable") from exc
        prepared = self.call("files.getUploadURLExternal", {"filename": path.name, "length": len(content)})
        upload_url = str(prepared.get("upload_url") or "")
        file_id = str(prepared.get("file_id") or "")
        if not upload_url or not file_id:
            raise RepositoryError("Slack file upload did not return an upload destination")
        request = urllib.request.Request(
            upload_url,
            data=content,
            headers={"Content-Type": media_type_for(path.name)},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                if response.status >= 300:
                    raise RepositoryError(f"Slack file upload failed with HTTP {response.status}")
        except (urllib.error.URLError, OSError) as exc:
            raise RepositoryError("Slack file upload failed") from exc
        return self.call(
            "files.completeUploadExternal",
            {
                "files": [{"id": file_id, "title": title[:255]}],
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                **({"initial_comment": initial_comment} if initial_comment else {}),
            },
        )


class AgentChannel(ABC):
    @abstractmethod
    def receive_message(
        self,
        thread_id: str,
        message: str,
        *,
        user_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def send_message(self, thread_id: str, message: str, *, channel_id: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def send_status(
        self,
        thread_id: str,
        message: str,
        *,
        channel_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def send_image(
        self,
        thread_id: str,
        image_url: str,
        title: str,
        *,
        channel_id: str | None = None,
        details: str | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def send_buttons(
        self,
        thread_id: str,
        message: str,
        buttons: list[dict[str, str]],
        *,
        channel_id: str | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def update_message(self, message_id: str, message: str, *, channel_id: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def resolve_thread(self, thread_id: str) -> dict[str, Any]: ...


class WebAgentChannel(AgentChannel):
    def __init__(self, tasks: AgentTaskService) -> None:
        self.tasks = tasks

    def _record(self, kind: str, thread_id: str, message: str, **extra: Any) -> dict[str, Any]:
        return self.tasks.record_outbox(
            {"channel": "web", "kind": kind, "thread_id": thread_id, "message": message, **extra}
        )

    def receive_message(
        self,
        thread_id: str,
        message: str,
        *,
        user_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        return self._record("received", thread_id, message, user_id=user_id)

    def send_message(self, thread_id: str, message: str, *, channel_id: str | None = None) -> dict[str, Any]:
        return self._record("message", thread_id, message)

    def send_status(
        self,
        thread_id: str,
        message: str,
        *,
        channel_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        return self._record("status", thread_id, message, replaces=message_id)

    def send_image(
        self,
        thread_id: str,
        image_url: str,
        title: str,
        *,
        channel_id: str | None = None,
        details: str | None = None,
    ) -> dict[str, Any]:
        return self._record("image", thread_id, title, image_url=image_url, details=details)

    def send_buttons(
        self,
        thread_id: str,
        message: str,
        buttons: list[dict[str, str]],
        *,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        return self._record("buttons", thread_id, message, buttons=buttons)

    def update_message(self, message_id: str, message: str, *, channel_id: str | None = None) -> dict[str, Any]:
        return self._record("update", "web-default", message, replaces=message_id)

    def resolve_thread(self, thread_id: str) -> dict[str, Any]:
        return self.tasks.resolve_context("web", thread_id)


class SlackAgentChannel(AgentChannel):
    def __init__(self, transport: SlackTransport, tasks: AgentTaskService, *, default_channel: str | None = None) -> None:
        self.transport = transport
        self.tasks = tasks
        self.default_channel = default_channel

    def send_message(self, thread_id: str, message: str, *, channel_id: str | None = None) -> dict[str, Any]:
        channel = self._channel(channel_id)
        payload = {"channel": channel, "text": message}
        if thread_id:
            payload["thread_ts"] = thread_id
        result = self.transport.call("chat.postMessage", payload)
        self.tasks.record_outbox({"channel": "slack", "kind": "message", "thread_id": thread_id, "message": message, "message_id": result.get("ts")})
        return result

    def receive_message(
        self,
        thread_id: str,
        message: str,
        *,
        user_id: str | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        return self.tasks.record_outbox(
            {
                "channel": "slack",
                "kind": "received",
                "thread_id": thread_id,
                "channel_id": channel_id,
                "user_id": user_id,
                "message": message,
            }
        )

    def send_status(
        self,
        thread_id: str,
        message: str,
        *,
        channel_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        if message_id:
            return self.update_message(message_id, message, channel_id=channel_id)
        return self.send_message(thread_id, message, channel_id=channel_id)

    def send_image(
        self,
        thread_id: str,
        image_url: str,
        title: str,
        *,
        channel_id: str | None = None,
        details: str | None = None,
    ) -> dict[str, Any]:
        channel = self._channel(channel_id)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*\n{details or ''}".strip()}},
            {"type": "image", "image_url": image_url, "alt_text": title[:200]},
        ]
        result = self.transport.call(
            "chat.postMessage",
            {"channel": channel, "thread_ts": thread_id, "text": title, "blocks": blocks},
        )
        self.tasks.record_outbox({"channel": "slack", "kind": "image", "thread_id": thread_id, "image_url": image_url, "message_id": result.get("ts")})
        return result

    def send_file(
        self,
        thread_id: str,
        path: Path,
        title: str,
        *,
        channel_id: str | None = None,
        details: str | None = None,
    ) -> dict[str, Any]:
        channel = self._channel(channel_id)
        uploader = getattr(self.transport, "upload_file", None)
        if not callable(uploader):
            raise RepositoryError("Slack file upload is unavailable for the configured transport")
        result = uploader(path, channel_id=channel, thread_ts=thread_id, title=title, initial_comment=details)
        self.tasks.record_outbox(
            {"channel": "slack", "kind": "file", "thread_id": thread_id, "path": str(path), "message_id": result.get("ts")}
        )
        return result

    def send_buttons(
        self,
        thread_id: str,
        message: str,
        buttons: list[dict[str, str]],
        *,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        channel = self._channel(channel_id)
        result = self.transport.call(
            "chat.postMessage",
            {
                "channel": channel,
                "thread_ts": thread_id,
                "text": message,
                "blocks": self._button_blocks(message, buttons),
            },
        )
        self.tasks.record_outbox({"channel": "slack", "kind": "buttons", "thread_id": thread_id, "buttons": buttons, "message_id": result.get("ts")})
        return result

    def update_buttons(
        self,
        message_id: str,
        message: str,
        buttons: list[dict[str, str]],
        *,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """Update one working message while preserving its deep-link action."""
        channel = self._channel(channel_id)
        result = self.transport.call(
            "chat.update",
            {
                "channel": channel,
                "ts": message_id,
                "text": message,
                "blocks": self._button_blocks(message, buttons),
            },
        )
        self.tasks.record_outbox(
            {
                "channel": "slack",
                "kind": "update_buttons",
                "message_id": message_id,
                "message": message,
                "buttons": buttons,
            }
        )
        return result

    def update_message(self, message_id: str, message: str, *, channel_id: str | None = None) -> dict[str, Any]:
        channel = self._channel(channel_id)
        result = self.transport.call("chat.update", {"channel": channel, "ts": message_id, "text": message})
        self.tasks.record_outbox({"channel": "slack", "kind": "update", "message_id": message_id, "message": message})
        return result

    def resolve_thread(self, thread_id: str) -> dict[str, Any]:
        return self.tasks.resolve_context("slack", thread_id)

    def _channel(self, channel_id: str | None) -> str:
        channel = channel_id or self.default_channel
        if not channel:
            raise RepositoryError("A Slack channel is required")
        return channel

    @staticmethod
    def _button_blocks(message: str, buttons: list[dict[str, str]]) -> list[dict[str, Any]]:
        elements = [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": item["label"][:75]},
                "action_id": item["action_id"],
                "value": item["value"][:2000],
                **({"url": item["url"]} if item.get("url") else {}),
                **({"style": item["style"]} if item.get("style") else {}),
            }
            for item in buttons
        ]
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            {"type": "actions", "elements": elements},
        ]


def public_asset_url(public_base_url: str, asset_url: str) -> str | None:
    if asset_url.startswith("https://"):
        return asset_url
    if public_base_url.startswith("https://") and asset_url.startswith("/"):
        return f"{public_base_url.rstrip('/')}{asset_url}"
    return None


def media_type_for(path: str) -> str:
    return mimetypes.guess_type(Path(path).name)[0] or "application/octet-stream"
