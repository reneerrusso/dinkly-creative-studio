from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from app.backend.models.dinkly_agent import SlackConnectRequest, SlackSettingsUpdate
from app.backend.services.agent_channels import SlackAgentChannel, SlackTransport, SlackWebApiTransport
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.secrets_service import SecretsService
from app.backend.services.tls_service import create_verified_ssl_context, verified_tls_diagnostics

SLACK_SETTINGS_PATH = "app-data/dinkly-agent/slack-settings.json"
DEFAULT_NOTIFICATIONS = {
    "daily_concepts_ready": True,
    "comic_ready_for_approval": True,
    "generation_failed": True,
    "meaningful_new_learning": True,
    "weekly_learning_recap": False,
    "routine_status": False,
}


class SlackSignatureVerifier:
    def __init__(self, signing_secret: str, *, tolerance_seconds: int = 300, clock: Callable[[], float] = time.time) -> None:
        self.signing_secret = signing_secret
        self.tolerance_seconds = tolerance_seconds
        self.clock = clock

    def verify(self, timestamp: str | None, signature: str | None, body: bytes) -> bool:
        if not timestamp or not signature or not self.signing_secret:
            return False
        try:
            value = int(timestamp)
        except ValueError:
            return False
        if abs(self.clock() - value) > self.tolerance_seconds:
            return False
        base = f"v0:{timestamp}:".encode() + body
        expected = "v0=" + hmac.new(self.signing_secret.encode(), base, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class SlackService:
    """Slack is a channel into the same persisted DINKLY Agent inbox."""

    def __init__(
        self,
        repository: RepositoryService,
        tasks: AgentTaskService,
        instruction_receiver: Callable[..., dict[str, Any]],
        approval_receiver: Callable[..., dict[str, Any]],
        *,
        cancellation_receiver: Callable[..., dict[str, Any]] | None = None,
        transport_factory: Callable[[str], SlackTransport] | None = None,
    ) -> None:
        self.repository = repository
        self.tasks = tasks
        self.secrets = SecretsService(repository)
        self.instruction_receiver = instruction_receiver
        self.approval_receiver = approval_receiver
        self.cancellation_receiver = cancellation_receiver
        self.transport_factory = transport_factory or (lambda token: SlackWebApiTransport(token))
        if not self.repository.path(SLACK_SETTINGS_PATH).exists():
            self.repository.write_json(SLACK_SETTINGS_PATH, self._defaults(), create_backup=False)

    def settings(self) -> dict[str, Any]:
        stored = self.repository.read_json(SLACK_SETTINGS_PATH, {})
        return {**self._defaults(), **stored, "notifications": {**DEFAULT_NOTIFICATIONS, **stored.get("notifications", {})}}

    def status(self) -> dict[str, Any]:
        settings = self.settings()
        secret_status = self.secrets.get_slack_secret_status()
        socket_ready = settings["mode"] != "socket_mode" or secret_status["socket_mode_configured"]
        return {
            "connected": bool(settings.get("connected") and secret_status["configured"] and socket_ready),
            "connection_status": settings.get("connection_status", "Not connected"),
            "mode": settings["mode"],
            "workspace_id": settings.get("workspace_id"),
            "workspace_name": settings.get("workspace_name"),
            "bot_user_id": settings.get("bot_user_id"),
            "bot_name": settings.get("bot_name"),
            "default_channel": settings.get("default_channel"),
            "allowed_users": settings.get("allowed_users", []),
            "notifications": settings["notifications"],
            "last_event_received": settings.get("last_event_received"),
            "last_message_sent": settings.get("last_message_sent"),
            "configured": secret_status["configured"],
            "socket_mode_configured": secret_status["socket_mode_configured"],
            "socket_mode_active": bool(settings.get("socket_mode_active")),
            "socket_mode_status": settings.get("socket_mode_status"),
            "tls_status": settings.get("tls_status", "Not tested"),
            "slack_api_status": settings.get("slack_api_status", "Not tested"),
            "masked_bot_token": secret_status["masked_bot_token"],
        }

    def connect(self, payload: SlackConnectRequest) -> dict[str, Any]:
        if not payload.allowed_users:
            raise RepositoryError("Add at least one allowed Slack user before connecting")
        self.secrets.configure_slack(payload.bot_token, payload.signing_secret, payload.app_token)
        settings = {
            **self.settings(),
            "mode": payload.mode,
            "default_channel": payload.default_channel,
            "allowed_users": sorted(set(payload.allowed_users)),
            "connection_status": "Configured — not tested",
        }
        self.repository.write_json(SLACK_SETTINGS_PATH, settings)
        return self.test_connection()

    def update_settings(self, payload: SlackSettingsUpdate) -> dict[str, Any]:
        if not payload.allowed_users:
            raise RepositoryError("At least one authorized Slack user is required")
        settings = {
            **self.settings(),
            "mode": payload.mode,
            "default_channel": payload.default_channel,
            "allowed_users": sorted(set(payload.allowed_users)),
            "notifications": {**DEFAULT_NOTIFICATIONS, **payload.notifications},
        }
        self.repository.write_json(SLACK_SETTINGS_PATH, settings)
        return self.status()

    def test_connection(self) -> dict[str, Any]:
        credentials = self.secrets.get_slack_credentials()
        if not credentials["SLACK_BOT_TOKEN"]:
            raise RepositoryError("Missing environment variable: SLACK_BOT_TOKEN")
        if not credentials["SLACK_SIGNING_SECRET"]:
            raise RepositoryError("Missing environment variable: SLACK_SIGNING_SECRET")
        settings_before = self.settings()
        try:
            result = self._transport().call("auth.test", {})
            socket_status = self._verify_socket_mode(settings_before["mode"], credentials["SLACK_APP_TOKEN"])
            settings = {
                **settings_before,
                "connected": True,
                "connection_status": "Connected",
                "tls_status": "Connected",
                "slack_api_status": "Connected",
                "workspace_id": result.get("team_id"),
                "workspace_name": result.get("team"),
                "bot_user_id": result.get("user_id"),
                "bot_name": result.get("user"),
                "socket_mode_active": bool(settings_before.get("socket_mode_active")),
                "socket_mode_status": socket_status,
                "last_tested_at": datetime.now(UTC).isoformat(),
            }
        except RepositoryError as exc:
            message = self._credential_error(str(exc), settings_before["mode"])
            tls_status, api_status = self._connection_failure_status(message)
            settings = {
                **settings_before,
                "connected": False,
                "connection_status": message,
                "tls_status": tls_status,
                "slack_api_status": api_status,
                "socket_mode_active": False,
                "socket_mode_status": message if settings_before["mode"] == "socket_mode" else None,
                "last_tested_at": datetime.now(UTC).isoformat(),
            }
            self.repository.write_json(SLACK_SETTINGS_PATH, settings)
            raise RepositoryError(message) from exc
        self.repository.write_json(SLACK_SETTINGS_PATH, settings)
        return self.status()

    def diagnostics(self) -> dict[str, Any]:
        tls = verified_tls_diagnostics()
        settings = self.settings()
        return {
            **tls,
            "tls_verification_status": settings.get("tls_status") or tls["tls_verification_status"],
            "slack_api_reachable": settings.get("slack_api_status") == "Connected",
            "socket_mode_status": settings.get("socket_mode_status") or "Not tested",
        }

    def test_message(self) -> dict[str, Any]:
        """Verify identity and prove outbound delivery to the configured channel."""
        status = self.test_connection()
        channel_id = status.get("default_channel")
        if not channel_id:
            raise RepositoryError("Add a default Slack channel or DM ID before sending a test message")
        try:
            result = self.channel().send_message("", "DINKLY Agent is connected.", channel_id=str(channel_id))
        except RepositoryError as exc:
            self._record_health(
                connected=False,
                connection_status=f"Error — test message failed: {exc}",
                last_tested_at=datetime.now(UTC).isoformat(),
            )
            raise
        self._record_health(
            connected=True,
            connection_status="Connected",
            last_message_sent=datetime.now(UTC).isoformat(),
            last_test_message_ts=result.get("ts"),
        )
        return self.status()

    def disconnect(self) -> dict[str, Any]:
        self.secrets.remove_slack()
        settings = {**self._defaults(), "connection_status": "Not connected"}
        self.repository.write_json(SLACK_SETTINGS_PATH, settings)
        return self.status()

    def verify_request(self, headers: dict[str, str], body: bytes) -> bool:
        secret = self.secrets.get_slack_credentials()["SLACK_SIGNING_SECRET"]
        verifier = SlackSignatureVerifier(secret)
        return verifier.verify(headers.get("x-slack-request-timestamp"), headers.get("x-slack-signature"), body)

    def receive_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = str(payload.get("event_id") or "")
        if event_id and not self.tasks.mark_external_event(f"slack:{event_id}"):
            return {"ok": True, "duplicate": True}
        event = payload.get("event") or {}
        if event.get("bot_id") or event.get("subtype"):
            return {"ok": True, "ignored": "bot_or_subtype"}
        event_type = event.get("type")
        is_dm = event_type == "message" and event.get("channel_type") == "im"
        if event_type != "app_mention" and not is_dm:
            return {"ok": True, "ignored": "unsupported_event"}
        user_id = str(event.get("user") or "")
        channel_id = str(event.get("channel") or "")
        thread_id = str(event.get("thread_ts") or event.get("ts") or event_id)
        self._record_health(last_event_received=datetime.now(UTC).isoformat())
        if user_id not in set(self.settings().get("allowed_users", [])):
            if channel_id:
                self.channel().send_message(
                    thread_id,
                    "This DINKLY Agent isn't available to this account.",
                    channel_id=channel_id,
                )
            return {"ok": True, "unauthorized": True}
        bot_user_id = str(self.settings().get("bot_user_id") or "")
        text = re.sub(rf"<@{re.escape(bot_user_id)}>", "", str(event.get("text") or ""), flags=re.I).strip()
        if len(text) < 2:
            return {"ok": True, "ignored": "empty_instruction"}
        if text.lower().strip(" .!") in {"cancel current task", "cancel this task"}:
            current = self.tasks.current(thread_id=thread_id) or self.tasks.current()
            if not current:
                self.channel().send_message(thread_id, "There is no active task to cancel.", channel_id=channel_id)
                return {"ok": True, "message": "There is no active task to cancel."}
            result = (
                self.cancellation_receiver(current["id"], reason="Cancelled from Slack")
                if self.cancellation_receiver
                else {"task": self.tasks.request_cancellation(current["id"], reason="Cancelled from Slack")[0]}
            )
            status_text = "Task cancelled." if result["task"]["status"] == "cancelled" else "Cancellation requested. Finishing the current safe step…"
            self.channel().send_status(thread_id, status_text, channel_id=channel_id)
            self._record_health(last_message_sent=datetime.now(UTC).isoformat())
            return {"ok": True, **result}
        result = self.instruction_receiver(
            channel="slack",
            message=text,
            user_id=user_id,
            thread_id=thread_id,
            source_message_id=str(event.get("ts") or event_id),
            external_event_id=event_id or str(event.get("ts")),
            channel_id=channel_id,
        )
        status = self.channel().send_status(
            thread_id,
            "DINKLY Agent · Queued\n✓ Assignment received\n○ Waiting for the Agent worker",
            channel_id=channel_id,
        )
        task = result["task"]
        context = {**task.get("context", {}), "slack_channel_id": channel_id, "slack_status_ts": status.get("ts")}
        self.tasks.update(task["id"], context=context)
        self._record_health(last_message_sent=datetime.now(UTC).isoformat())
        return {"ok": True, "task": self.tasks.get(task["id"])}

    def receive_interaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = str(payload.get("trigger_id") or payload.get("action_ts") or "")
        if event_id and not self.tasks.mark_external_event(f"slack-interaction:{event_id}"):
            return {"ok": True, "duplicate": True}
        user_id = str((payload.get("user") or {}).get("id") or "")
        if user_id not in set(self.settings().get("allowed_users", [])):
            return {"ok": False, "unauthorized": True}
        actions = payload.get("actions") or []
        if not actions:
            raise RepositoryError("Slack interaction did not include an action")
        action = actions[0]
        if str(action.get("action_id")) in {"dinkly_open_comic", "dinkly_open_batch"}:
            return {"ok": True, "opened": True}
        action_map = {
            "dinkly_approve": "approve",
            "dinkly_pass": "pass",
            "dinkly_fix": "fix",
            "dinkly_try_another": "try_another",
            "dinkly_more_like_this": "more_like_this",
        }
        requested = action_map.get(str(action.get("action_id")))
        if not requested:
            raise RepositoryError("Unknown DINKLY Slack action")
        value = json.loads(str(action.get("value") or "{}"))
        channel_id = str((payload.get("channel") or {}).get("id") or "")
        message = payload.get("message") or {}
        thread_id = str(message.get("thread_ts") or message.get("ts") or event_id)
        return self.approval_receiver(
            action=requested,
            item_type=value["item_type"],
            item_id=value["item_id"],
            notes=value.get("notes"),
            source_channel="slack",
            source_thread_id=thread_id,
            user_id=user_id,
            channel_id=channel_id,
            external_event_id=event_id,
        )

    def channel(self) -> SlackAgentChannel:
        return SlackAgentChannel(
            self._transport(),
            self.tasks,
            default_channel=self.settings().get("default_channel"),
        )

    def _transport(self) -> SlackTransport:
        token = self.secrets.get_slack_credentials()["SLACK_BOT_TOKEN"]
        if not token:
            raise RepositoryError("Slack is not configured")
        return self.transport_factory(token)

    def _record_health(self, **changes: Any) -> None:
        self.repository.write_json(SLACK_SETTINGS_PATH, {**self.settings(), **changes})

    def _verify_socket_mode(self, mode: str, app_token: str) -> str | None:
        if mode != "socket_mode":
            return None
        if not app_token:
            raise RepositoryError("Missing environment variable: SLACK_APP_TOKEN")
        if not app_token.startswith("xapp-"):
            raise RepositoryError("Invalid app token")
        try:
            response = self.transport_factory(app_token).call("apps.connections.open", {})
        except RepositoryError as exc:
            message = str(exc)
            if any(code in message for code in ("invalid_auth", "not_authed", "token_revoked", "not_allowed_token_type")):
                raise RepositoryError("Invalid app token") from exc
            raise RepositoryError(f"Socket Mode unavailable: {message}") from exc
        socket_url = str(response.get("url") or "")
        parsed = urlsplit(socket_url)
        if parsed.scheme != "wss" or not parsed.hostname:
            raise RepositoryError("Socket Mode unavailable: Slack did not return a valid WebSocket URL")
        return "Verified — worker connecting automatically"

    @staticmethod
    def _credential_error(message: str, mode: str) -> str:
        if message.startswith("Missing environment variable:"):
            return message
        if message == "Invalid app token" or message.startswith("Socket Mode unavailable:"):
            return message
        if any(code in message for code in ("invalid_auth", "not_authed", "token_revoked", "account_inactive")):
            return "Invalid bot token"
        if mode == "socket_mode" and "not_allowed_token_type" in message:
            return "Invalid app token"
        return message

    @staticmethod
    def _connection_failure_status(message: str) -> tuple[str, str]:
        lower = message.lower()
        if message.startswith("Socket Mode unavailable:") and ("tls" in lower or "certificate" in lower or "ca bundle" in lower):
            return message, "Connected"
        if "tls" in lower or "certificate" in lower or "ca bundle" in lower:
            return message, "Not tested"
        if message == "Invalid bot token" or message.startswith("Slack API error:"):
            return "Connected", message
        if message.startswith("Invalid app token") or message.startswith("Socket Mode unavailable:"):
            return "Connected", "Connected"
        return "Not tested", message

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "connected": False,
            "connection_status": "Not connected",
            "mode": "events_api",
            "workspace_id": None,
            "workspace_name": None,
            "bot_user_id": None,
            "bot_name": None,
            "default_channel": None,
            "allowed_users": [],
            "notifications": DEFAULT_NOTIFICATIONS,
            "last_event_received": None,
            "last_message_sent": None,
            "socket_mode_active": False,
            "socket_mode_status": None,
            "tls_status": "Not tested",
            "slack_api_status": "Not tested",
        }


