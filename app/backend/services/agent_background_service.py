from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.backend.services.repository_service import RepositoryError, RepositoryService

LABEL = "com.dinkly.creative-studio.agent"
LEGACY_LABELS = (
    "com.dinkly.creative-studio.concept-generator",
    "com.dinkly.creative-studio.content-agent",
    "com.dinkly.content-agent",
)


class AgentBackgroundService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.root = repository.root
        self.plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        self.python = self.root / ".venv" / "bin" / "python"
        self.logs = self.root / "app-data" / "logs"

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        heartbeat = self.repository.read_json("app-data/dinkly-agent/worker-heartbeat.json", {})
        value = heartbeat.get("timestamp") if isinstance(heartbeat, dict) else None
        fresh = False
        if value:
            with suppress(ValueError):
                fresh = datetime.fromisoformat(str(value).replace("Z", "+00:00")) >= now - timedelta(minutes=2)
        loaded = self._loaded(LABEL)
        return {
            "label": LABEL,
            "installed": self.plist_path.is_file(),
            "loaded": loaded,
            "running": fresh and (loaded or heartbeat.get("status") == "online"),
            "status": "Running" if fresh else "Not running",
            "heartbeat_at": value,
            "mode": self.repository.settings.app_mode,
            "stdout_log": str(self.logs / "dinkly-agent-worker.log"),
            "stderr_log": str(self.logs / "dinkly-agent-worker.error.log"),
        }

    def install(self) -> dict[str, Any]:
        if not shutil.which("launchctl"):
            raise RepositoryError("macOS launchctl is unavailable")
        if not self.python.is_file():
            raise RepositoryError("Run uv sync before installing the always-on Agent")
        self.logs.mkdir(parents=True, exist_ok=True)
        self.plist_path.parent.mkdir(parents=True, exist_ok=True)
        for legacy in LEGACY_LABELS:
            self._launchctl("bootout", f"gui/{os.getuid()}/{legacy}", allow_missing=True)
        payload = {
            "Label": LABEL,
            "ProgramArguments": [str(self.python), "-m", "app.backend.workers.dinkly_agent_worker"],
            "WorkingDirectory": str(self.root),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 10,
            "StandardOutPath": str(self.logs / "dinkly-agent-worker.log"),
            "StandardErrorPath": str(self.logs / "dinkly-agent-worker.error.log"),
            "EnvironmentVariables": {"DINKLY_REPOSITORY_ROOT": str(self.root), "PYTHONUNBUFFERED": "1"},
        }
        temporary = self.plist_path.with_suffix(".plist.tmp")
        temporary.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True))
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.plist_path)
        self.restart()
        return self.status()

    def start(self) -> dict[str, Any]:
        if not self.plist_path.is_file():
            return self.install()
        if not self._loaded(LABEL):
            self._launchctl("bootstrap", f"gui/{os.getuid()}", str(self.plist_path))
        self._launchctl("kickstart", "-k", f"gui/{os.getuid()}/{LABEL}")
        return self.status()

    def restart(self) -> dict[str, Any]:
        self._launchctl("bootout", f"gui/{os.getuid()}/{LABEL}", allow_missing=True)
        self._launchctl("bootstrap", f"gui/{os.getuid()}", str(self.plist_path))
        self._launchctl("kickstart", "-k", f"gui/{os.getuid()}/{LABEL}")
        return self.status()

    def logs_tail(self, lines: int = 100) -> dict[str, list[str]]:
        def tail(path: Path) -> list[str]:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:] if path.is_file() else []

        return {
            "stdout": tail(self.logs / "dinkly-agent-worker.log"),
            "stderr": tail(self.logs / "dinkly-agent-worker.error.log"),
        }

    @staticmethod
    def _launchctl(*arguments: str, allow_missing: bool = False) -> None:
        result = subprocess.run(["launchctl", *arguments], text=True, capture_output=True, check=False)
        message = (result.stderr or result.stdout).strip()
        missing = "could not find service" in message.lower() or "no such process" in message.lower()
        if result.returncode and not (allow_missing and missing):
            raise RepositoryError(f"launchctl failed: {message or result.returncode}")

    @staticmethod
    def _loaded(label: str) -> bool:
        if not shutil.which("launchctl"):
            return False
        return subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            check=False,
        ).returncode == 0
