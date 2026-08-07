from __future__ import annotations

import os
import re
import tempfile
from contextlib import suppress
from datetime import UTC, datetime

from app.backend.services.repository_service import RepositoryError, RepositoryService

MANAGED_KEYS = (
    "APIFY_API_TOKEN",
    "APIFY_INSTAGRAM_ACTOR_ID",
    "APIFY_TIKTOK_ACTOR_ID",
    "OPENAI_API_KEY",
    "DINKLY_CONTENT_MODEL",
    "GEMINI_API_KEY",
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "SLACK_APP_TOKEN",
)
HEADER = "# Managed by DINKLY Creative Studio\n# Do not commit this file\n"


class SecretsService:
    """Backend-only local provider configuration with atomic, restrictive writes."""

    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.directory = repository.path("app-data/secrets")
        self.path = repository.path("app-data/secrets/.env.local")
        self.backup_directory = repository.path("app-data/secrets/backups")
        self._ensure_secure_directories()

    def get_provider_configuration_status(self) -> dict:
        values = self._effective_values()
        token = values.get("APIFY_API_TOKEN", "")
        source = "environment" if os.getenv("APIFY_API_TOKEN") else "local secrets file" if token else None
        provider_states = self.repository.read_json("app-data/provider_states.json", {})
        provider_state = provider_states.get("apify", {}) if isinstance(provider_states, dict) else {}
        last_tested_at = provider_state.get("last_success_at") or provider_state.get("last_error_at")
        return {
            "provider": "apify",
            "configured": bool(token),
            "masked_token": self._mask(token) if token else None,
            "instagram_actor_id": values.get("APIFY_INSTAGRAM_ACTOR_ID", ""),
            "tiktok_actor_id": values.get("APIFY_TIKTOK_ACTOR_ID", ""),
            "source": source,
            "secret_path": "app-data/secrets/.env.local" if self.path.exists() else None,
            "last_modified": (
                datetime.fromtimestamp(self.path.stat().st_mtime, UTC).isoformat() if self.path.exists() else None
            ),
            "last_tested_at": last_tested_at,
            "connection_status": provider_state.get("status", "Not tested"),
            "hot_reload_supported": True,
        }

    def get_apify_credentials(self) -> dict[str, str]:
        values = self._effective_values()
        return {
            key: values.get(key, "")
            for key in ("APIFY_API_TOKEN", "APIFY_INSTAGRAM_ACTOR_ID", "APIFY_TIKTOK_ACTOR_ID")
        }

    def get_content_credentials(self) -> dict[str, str]:
        values = self._effective_values()
        return {
            "OPENAI_API_KEY": values.get("OPENAI_API_KEY", ""),
            "DINKLY_CONTENT_MODEL": values.get("DINKLY_CONTENT_MODEL", "gpt-5.6-luna") or "gpt-5.6-luna",
        }

    def get_content_provider_status(self) -> dict:
        credentials = self.get_content_credentials()
        token = credentials["OPENAI_API_KEY"]
        source = "environment" if os.getenv("OPENAI_API_KEY") or os.getenv("DINKLY_OPENAI_API_KEY") else "local secrets file" if token else None
        return {
            "provider": "openai",
            "configured": bool(token),
            "masked_token": self._mask(token) if token else None,
            "model": credentials["DINKLY_CONTENT_MODEL"],
            "source": source,
            "secret_path": "app-data/secrets/.env.local" if self.path.exists() and token else None,
            "hot_reload_supported": True,
        }

    def get_gemini_api_key(self) -> str:
        return self._effective_values().get("GEMINI_API_KEY", "")

    def get_gemini_status(self) -> dict:
        token = self.get_gemini_api_key()
        source = "environment" if os.getenv("GEMINI_API_KEY") else "local secrets file" if token else None
        return {
            "provider": "google_gemini",
            "configured": bool(token),
            "status": "Connected" if token else "Not configured",
            "masked_token": self._mask(token) if token else None,
            "source": source,
            "secret_path": "app-data/secrets/.env.local" if self.path.exists() and token else None,
        }

    def get_slack_credentials(self) -> dict[str, str]:
        values = self._effective_values()
        return {
            "SLACK_BOT_TOKEN": values.get("SLACK_BOT_TOKEN", ""),
            "SLACK_SIGNING_SECRET": values.get("SLACK_SIGNING_SECRET", ""),
            "SLACK_APP_TOKEN": values.get("SLACK_APP_TOKEN", ""),
        }

    def get_slack_secret_status(self) -> dict:
        credentials = self.get_slack_credentials()
        bot_token = credentials["SLACK_BOT_TOKEN"]
        app_token = credentials["SLACK_APP_TOKEN"]
        return {
            "configured": bool(bot_token and credentials["SLACK_SIGNING_SECRET"]),
            "socket_mode_configured": bool(app_token),
            "masked_bot_token": self._mask(bot_token) if bot_token else None,
            "masked_app_token": self._mask(app_token) if app_token else None,
            "source": "environment" if os.getenv("SLACK_BOT_TOKEN") else "local secrets file" if bot_token else None,
        }

    def configure_slack(self, bot_token: str, signing_secret: str, app_token: str | None = None) -> dict:
        bot = bot_token.strip()
        signing = signing_secret.strip()
        app = (app_token or "").strip()
        if not bot.startswith("xoxb-") or len(bot) < 10:
            raise RepositoryError("Slack bot token must be an xoxb token")
        if len(signing) < 8 or any(character.isspace() for character in signing):
            raise RepositoryError("Slack signing secret is invalid")
        if app and (not app.startswith("xapp-") or len(app) < 10):
            raise RepositoryError("Slack app token must be an xapp token")
        self._update(
            {
                "SLACK_BOT_TOKEN": bot,
                "SLACK_SIGNING_SECRET": signing,
                "SLACK_APP_TOKEN": app or None,
            }
        )
        return self.get_slack_secret_status()

    def remove_slack(self) -> dict:
        self._update({"SLACK_BOT_TOKEN": None, "SLACK_SIGNING_SECRET": None, "SLACK_APP_TOKEN": None})
        return self.get_slack_secret_status()

    def configure_gemini(self, api_key: str) -> dict:
        clean = api_key.strip()
        if len(clean) < 8 or any(character.isspace() for character in clean):
            raise RepositoryError("Gemini API key is invalid")
        self._update({"GEMINI_API_KEY": clean})
        return self.get_gemini_status()

    def remove_gemini(self) -> dict:
        self._update({"GEMINI_API_KEY": None})
        return self.get_gemini_status()

    def configure_content_provider(self, api_key: str, model: str) -> dict:
        clean = api_key.strip()
        if len(clean) < 8 or any(character.isspace() for character in clean):
            raise RepositoryError("OpenAI API key is invalid")
        clean_model = model.strip()
        if len(clean_model) < 2 or any(character.isspace() for character in clean_model):
            raise RepositoryError("OpenAI model ID is invalid")
        self._update({"OPENAI_API_KEY": clean, "DINKLY_CONTENT_MODEL": clean_model})
        return self.get_content_provider_status()

    def remove_content_provider(self) -> dict:
        self._update({"OPENAI_API_KEY": None})
        return self.get_content_provider_status()

    def set_apify_token(self, token: str) -> dict:
        clean = token.strip()
        if len(clean) < 8 or any(character.isspace() for character in clean):
            raise RepositoryError("Apify API token is invalid")
        self._update({"APIFY_API_TOKEN": clean})
        return self.get_provider_configuration_status()

    def set_actor_ids(self, instagram_actor_id: str, tiktok_actor_id: str) -> dict:
        self._update(
            {
                "APIFY_INSTAGRAM_ACTOR_ID": instagram_actor_id.strip(),
                "APIFY_TIKTOK_ACTOR_ID": tiktok_actor_id.strip(),
            }
        )
        return self.get_provider_configuration_status()

    def configure_apify(self, token: str, instagram_actor_id: str, tiktok_actor_id: str) -> dict:
        clean = token.strip()
        if len(clean) < 8 or any(character.isspace() for character in clean):
            raise RepositoryError("Apify API token is invalid")
        self._update(
            {
                "APIFY_API_TOKEN": clean,
                "APIFY_INSTAGRAM_ACTOR_ID": instagram_actor_id.strip(),
                "APIFY_TIKTOK_ACTOR_ID": tiktok_actor_id.strip(),
            }
        )
        return self.get_provider_configuration_status()

    def remove_apify_token(self) -> dict:
        self._update({"APIFY_API_TOKEN": None})
        status = self.get_provider_configuration_status()
        if os.getenv("APIFY_API_TOKEN"):
            status["message"] = "The local token was removed, but APIFY_API_TOKEN is still set in the backend environment."
        else:
            status["message"] = "The local Apify token was removed."
        return status

    def reload_provider_configuration(self) -> dict:
        # Providers read this service for every operation, so no process-global token cache is retained.
        return {**self.get_provider_configuration_status(), "reloaded": True, "restart_required": False}

    def test_apify_connection(self, provider_factory) -> dict:
        provider = provider_factory(self.get_apify_credentials())
        return provider.validate_credentials()

    def redact(self, value: str) -> str:
        redacted = value
        token = self._effective_values().get("APIFY_API_TOKEN", "")
        if token:
            redacted = redacted.replace(token, "[REDACTED]")
        content_token = self._effective_values().get("OPENAI_API_KEY", "")
        if content_token:
            redacted = redacted.replace(content_token, "[REDACTED]")
        gemini_token = self._effective_values().get("GEMINI_API_KEY", "")
        if gemini_token:
            redacted = redacted.replace(gemini_token, "[REDACTED]")
        for key in ("SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_APP_TOKEN"):
            secret = self._effective_values().get(key, "")
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        redacted = re.sub(r"(?i)(token|authorization|bearer)(\s*[:=]?\s*)([^\s,;]+)", r"\1\2[REDACTED]", redacted)
        return redacted

    def _effective_values(self) -> dict[str, str]:
        stored = self._read_file_values()
        values = {key: os.getenv(key) or stored.get(key, "") for key in MANAGED_KEYS}
        values["OPENAI_API_KEY"] = os.getenv("DINKLY_OPENAI_API_KEY") or values.get("OPENAI_API_KEY", "")
        return values

    def _read_file_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if not self.path.exists():
            return values
        for line in self.path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def _update(self, updates: dict[str, str | None]) -> None:
        unknown = set(updates) - set(MANAGED_KEYS)
        if unknown:
            raise RepositoryError("Only managed provider keys may be changed")
        existing_lines = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []
        preserved: list[str] = []
        existing_managed = self._read_file_values()
        for line in existing_lines:
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key not in MANAGED_KEYS and line not in HEADER.splitlines():
                preserved.append(line)
        merged: dict[str, str] = {**existing_managed}
        for key, value in updates.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        body = HEADER
        if preserved:
            body += "\n" + "\n".join(preserved).rstrip() + "\n"
        managed_lines = [f"{key}={merged[key]}" for key in MANAGED_KEYS if key in merged]
        if managed_lines:
            body += "\n" + "\n".join(managed_lines) + "\n"
        self._secure_atomic_write(body.encode())

    def _secure_atomic_write(self, content: bytes) -> None:
        self._ensure_secure_directories()
        if self.path.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            backup = self.backup_directory / f"{stamp}__.env.local.bak"
            backup.write_bytes(self.path.read_bytes())
            os.chmod(backup, 0o600)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".env.local.", suffix=".tmp", dir=self.directory)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise

    def _ensure_secure_directories(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            os.chmod(self.directory, 0o700)
            os.chmod(self.backup_directory, 0o700)

    @staticmethod
    def _mask(token: str) -> str:
        suffix = token[-4:] if len(token) >= 4 else ""
        return f"••••••••••••{suffix}"