class SlackSocketModeReceiver:
    """Optional local receiver. Events API remains the cloud deployment mode."""

    def __init__(self, service: SlackService) -> None:
        self.service = service

    def run_forever(self, stopped: Any) -> None:
        credentials = self.service.secrets.get_slack_credentials()
        app_token = credentials["SLACK_APP_TOKEN"]
        if not app_token:
            raise RepositoryError("Slack Socket Mode needs an app-level xapp token")
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise RepositoryError("Install the websocket runtime before using Slack Socket Mode") from exc
        while not stopped.is_set():
            try:
                response = SlackWebApiTransport(app_token).call("apps.connections.open", {})
                with connect(
                    response["url"],
                    ssl=create_verified_ssl_context(),
                    open_timeout=15,
                    close_timeout=5,
                ) as websocket:
                    self.service._record_health(socket_mode_active=True, socket_mode_status="Connected")
                    while not stopped.is_set():
                        raw = websocket.recv(timeout=30)
                        envelope = json.loads(raw)
                        envelope_id = envelope.get("envelope_id")
                        if envelope_id:
                            websocket.send(json.dumps({"envelope_id": envelope_id}))
                        payload = envelope.get("payload") or {}
                        if envelope.get("type") == "events_api":
                            self.service.receive_event(payload)
                        elif envelope.get("type") == "interactive":
                            self.service.receive_interaction(payload)
            except TimeoutError:
                continue
            except Exception as exc:
                reason = str(exc) if isinstance(exc, RepositoryError) else type(exc).__name__
                self.service._record_health(
                    socket_mode_active=False,
                    socket_mode_status=f"Socket Mode reconnecting: {reason}",
                )
                stopped.wait(5)
        self.service._record_health(socket_mode_active=False, socket_mode_status="Stopped")
