from __future__ import annotations

import signal
from datetime import UTC, datetime
from os import getpid
from threading import Event, Thread

from app.backend.services.concept_generator_scheduler import ConceptGeneratorScheduler
from app.backend.services.concept_generator_service import ConceptGeneratorService
from app.backend.services.repository_service import RepositoryService


def main() -> int:
    repository = RepositoryService()
    service = ConceptGeneratorService(repository)
    scheduler = ConceptGeneratorScheduler(service)
    scheduler.recover_interrupted_run()
    stopped = Event()

    def stop(*_args) -> None:
        stopped.set()

    def heartbeat() -> None:
        while not stopped.is_set():
            repository.write_json(
                "app-data/concept_generator_worker_heartbeat.json",
                {"timestamp": datetime.now(UTC).isoformat(), "pid": getpid()},
                create_backup=False,
            )
            stopped.wait(30)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    heartbeat_thread = Thread(target=heartbeat, name="concept-generator-heartbeat", daemon=True)
    heartbeat_thread.start()
    while not stopped.is_set():
        try:
            scheduler.run_due(trigger="worker")
        except Exception as exc:  # The scheduler persists the exact error before it reaches this log.
            print(f"Concept Generator scheduler error: {exc}", flush=True)
        stopped.wait(30)
    heartbeat_thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
