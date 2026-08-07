from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.backend.models.social_intelligence import BudgetSettings
from app.backend.services.repository_service import RepositoryError, RepositoryService

BUDGET_PATH = "app-data/provider_budget.json"
USAGE_PATH = "data/provider_usage.json"


class BudgetStopped(RepositoryError):
    pass


class BudgetService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def get_settings(self) -> BudgetSettings:
        payload = self.repository.read_json(BUDGET_PATH, {})
        return BudgetSettings.model_validate(payload or BudgetSettings().model_dump())

    def update_settings(self, settings: BudgetSettings) -> tuple[dict, str | None]:
        payload = settings.model_dump(mode="json")
        backup = self.repository.write_json(BUDGET_PATH, payload)
        return payload, backup

    def usage(self) -> list[dict[str, Any]]:
        return self.repository.read_json(USAGE_PATH, [])

    def usage_summary(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        records = self.usage()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        daily = sum(self._effective_cost(item) for item in records if self._timestamp(item) >= day_start)
        monthly = sum(self._effective_cost(item) for item in records if self._timestamp(item) >= month_start)
        settings = self.get_settings()
        remaining = max(0.0, settings.monthly_provider_budget - monthly)
        percent = (monthly / settings.monthly_provider_budget * 100) if settings.monthly_provider_budget else 100.0
        return {
            "daily_used": round(daily, 4),
            "daily_remaining": round(max(0.0, settings.daily_provider_budget - daily), 4),
            "monthly_used": round(monthly, 4),
            "monthly_remaining": round(remaining, 4),
            "monthly_budget": settings.monthly_provider_budget,
            "percent_used": round(percent, 1),
            "percent_remaining": round(max(0.0, 100 - percent), 1),
            "approaching_limit": settings.automatically_pause_at_80_percent and percent >= 80,
            "hard_limit_reached": settings.hard_stop_at_100_percent and percent >= 100,
        }

    def preflight(
        self,
        *,
        handles: list[dict],
        posts_per_handle: int,
        estimates: list[dict],
        provider_configured: bool,
        provider_state: str,
        scheduled: bool = False,
    ) -> dict[str, Any]:
        settings = self.get_settings()
        summary = self.usage_summary()
        enabled = [item for item in handles if item.get("enabled", True)]
        expected_requests = len(enabled)
        low_values = [item.get("estimated_cost_low") for item in estimates]
        high_values = [item.get("estimated_cost_high") for item in estimates]
        known_low = [float(value) for value in low_values if isinstance(value, (int, float))]
        known_high = [float(value) for value in high_values if isinstance(value, (int, float))]
        estimated_low = sum(known_low) if len(known_low) == len(estimates) else None
        estimated_high = sum(known_high) if len(known_high) == len(estimates) else None
        unknown = estimated_high is None or any(item.get("requires_confirmation") for item in estimates)
        warnings: list[str] = []
        hard_stops: list[str] = []
        if not provider_configured:
            hard_stops.append("Connect a social-data provider or import public post data manually.")
        if not settings.enable_paid_provider_calls:
            hard_stops.append("Paid provider calls are disabled in budget settings.")
        if provider_state not in {"Closed", "Half-open"}:
            hard_stops.append(f"Provider circuit is {provider_state.lower()}.")
        if len(enabled) > settings.maximum_handles_per_refresh:
            hard_stops.append(f"Reduce scope to {settings.maximum_handles_per_refresh} handles or fewer.")
        if posts_per_handle > settings.maximum_posts_per_handle:
            hard_stops.append(f"Reduce posts per handle to {settings.maximum_posts_per_handle} or fewer.")
        if expected_requests > settings.maximum_provider_requests_per_run:
            hard_stops.append("The selected scope exceeds the maximum provider requests per run.")
        if estimated_high is not None:
            if estimated_high > settings.maximum_estimated_cost_per_run:
                hard_stops.append("Estimated provider cost exceeds the configured per-run limit.")
            if not settings.allow_paid_overage and estimated_high > summary["daily_remaining"]:
                hard_stops.append("Estimated provider cost would exceed the daily provider budget.")
            if not settings.allow_paid_overage and estimated_high > summary["monthly_remaining"]:
                hard_stops.append("Estimated provider cost would exceed the monthly provider budget.")
            projected_percent = (
                (summary["monthly_used"] + estimated_high) / settings.monthly_provider_budget * 100
                if settings.monthly_provider_budget
                else 100
            )
            if projected_percent >= 80:
                warnings.append("This run may move usage beyond 80 percent of the monthly provider budget.")
        else:
            warnings.append("Provider cost cannot be reasonably estimated from current usage history.")
        if summary["approaching_limit"]:
            warnings.append("Approaching your monthly provider budget.")
        if summary["hard_limit_reached"] and not settings.allow_paid_overage:
            hard_stops.append("Provider calls paused to prevent additional charges.")
        requires_confirmation = bool(
            unknown
            or (estimated_high is not None and estimated_high >= settings.require_confirmation_above_estimated_cost)
            or warnings
        )
        if scheduled and requires_confirmation:
            hard_stops.append("Scheduled refresh skipped because this run requires confirmation.")
        platforms = sorted({str(item.get("platform", "")).title() for item in enabled if item.get("platform")})
        return {
            "handles": len(enabled),
            "platforms": platforms,
            "posts_per_handle": posts_per_handle,
            "maximum_posts": len(enabled) * posts_per_handle,
            "expected_provider_runs": expected_requests,
            "estimated_cost_low": round(estimated_low, 4) if estimated_low is not None else None,
            "estimated_cost_high": round(estimated_high, 4) if estimated_high is not None else None,
            "estimated_cost_label": "Estimated provider cost",
            "estimate_sources": sorted({str(item.get("source", "unknown")) for item in estimates}),
            "daily_budget_remaining": summary["daily_remaining"],
            "monthly_budget_remaining": summary["monthly_remaining"],
            "monthly_percent_used": summary["percent_used"],
            "requires_confirmation": requires_confirmation,
            "can_run": not hard_stops,
            "warnings": list(dict.fromkeys(warnings)),
            "hard_stops": list(dict.fromkeys(hard_stops)),
            "scheduled": scheduled,
        }

    def check_before_request(self, estimated_next_cost: float, *, request_count: int, phase: str) -> None:
        settings = self.get_settings()
        summary = self.usage_summary()
        if not settings.enable_paid_provider_calls:
            raise BudgetStopped("Paid provider calls are disabled in budget settings.")
        if request_count >= settings.maximum_provider_requests_per_run:
            raise BudgetStopped("Stopped before the next provider request because the per-run request limit was reached.")
        if settings.automatically_pause_at_80_percent and summary["percent_used"] >= 80 and not settings.allow_paid_overage:
            raise BudgetStopped("Stopped before the next provider request because 80 percent of the monthly budget was reached.")
        if estimated_next_cost > settings.maximum_estimated_cost_per_run and not settings.allow_paid_overage:
            raise BudgetStopped("Stopped before the next provider request because the per-run cost limit was reached.")
        if settings.hard_stop_at_100_percent and not settings.allow_paid_overage:
            if estimated_next_cost > summary["daily_remaining"]:
                raise BudgetStopped("Stopped before the next provider request because the daily budget limit was reached.")
            if estimated_next_cost > summary["monthly_remaining"]:
                raise BudgetStopped("Stopped before the next provider request because the monthly budget limit was reached.")

    def check_after_usage(self) -> None:
        """Pause after recorded usage reaches a configured boundary, before any later request."""
        settings = self.get_settings()
        summary = self.usage_summary()
        if settings.allow_paid_overage:
            return
        if settings.hard_stop_at_100_percent and summary["hard_limit_reached"]:
            raise BudgetStopped("Provider calls paused to prevent additional charges.")
        if settings.automatically_pause_at_80_percent and summary["approaching_limit"]:
            raise BudgetStopped("Stopped before the next provider request because 80 percent of the monthly budget was reached.")

    def record_usage(self, record: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        actual = record.get("actual_cost")
        estimated = record.get("estimated_cost_before")
        if actual is not None and (not isinstance(actual, (int, float)) or actual < 0):
            raise RepositoryError("Actual provider cost must be a non-negative number or null")
        if estimated is not None and (not isinstance(estimated, (int, float)) or estimated < 0):
            raise RepositoryError("Estimated provider cost must be a non-negative number or null")
        payload = {
            "id": record.get("id") or f"usage-{uuid.uuid4().hex[:12]}",
            "provider": record.get("provider", "unknown"),
            "actor_id": record.get("actor_id"),
            "run_id": record.get("run_id"),
            "timestamp": record.get("timestamp") or datetime.now(UTC).isoformat(),
            "estimated_cost_before": estimated,
            "actual_cost": actual,
            "currency": record.get("currency", "USD"),
            "requests": int(record.get("requests") or 0),
            "compute_units": record.get("compute_units"),
            "items_returned": int(record.get("items_returned") or 0),
            "handles_processed": int(record.get("handles_processed") or 0),
            "platform": record.get("platform"),
            "billing_source": record.get("billing_source", "provider"),
            "usage_source": record.get("usage_source", "estimated" if actual is None else "provider_reported"),
            "status": record.get("status", "Completed"),
            "notes": record.get("notes", ""),
        }
        records = self.usage()
        records.append(payload)
        backup = self.repository.write_json(
            USAGE_PATH,
            records,
            schema_relative="schemas/provider_usage.schema.json",
            validate_each=True,
        )
        return payload, backup

    @staticmethod
    def _effective_cost(record: dict[str, Any]) -> float:
        actual = record.get("actual_cost")
        if isinstance(actual, (int, float)):
            return max(0.0, float(actual))
        estimated = record.get("estimated_cost_before")
        return max(0.0, float(estimated)) if isinstance(estimated, (int, float)) else 0.0

    @staticmethod
    def _timestamp(record: dict[str, Any]) -> datetime:
        try:
            parsed = datetime.fromisoformat(str(record.get("timestamp", "")).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC) - timedelta(days=36500)
