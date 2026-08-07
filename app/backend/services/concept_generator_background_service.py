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

LABEL = "com.dinkly.creative-studio.concept-generator"
LEGACY_LABELS = ("com.dinkly.creative-studio.content-agent", "com.dinkly.content-agent")
HEARTBEAT_PATH = "app-data/concept_generator_worker_heartbeat.json"


class ConceptGeneratorBackgroundService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.root = repository.root
        self.plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        self.python = self.root / ".venv" / "bin" / "python"
        self.logs = self.root / "app-data" / "logs"

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        heartbeat = self.repository.read_json(HEARTBEAT_PATH, {})
        value = heartbeat.get("timestamp") if isinstance(heartbeat, dict) else None
        fresh = False
        if value:
            with suppress(ValueError):
                fresh = datetime.fromisoformat(str(value).replace("Z", "+00:00")) >= now - timedelta(minutes=2)
        installed = self.plist_path.is_file()
        loaded = self._is_loaded()
        return {
            "label": LABEL,
            "installed": installed,
            "loaded": loaded,
            "running": loaded and fresh,
            "status": "Running" if loaded and fresh else "Not Running",
            "heartbeat_at": value,
            "plist_path": str(self.plist_path),
            "python_path": str(self.python),
            "python_valid": self.python.is_file(),
            "working_directory": str(self.root),
            "stdout_log": str(self.logs / "concept-generator-worker.log"),
            "stderr_log": str(self.logs / "concept-generator-worker.error.log"),
            "legacy_services_detected": [label for label in LEGACY_LABELS if self._label_loaded(label) or self._plist_for(label).is_file()],
        }

    def install(self) -> dict[str, Any]:
        if not shutil.which("launchctl"):
            raise RepositoryError("macOS launchctl is unavailable; the background agent can only be installed on macOS.")
        if not self.python.is_file():
            raise RepositoryError("The project Python environment is missing. Run uv sync before installing the background agent.")
        self.logs.mkdir(parents=True, exist_ok=True)
        self.plist_path.parent.mkdir(parents=True, exist_ok=True)
        migrated: list[str] = []
        for legacy in LEGACY_LABELS:
            self._launchctl("bootout", f"gui/{os.getuid()}/{legacy}", allow_missing=True)
            legacy_plist = self._plist_for(legacy)
            if legacy_plist.is_file():
                disabled = legacy_plist.with_name(f"{legacy_plist.name}.{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.migrated")
                os.replace(legacy_plist, disabled)
                migrated.append(str(disabled))
        payload = {
            "Label": LABEL,
            "ProgramArguments": [str(self.python), "-m", "app.backend.workers.concept_generator_worker"],
            "WorkingDirectory": str(self.root),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 10,
            "StandardOutPath": str(self.logs / "concept-generator-worker.log"),
            "StandardErrorPath": str(self.logs / "concept-generator-worker.error.log"),
            "EnvironmentVariables": {"DINKLY_REPOSITORY_ROOT": str(self.root), "PYTHONUNBUFFERED": "1"},
        }
        temporary = self.plist_path.with_suffix(".plist.tmp")
        temporary.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True))
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.plist_path)
        self._launchctl("bootout", f"gui/{os.getuid()}/{LABEL}", allow_missing=True)
        self._launchctl("bootstrap", f"gui/{os.getuid()}", str(self.plist_path))
        self._launchctl("kickstart", "-k", f"gui/{os.getuid()}/{LABEL}")
        return {**self.status(), "migrated_legacy_plists": migrated}

    def start(self) -> dict[str, Any]:
        if not self.plist_path.is_file():
            return self.install()
        if not self._is_loaded():
            self._launchctl("bootstrap", f"gui/{os.getuid()}", str(self.plist_path))
        self._launchctl("kickstart", "-k", f"gui/{os.getuid()}/{LABEL}")
        return self.status()

    def restart(self) -> dict[str, Any]:
        if not self.plist_path.is_file():
            return self.install()
        self._launchctl("bootout", f"gui/{os.getuid()}/{LABEL}", allow_missing=True)
        self._launchctl("bootstrap", f"gui/{os.getuid()}", str(self.plist_path))
        self._launchctl("kickstart", "-k", f"gui/{os.getuid()}/{LABEL}")
        return self.status()

    def logs_tail(self, lines: int = 100) -> dict[str, Any]:
        def tail(path: Path) -> list[str]:
            if not path.is_file():
                return []
            return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        return {"stdout": tail(self.logs / "concept-generator-worker.log"), "stderr": tail(self.logs / "concept-generator-worker.error.log")}

    @staticmethod
    def _launchctl(*arguments: str, allow_missing: bool = False) -> None:
        process = subprocess.run(["launchctl", *arguments], text=True, capture_output=True, check=False)
        message = (process.stderr or process.stdout).strip()
        missing = "could not find service" in message.lower() or "no such process" in message.lower()
        if process.returncode and not (allow_missing and missing):
            raise RepositoryError(f"launchctl failed: {message or process.returncode}")

    @staticmethod
    def _is_loaded() -> bool:
        return ConceptGeneratorBackgroundService._label_loaded(LABEL)

    @staticmethod
    def _label_loaded(label: str) -> bool:
        if not shutil.which("launchctl"):
            return False
        process = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            text=True,
            capture_output=True,
            check=False,
        )
        return process.returncode == 0

    @staticmethod
    def _plist_for(label: str) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
