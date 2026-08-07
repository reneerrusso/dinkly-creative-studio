from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.backend.models.social_intelligence import RefreshRequest, RunStatus
from app.backend.services.social_intelligence_service import SocialIntelligenceService


class SocialIntelligenceScheduler:
    """Runs due local schedules while the backend worker is alive; never wakes a machine."""

    def __init__(self, service: SocialIntelligenceService) -> None:
        self.service = service

    def run_due(self, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or datetime.now(UTC)
        settings = self.service.budget.get_settings()
        if not settings.schedule_enabled:
            return None
        scheduled_runs = [
            item
            for item in self.service.runtime.list_runs()
            if bool((item.get("request") or {}).get("scheduled"))
        ]
        if scheduled_runs and not self._is_due(scheduled_runs[0].get("created_at"), settings.schedule_frequency, now):
            return None
        payload = RefreshRequest(scheduled=True, confirmed=False)
        preflight = self.service.preflight(payload)
        if not preflight["can_run"] or preflight["requires_confirmation"]:
            run = self.service.runtime.create_run("social-intelligence-scheduled-skip", payload.model_dump(mode="json"))
            reasons = preflight["hard_stops"] or ["Scheduled refresh skipped because this run requires confirmation."]
            self.service.runtime.emit(run["id"], "preflight", self.service._preflight_message(preflight), preflight)
            return self.service.runtime.finish(
                run["id"],
                RunStatus.BUDGET_STOPPED,
                {"scheduled": True, "handles_selected": preflight.get("handles", 0)},
                warnings=reasons,
            )
        started = self.service.start_refresh(payload)
        return self.service.execute_refresh(started["run"]["id"], payload)

    @staticmethod
    def _is_due(last_created_at: str | None, frequency: str, now: datetime) -> bool:
        if not last_created_at:
            return True
        try:
            last = datetime.fromisoformat(last_created_at.replace("Z", "+00:00"))
            if not last.tzinfo:
                last = last.replace(tzinfo=UTC)
        except ValueError:
            return True
        delay = {"Daily": timedelta(days=1), "Every 3 days": timedelta(days=3), "Weekly": timedelta(days=7)}[frequency]
        return now - last >= delay
