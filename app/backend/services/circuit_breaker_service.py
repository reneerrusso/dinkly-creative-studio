from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.backend.providers.social_data import ProviderError
from app.backend.services.repository_service import RepositoryError, RepositoryService

STATE_PATH = "app-data/provider_states.json"
IMMEDIATE_OPEN_ERRORS = {"authentication", "insufficient_credit", "actor_unavailable", "schema_incompatible"}
MANUAL_ERRORS = {"authentication", "insufficient_credit", "actor_unavailable"}


class CircuitBreakerService:
    def __init__(self, repository: RepositoryService, cooldown_minutes: int = 15) -> None:
        self.repository = repository
        self.cooldown = timedelta(minutes=cooldown_minutes)

    def state(self, provider: str = "apify") -> dict[str, Any]:
        states = self.repository.read_json(STATE_PATH, {})
        current = states.get(provider) or self._default(provider)
        if current["circuit_state"] == "Open" and not current.get("manual_action_required"):
            opened_at = self._parse(current.get("opened_at"))
            if opened_at and datetime.now(UTC) - opened_at >= self.cooldown:
                current["circuit_state"] = "Half-open"
                current["status"] = "Provider unavailable"
                current["message"] = "Cooldown ended. Test one provider request before resuming normal work."
                self._save(provider, current)
        return current

    def ensure_available(self, provider: str = "apify") -> None:
        state = self.state(provider)
        if state.get("paused"):
            raise RepositoryError("Provider calls are paused. Resume them explicitly in Settings.")
        if state["circuit_state"] == "Open":
            raise RepositoryError(state.get("message") or "Provider circuit is open.")

    def record_success(self, provider: str = "apify") -> dict:
        current = self._default(provider)
        current.update(
            {
                "circuit_state": "Closed",
                "status": "Configured",
                "message": "Provider connection is healthy.",
                "last_success_at": datetime.now(UTC).isoformat(),
            }
        )
        self._save(provider, current)
        return current

    def record_error(self, error: ProviderError, provider: str = "apify") -> dict:
        current = self.state(provider)
        failures = int(current.get("consecutive_errors") or 0) + 1
        open_now = error.code in IMMEDIATE_OPEN_ERRORS or failures >= 3
        current.update(
            {
                "consecutive_errors": failures,
                "last_error_code": error.code,
                "last_error_at": datetime.now(UTC).isoformat(),
                "message": error.safe_message,
                "status": self._status(error.code),
            }
        )
        if open_now:
            current.update(
                {
                    "circuit_state": "Open",
                    "opened_at": datetime.now(UTC).isoformat(),
                    "manual_action_required": error.code in MANUAL_ERRORS,
                }
            )
        self._save(provider, current)
        return current

    def pause(self, reason: str = "Paused by user", provider: str = "apify") -> dict:
        current = self.state(provider)
        current.update({"paused": True, "status": "Budget paused", "message": reason})
        self._save(provider, current)
        return current

    def resume(self, *, confirmed: bool, provider: str = "apify") -> dict:
        if not confirmed:
            raise RepositoryError("Resuming provider calls requires explicit confirmation")
        current = self.state(provider)
        current.update(
            {
                "paused": False,
                "circuit_state": "Half-open" if current.get("consecutive_errors") else "Closed",
                "manual_action_required": False,
                "status": "Configured",
                "message": "Provider resumed. Test the connection before a paid refresh.",
            }
        )
        self._save(provider, current)
        return current

    def _save(self, provider: str, current: dict) -> None:
        states = self.repository.read_json(STATE_PATH, {})
        states[provider] = current
        self.repository.write_json(STATE_PATH, states)

    @staticmethod
    def _default(provider: str) -> dict[str, Any]:
        return {
            "provider": provider,
            "circuit_state": "Closed",
            "consecutive_errors": 0,
            "paused": False,
            "manual_action_required": False,
            "status": "Not configured",
            "message": "No provider connection has been tested yet.",
            "opened_at": None,
            "last_error_code": None,
            "last_error_at": None,
            "last_success_at": None,
        }

    @staticmethod
    def _status(code: str) -> str:
        return {
            "authentication": "Connection failed",
            "insufficient_credit": "Budget paused",
            "rate_limited": "Rate limited",
            "provider_unavailable": "Provider unavailable",
            "actor_unavailable": "Provider unavailable",
            "timeout": "Provider unavailable",
        }.get(code, "Provider unavailable")

    @staticmethod
    def _parse(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
