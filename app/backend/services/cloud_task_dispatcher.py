from __future__ import annotations

import logging

import httpx

from app.backend.config import Settings

logger = logging.getLogger(__name__)


class CloudTaskDispatcher:
    """Wake a stateless cloud task executor after durable work is queued."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def dispatch(self) -> dict[str, str | bool]:
        if self.settings.app_mode != "cloud":
            return {"dispatched": False, "reason": "local_worker_owns_queue"}
        if not self.settings.cloud_task_runner_url or not self.settings.cloud_task_token:
            logger.error("Cloud task dispatch skipped: runner URL or token is not configured")
            return {"dispatched": False, "reason": "cloud_task_runner_not_configured"}
        url = self.settings.cloud_task_runner_url.rstrip("/")
        if not url.endswith("/api/cloud/tasks/run-next"):
            url = f"{url}/api/cloud/tasks/run-next"
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self.settings.cloud_task_token}"},
                timeout=httpx.Timeout(connect=10, read=3600, write=10, pool=10),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Cloud task dispatch failed: %s", type(exc).__name__)
            return {"dispatched": False, "reason": "cloud_task_runner_unreachable"}
        return {"dispatched": True, "reason": "cloud_task_runner_woken"}
