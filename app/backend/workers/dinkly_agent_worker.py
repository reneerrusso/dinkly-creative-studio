from __future__ import annotations

import signal
from datetime import UTC, datetime
from os import getpid
from threading import Event, Thread

from app.backend.services.agent_schedule_service import AgentScheduleService
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.agent_visual_state_service import AgentVisualStateService
from app.backend.services.dinkly_agent_runtime import DinklyAgent
from app.backend.services.repository_service import RepositoryService
from app.backend.services.slack_service import SlackService, SlackSocketModeReceiver


def main() -> int:
    repository = RepositoryService()
    tasks = AgentTaskService(repository)
    visual = AgentVisualStateService(repository)
    agent = DinklyAgent(repository, tasks=tasks, visual=visual)
    schedules = AgentScheduleService(repository, tasks, agent.concepts, visual)
    tasks.recover_interrupted()
    stopped = Event()

    def stop(*_args) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    slack = SlackService(
        repository,
        tasks,
        agent.receive_instruction,
        agent.receive_approval,
        cancellation_receiver=agent.request_cancellation,
    )
    socket_thread: Thread | None = None
    socket_stopped: Event | None = None

    def sync_socket_mode() -> None:
        nonlocal socket_thread, socket_stopped
        slack_status = slack.status()
        should_run = bool(
            slack_status["connected"]
            and slack_status["mode"] == "socket_mode"
            and slack_status["socket_mode_configured"]
        )
        if socket_thread and not socket_thread.is_alive():
            socket_thread = None
            socket_stopped = None
        if should_run and socket_thread is None:
            socket_stopped = Event()
            socket_thread = Thread(
                target=SlackSocketModeReceiver(slack).run_forever,
                args=(socket_stopped,),
                name="dinkly-slack-socket",
                daemon=True,
            )
            socket_thread.start()
        elif not should_run and socket_stopped is not None:
            socket_stopped.set()

    while not stopped.is_set():
        sync_socket_mode()
        repository.write_json(
            "app-data/dinkly-agent/worker-heartbeat.json",
            {"timestamp": datetime.now(UTC).isoformat(), "pid": getpid(), "status": "online"},
            create_backup=False,
        )
        try:
            agent.reconcile_cancellations()
            schedules.queue_due()
            processed = agent.process_next()
            if not processed:
                stopped.wait(2)
        except Exception as exc:
            print(f"DINKLY Agent worker error: {type(exc).__name__}: {exc}", flush=True)
            stopped.wait(3)
    if socket_stopped:
        socket_stopped.set()
    if socket_thread:
        socket_thread.join(timeout=3)
    repository.write_json(
        "app-data/dinkly-agent/worker-heartbeat.json",
        {"timestamp": datetime.now(UTC).isoformat(), "pid": getpid(), "status": "stopped"},
        create_backup=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
