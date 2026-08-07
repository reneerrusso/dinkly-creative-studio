from __future__ import annotations

import json
import re
import threading
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from app.backend.config import settings
from app.backend.models.dinkly_agent import AgentSourceChannel, AgentTaskType
from app.backend.models.generation_engine import (
    GenerationRequest,
    RepairRequest,
    StoryBrief,
    StoryBriefRequest,
)
from app.backend.services.agent_channels import (
    AgentChannel,
    SlackAgentChannel,
    WebAgentChannel,
    public_asset_url,
)
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.agent_visual_state_service import AgentVisualStateService, DinklyLearningLoop
from app.backend.services.concept_service import ConceptService
from app.backend.services.content_agent_service import ConceptGeneratorService
from app.backend.services.generation_engine_service import (
    GenerationCancellationRequested,
    GenerationEngineService,
)
from app.backend.services.prompt_service import PromptService
from app.backend.services.repository_service import RepositoryError, RepositoryService

MEMORY_PATHS = (
    "data/generation_learnings.json",
    "data/prompt_learnings.json",
    "data/qa_learnings.json",
    "data/user_preferences.json",
)


class TaskCancellationRequested(Exception):
    pass


class DinklyAgent:
    """Canonical employee runtime shared by the web desk, Slack, and schedules."""

    def __init__(
        self,
        repository: RepositoryService,
        *,
        tasks: AgentTaskService | None = None,
        concepts: ConceptGeneratorService | None = None,
        generation: GenerationEngineService | None = None,
        visual: AgentVisualStateService | None = None,
        learning: DinklyLearningLoop | None = None,
    ) -> None:
        self.repository = repository
        self.tasks = tasks or AgentTaskService(repository)
        self.visual = visual or AgentVisualStateService(repository)
        self.learning = learning or DinklyLearningLoop(repository, self.visual)
        self.concepts = concepts or ConceptGeneratorService(repository)
        self.generation = generation or GenerationEngineService(
            repository,
            PromptService(repository, ConceptService(repository)),
        )

    def receive_instruction(
        self,
        *,
        channel: AgentSourceChannel,
        message: str,
        user_id: str,
        thread_id: str,
        source_message_id: str | None = None,
        external_event_id: str | None = None,
        channel_id: str | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = self.plan_task(message)
        classified_type = (extra_context or {}).get("classified_task_type")
        if classified_type in {
            "generate_comic", "generate_concepts", "repair_comic", "brain_query", "feedback"
        }:
            plan["task_type"] = classified_type
        prior = self.tasks.resolve_context(channel, thread_id)
        if not prior.get("recent_task_id"):
            prior = self._global_recent_context()
        context = {
            **prior,
            **plan["context"],
            **(extra_context or {}),
            **({"slack_channel_id": channel_id} if channel_id else {}),
        }
        ordinal = re.search(r"\b(?:number|#)\s*(\d{1,2})\b", message.lower())
        recent_concepts = (context.get("recent_result") or {}).get("concept_ids", [])
        if plan["task_type"] == "feedback" and ordinal and recent_concepts:
            index = int(ordinal.group(1)) - 1
            if 0 <= index < len(recent_concepts):
                context["recent_artifact_ids"] = [recent_concepts[index]]
        task, created = self.tasks.create_task(
            source_channel=channel,
            source_thread_id=thread_id,
            source_user_id=user_id,
            source_message_id=source_message_id,
            user_instruction=message,
            task_type=plan["task_type"],
            context=context,
            approval_required=plan["approval_required"],
            dedupe_key=f"channel:{channel}:{external_event_id}" if external_event_id else None,
        )
        if channel in {"web", "slack"} and created:
            self.tasks.append_message(
                channel=channel,
                thread_id=thread_id,
                user_id=user_id,
                role="user",
                message=message,
                linked_task_ids=[task["id"]],
            )
            acknowledgement = self._acknowledgement(plan["task_type"])
            self.tasks.append_message(
                channel=channel,
                thread_id=thread_id,
                role="agent",
                message=acknowledgement,
                linked_task_ids=[task["id"]],
            )
            self.visual.record_activity(
                acknowledgement,
                source_run_id=task["id"],
                details={"task_id": task["id"], "source_channel": channel, "queued": True},
            )
        return {"task": task, "created": created, "reply": self._acknowledgement(plan["task_type"])}

    def receive_approval(
        self,
        *,
        action: str,
        item_type: str,
        item_id: str,
        notes: str | None = None,
        source_channel: AgentSourceChannel = "web",
        source_thread_id: str | None = None,
        user_id: str = "owner",
        channel_id: str | None = None,
        external_event_id: str | None = None,
    ) -> dict[str, Any]:
        instruction = f"{action.replace('_', ' ')} {item_type} {item_id}"
        task, created = self.tasks.create_task(
            source_channel=source_channel,
            source_thread_id=source_thread_id or f"approval-{item_id}",
            source_user_id=user_id,
            user_instruction=instruction,
            task_type="approval",
            priority=2,
            context={
                "action": action,
                "item_type": item_type,
                "item_id": item_id,
                "notes": notes,
                **({"slack_channel_id": channel_id} if channel_id else {}),
            },
            dedupe_key=f"approval:{source_channel}:{external_event_id}" if external_event_id else None,
        )
        if created and action not in {"fix", "try_another", "more_like_this"}:
            task = self.tasks.update(task["id"], status="running", started_at=datetime.now(UTC).isoformat())
            task = self.invoke_tool(task)
        return {"task": task, "created": created, "reply": "Your decision is recorded."}

    def plan_task(self, instruction: str) -> dict[str, Any]:
        text = " ".join(instruction.strip().split())
        lower = text.lower()
        context: dict[str, Any] = {}
        count_match = re.search(r"\b(\d{1,2})\b", lower)
        if count_match:
            context["requested_count"] = max(1, min(int(count_match.group(1)), 30))
        else:
            word_counts = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "twenty": 20, "thirty": 30}
            named_count = next((value for word, value in word_counts.items() if re.search(rf"\b{word}\b", lower)), None)
            if named_count:
                context["requested_count"] = named_count
        candidate = re.search(r"candidate\s+([a-z])", lower)
        if candidate:
            context["candidate_label"] = candidate.group(1).upper()
        context["model_selection"] = "pro" if "pro" in lower else "balanced" if "balanced" in lower else "automatic"
        context["confirm_pro"] = bool(re.search(r"\b(use|with|on)\b.{0,20}\bpro\b", lower))

        if any(
            phrase in lower
            for phrase in ("try candidate", "make candidate", "fix ", "repair ", "make this", "try another")
        ):
            task_type: AgentTaskType = "repair_comic"
        elif any(phrase in lower for phrase in ("i like", "i love", "more like", "stop giving", "remember that", "less of", "don't give", "use girl", "use boy")):
            task_type = "feedback"
        elif any(phrase in lower for phrase in ("what have you learned", "what did you learn", "show me what", "waiting for approval", "working on")):
            task_type = "brain_query"
        elif lower.startswith("learn") or "run learning" in lower:
            task_type = "learn"
        elif any(word in lower for word in ("concept", "concepts", "idea", "ideas")):
            task_type = "generate_concepts"
        elif (
            "/" in text
            or re.search(r"\b(?:and|vs\.?|versus|compared to)\b.+\bwith you\b", lower)
            or any(phrase in lower for phrase in ("generate the", "generate comic", "make a comic", "create a comic", "make me a comic", "create me a comic"))
        ):
            task_type = "generate_comic"
        elif re.search(r"\b(approve|pass)\b", lower):
            task_type = "approval"
            context["action"] = "approve" if "approve" in lower else "pass"
        else:
            task_type = "custom"
        return {"task_type": task_type, "context": context, "approval_required": False}

    def start_run(self) -> dict[str, Any] | None:
        task = self.tasks.claim_next()
        if not task:
            self.visual.transition("idle", "Ready when you are.")
            return None
        timer: threading.Timer | None = None
        timeout = self.visual.settings().get("maximum_task_runtime_seconds")
        if timeout:
            timer = threading.Timer(
                float(timeout),
                lambda: self.request_cancellation(task["id"], reason=f"Maximum runtime of {timeout} seconds exceeded"),
            )
            timer.daemon = True
            timer.start()
        try:
            previous = next(
                (item for item in self.tasks.list_tasks(status="cancelled", limit=100) if (item.get("result") or {}).get("next_task_id") == task["id"]),
                None,
            )
            if previous:
                self.emit_event(
                    task,
                    "preparing",
                    f"{previous['user_instruction']} cancelled. Starting {task['user_instruction']}.",
                    event_type="next_task_started",
                )
            self._notify_status(task, self._status_message(task, "started"))
            result = self.invoke_tool(task)
            return result
        except (TaskCancellationRequested, GenerationCancellationRequested) as exc:
            return self._finish_cancellation(task["id"], str(exc) or "Safe checkpoint")
        except Exception as exc:
            if self.tasks.get(task["id"]).get("status") == "cancellation_requested":
                return self._finish_cancellation(task["id"], "Workflow cleanup")
            message = self._safe_error(exc)
            failed = self.tasks.fail(task["id"], message)
            failed = self.tasks.update(failed["id"], result={"message": f"Assignment failed: {message}"})
            self.visual.transition("error", message, source_run_id=task["id"], details={"task_id": task["id"]})
            self._append_agent_message(failed, f"I couldn't finish that: {message}")
            self._notify_status(failed, f"DINKLY hit an issue while generating this comic.\n\n{self._slack_failure_reason(message)}")
            self._deliver_failure(failed)
            self._deliver_proactive(failed)
            return failed
        finally:
            if timer:
                timer.cancel()

    process_next = start_run

    def request_cancellation(self, task_id: str, *, reason: str = "Cancelled by user", skip: bool = False) -> dict[str, Any]:
        task, message = self.tasks.request_cancellation(task_id, reason=reason, skip=skip)
        if message in {"Task already cancelled.", "Task already completed.", "Task already failed.", "Task already waiting for human."}:
            return {"task": task, "message": message}
        if task["status"] == "cancelled":
            self.emit_event(task, "idle", "Task cancelled.", event_type="task_cancelled")
            self._notify_status(task, "Task cancelled.")
            return {"task": task, "message": message}
        self.emit_event(task, "preparing", "Cancellation requested.", event_type="cancellation_requested")
        self.visual.record_activity(
            "Provider cancellation requested; this provider does not support remote cancellation, so its in-flight result will be ignored.",
            source_run_id=task_id,
            details={"event_type": "provider_cancellation_requested", "task_id": task_id, "supported": False},
        )
        self.emit_event(task, "preparing", "Finishing the current safe step…", event_type="workflow_stopping")
        self._notify_status(task, "DINKLY Agent · STOPPING\nFinishing the current safe step…")
        watchdog = threading.Timer(5.25, self._cancellation_watchdog, args=(task_id,))
        watchdog.daemon = True
        watchdog.start()
        return {"task": self.tasks.get(task_id), "message": message}

    def restart_task(self, task_id: str) -> dict[str, Any]:
        return self.tasks.restart(task_id)

    def _checkpoint(self, task_id: str, stage: str) -> None:
        if self.tasks.get(task_id).get("status") in {"cancellation_requested", "cancelled"}:
            raise TaskCancellationRequested(stage)

    def _cancellation_watchdog(self, task_id: str) -> None:
        try:
            task = self.tasks.get(task_id)
            if task.get("status") != "cancellation_requested":
                return
            # Stop every linked persisted run after the short grace period.
            # A provider request may still return because Gemini does not
            # expose remote cancellation, but should_cancel() will discard it.
            # Keeping the persisted task in STOPPING until that network call
            # returns made cancellation appear hung indefinitely.
            for run_id in task.get("run_ids", []):
                try:
                    if self.generation.get(run_id).get("status") in {"compiling", "generating", "reviewing", "repairing"}:
                        self.generation.cancel(run_id)
                except RepositoryError:
                    continue
            finalized = self.tasks.finalize_stale_cancellations(task_id=task_id)
            if task_id not in finalized:
                return
            task = self.tasks.get(task_id)
            self.emit_event(task, "idle", "Task cancelled. Completed work was preserved.", event_type="task_cancelled", stopped_at="Cancellation watchdog")
            self._append_agent_message(task, "Task cancelled. Completed work was preserved.")
            self._notify_status(task, "Task cancelled.")
        except RepositoryError:
            return

    def reconcile_cancellations(self) -> list[str]:
        finalized: list[str] = []
        for task in self.tasks.list_tasks(status="cancellation_requested", limit=500):
            before = task.get("status")
            self._cancellation_watchdog(task["id"])
            if before == "cancellation_requested" and self.tasks.get(task["id"]).get("status") == "cancelled":
                finalized.append(task["id"])
        return finalized

    def _finish_cancellation(self, task_id: str, stage: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        run_ids = list(task.get("run_ids", []))
        artifacts = list(task.get("artifact_ids", []))
        stopped_at = stage
        for run_id in run_ids:
            try:
                run = self.generation.get(run_id)
            except RepositoryError:
                continue
            artifacts = list(dict.fromkeys([*artifacts, *[item["id"] for item in run.get("candidates", []) if item.get("image_path")]]))
            stopped_at = str(run.get("cancellation_stage") or stage)
        next_task = self.tasks.peek_next()
        message = f"Task cancelled. Preserved {len(artifacts)} completed artifact{'s' if len(artifacts) != 1 else ''}."
        cancelled = self.tasks.mark_cancelled(
            task_id,
            stopped_at=stopped_at,
            result={"message": message, "task_cancelled": True, "next_task_id": next_task.get("id") if next_task else None},
            run_ids=run_ids,
            artifact_ids=artifacts,
        )
        self.emit_event(cancelled, "idle", message, event_type="task_cancelled", stopped_at=stopped_at, completed_artifacts=len(artifacts))
        self._append_agent_message(cancelled, message)
        self._notify_status(cancelled, "Task cancelled.")
        return cancelled

    def invoke_tool(self, task: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "generate_concepts": self._generate_concepts,
            "generate_comic": self._generate_comic,
            "repair_comic": self._repair_comic,
            "review_comic": self._review_comic,
            "learn": self._learn,
            "brain_query": self._brain_query,
            "feedback": self.handle_feedback,
            "approval": self._handle_approval,
            "custom": self._custom,
        }
        handler = handlers[str(task["task_type"])]
        return handler(task)

    def emit_event(self, task: dict[str, Any], state: str, message: str, **details: Any) -> dict[str, Any]:
        return self.visual.transition(
            state,  # type: ignore[arg-type]
            message,
            source_run_id=task["id"],
            details={"task_id": task["id"], **details},
        )

    def request_approval(
        self,
        task: dict[str, Any],
        result: dict[str, Any],
        *,
        run_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self._checkpoint(task["id"], "Before approval preparation")
        waiting = self.tasks.complete(
            task["id"],
            result,
            run_ids=run_ids,
            artifact_ids=artifact_ids,
            waiting_for_human=True,
        )
        if waiting.get("status") in {"cancellation_requested", "cancelled"}:
            raise TaskCancellationRequested("Before approval preparation")
        self.emit_event(task, "waiting_for_human", result.get("message", "Ready for your decision."))
        self._append_agent_message(waiting, result.get("message", "Ready for your decision."))
        self._deliver_result(waiting)
        return waiting

    def handle_feedback(self, task: dict[str, Any]) -> dict[str, Any]:
        self.emit_event(task, "learning", "Saving your creative preference.")
        feedback = self.learning.save_chat_preference(task["user_instruction"])
        context = task.get("context") or {}
        preference = feedback["preference"]
        preference.update(
            linked_task_id=context.get("recent_task_id"),
            linked_run_ids=context.get("recent_run_ids", []),
            linked_artifact_ids=context.get("recent_artifact_ids", []),
        )
        self._persist_preference_links(preference)
        result = {
            "message": feedback["reply"],
            "preference": preference,
            "linked_run_ids": context.get("recent_run_ids", []),
            "linked_artifact_ids": context.get("recent_artifact_ids", []),
        }
        return self.complete_task(task, result)

    def update_memory(self, learning_id: str, status: str) -> dict[str, Any]:
        for path in MEMORY_PATHS:
            records = self.repository.read_json(path, [])
            for record in records:
                if record.get("id") == learning_id:
                    record["status"] = status
                    record["updated_at"] = datetime.now(UTC).isoformat()
                    self.repository.write_json(path, records)
                    return record
        raise RepositoryError("Brain update not found")

    def complete_task(
        self,
        task: dict[str, Any],
        result: dict[str, Any],
        *,
        run_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self._checkpoint(task["id"], "Before completion")
        completed = self.tasks.complete(task["id"], result, run_ids=run_ids, artifact_ids=artifact_ids)
        if completed.get("status") in {"cancellation_requested", "cancelled"}:
            raise TaskCancellationRequested("Before completion")
        self.emit_event(task, "success", result.get("message", "Assignment complete."))
        self._append_agent_message(completed, result.get("message", "Assignment complete."))
        self._deliver_result(completed)
        return completed

    def approvals(self) -> dict[str, list[dict[str, Any]]]:
        concepts = [item for item in self.concepts.list_concepts() if item.get("status") == "candidate"]
        comics = [item for item in self.generation.history() if item.get("status") == "awaiting_human"]
        brain = [item for item in self.learning.recent_learnings(100) if item.get("status") == "proposed"]
        return {"concepts": concepts, "comics": comics, "brain_updates": brain}

    def task_events(self, task_id: str, after: str | None = None) -> list[dict[str, Any]]:
        task = self.tasks.get(task_id)
        linked = {task_id, *task.get("run_ids", [])}
        records = [
            event
            for event in self.visual.events(limit=250)
            if event.get("source_run_id") in linked or (event.get("details") or {}).get("task_id") == task_id
        ]
        if after:
            for index, event in enumerate(records):
                if event.get("id") == after:
                    records = records[index + 1 :]
                    break
        return records

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for task in self.tasks.list_tasks(limit=limit):
            if task.get("status") not in {"completed", "failed", "waiting_for_human", "cancelled"}:
                continue
            result = task.get("result") or {}
            started = AgentTaskService._parse_time(task.get("started_at") or task.get("created_at"))
            finished = AgentTaskService._parse_time(task.get("completed_at"))
            entries.append(
                {
                    "id": task["id"],
                    "kind": task["task_type"],
                    "status": task["status"],
                    "message": result.get("message") or task.get("error") or task["user_instruction"],
                    "timestamp": task.get("completed_at") or task.get("started_at") or task["created_at"],
                    "run_ids": task.get("run_ids", []),
                    "artifact_ids": task.get("artifact_ids", []),
                    "source_channel": task["source_channel"],
                    "task_instruction": task["user_instruction"],
                    "stopped_at": task.get("stopped_at"),
                    "duration_seconds": int((finished - started).total_seconds()) if started and finished else None,
                    "completed_artifact_count": len(task.get("artifact_ids", [])),
                }
            )
        return sorted(entries, key=lambda item: item["timestamp"], reverse=True)[:limit]

    def workspace(self) -> dict[str, Any]:
        approvals = self.approvals()
        stopping = self.tasks.list_tasks(status="cancellation_requested", limit=10)
        running = self.tasks.list_tasks(status="running", limit=10)
        queued = self.tasks.list_tasks(status="queued", limit=10)
        waiting = self.tasks.list_tasks(status="waiting_for_human", limit=10)
        current_task = (stopping or running or queued or waiting or [None])[0]
        current_run = None
        if current_task and current_task.get("run_ids"):
            try:
                current_run = self.generation.get(current_task["run_ids"][0])
            except RepositoryError:
                current_run = None
        return {
            "agent": self.visual.status(),
            "waiting": {key: len(value) for key, value in approvals.items()},
            "recent_work": self.history(8),
            "brain_updates": self.learning.recent_learnings(5),
            "queued_tasks": len(self.tasks.list_tasks(status="queued", limit=500)),
            "running_tasks": len(self.tasks.list_tasks(status="running", limit=500)),
            "stopping_tasks": len(self.tasks.list_tasks(status="cancellation_requested", limit=500)),
            "current_task": current_task,
            "current_run": current_run,
        }

    def _generate_concepts(self, task: dict[str, Any]) -> dict[str, Any]:
        self._checkpoint(task["id"], "Before learning")
        self.emit_event(task, "preparing", "Loading the DINKLY Brain and checking used storylines.")
        mode = "supplemental" if self.concepts.has_primary_batch(self.concepts.local_date()) else "primary"
        source = "scheduled" if task.get("source_channel") == "scheduled" else "manual"
        batch = self.concepts.generate_daily_concept_batch(source=source, mode=mode, execute=True)
        self._checkpoint(task["id"], "After concept generation")
        if batch.get("status") == "skipped":
            result = {
                "message": f"Today's automatic concept run was skipped: {batch['message']}",
                "skipped": True,
                "problems": batch.get("problems", []),
            }
            return self.complete_task(task, result, run_ids=[batch["run"]["id"]])
        batch_id = batch["batch"]["id"]
        requested = int((task.get("context") or {}).get("requested_count") or 10)
        concepts = [item for item in self.concepts.list_concepts() if item.get("batch_id") == batch_id][:requested]
        result = {
            "message": f"I made {len(concepts)} concept{'s' if len(concepts) != 1 else ''}. I put them in your review queue.",
            "batch_id": batch_id,
            "concept_ids": [item["id"] for item in concepts],
            "concepts": concepts,
        }
        return self.request_approval(task, result, run_ids=[batch["run"]["id"]], artifact_ids=result["concept_ids"])

    def _generate_comic(self, task: dict[str, Any]) -> dict[str, Any]:
        context = task.get("context") or {}
        self._checkpoint(task["id"], "Before story brief")
        self.emit_event(task, "preparing", "Building the story brief from the DINKLY Story Library.")
        brief_request = StoryBriefRequest(
            story_id=context.get("story_id"),
            story_brief=context.get("story_brief"),
            concept_text=None if context.get("story_id") or context.get("story_brief") else task["user_instruction"],
        )
        built = self.generation.build_brief(brief_request)
        self._checkpoint(task["id"], "After story brief")
        brief = StoryBrief.model_validate(built["story_brief"])
        model = context.get("model_selection") or "automatic"
        confirm_pro = bool(context.get("confirm_pro"))
        count = max(1, min(int(context.get("candidate_count") or 4), 4))
        run = self.generation.start(
            GenerationRequest(
                story_brief=brief,
                model_selection_mode=model,
                candidate_count=count,
                confirm_pro=confirm_pro,
            )
        )
        task = self.tasks.update(task["id"], run_ids=[run["id"]])
        self.generation.record_source(
            run["id"],
            source_channel=str(task["source_channel"]),
            source_task_id=str(task["id"]),
        )
        self._checkpoint(task["id"], "After prompt compilation and reference loading")
        self._notify_status(task, self._status_message(task, "generating"))
        self.generation.execute(
            run["id"],
            should_cancel=lambda: self.tasks.get(task["id"]).get("status") in {"cancellation_requested", "cancelled"},
            on_progress=lambda progress: self._slack_generation_progress(task, progress),
        )
        self._checkpoint(task["id"], "Before approval preparation")
        run = self.generation.get(run["id"])
        if run["status"] == "failed":
            raise RepositoryError(run.get("error") or "Comic generation failed")
        recommended = next((item for item in run["candidates"] if item.get("recommended")), None)
        artifacts = [item["id"] for item in run["candidates"] if item.get("image_path")]
        result = {
            "message": f"{run['concept_text']} is ready. {('Candidate ' + recommended['label'] + ' is my recommendation.') if recommended else 'Choose the strongest candidate.'}",
            "run_id": run["id"],
            "concept_title": run["concept_text"],
            "recommended_candidate_id": recommended.get("id") if recommended else None,
            "recommended_candidate": recommended,
            "qa_summary": recommended.get("qa_summary") if recommended else "QA completed.",
            "model": recommended.get("model_display_name") if recommended else None,
        }
        return self.request_approval(task, result, run_ids=[run["id"]], artifact_ids=artifacts)

    def _repair_comic(self, task: dict[str, Any]) -> dict[str, Any]:
        context = task.get("context") or {}
        run = self._resolve_generation(context)
        candidate = self._resolve_candidate(run, context.get("candidate_label"))
        self.emit_event(task, "repairing", f"Repairing Candidate {candidate['label']}.")
        failures = [str(item.get("check")) for item in candidate.get("qa_findings", []) if item.get("status") != "Pass"]
        if not failures:
            failures = ["User-requested creative revision"]
        repaired = self.generation.repair(
            candidate["id"],
            RepairRequest(
                failures=failures,
                notes=task["user_instruction"],
                model_selection="pro" if context.get("model_selection") == "pro" else "balanced" if context.get("model_selection") == "balanced" else "same",
                confirm_pro=bool(context.get("confirm_pro")),
            ),
            should_cancel=lambda: self.tasks.get(task["id"]).get("status") in {"cancellation_requested", "cancelled"},
        )
        self._checkpoint(task["id"], "After repair")
        recommended = next((item for item in repaired["candidates"] if item.get("recommended")), None)
        result = {
            "message": f"The repair is ready. {('Candidate ' + recommended['label'] + ' is strongest.') if recommended else 'It is ready for review.'}",
            "run_id": repaired["id"],
            "recommended_candidate": recommended,
            "recommended_candidate_id": recommended.get("id") if recommended else None,
        }
        return self.request_approval(task, result, run_ids=[repaired["id"]])

    def _review_comic(self, task: dict[str, Any]) -> dict[str, Any]:
        run = self._resolve_generation(task.get("context") or {})
        candidate = self._resolve_candidate(run, (task.get("context") or {}).get("candidate_label"))
        self.emit_event(task, "reviewing", f"Reviewing Candidate {candidate['label']}.")
        self._checkpoint(task["id"], "Before QA")
        reviewed = self.generation.qa_candidate(
            candidate["id"],
            should_cancel=lambda: self.tasks.get(task["id"]).get("status") in {"cancellation_requested", "cancelled"},
        )
        self._checkpoint(task["id"], "After QA")
        return self.complete_task(
            task,
            {"message": f"Candidate {candidate['label']} review complete: {reviewed['qa_summary']}", "candidate": reviewed},
            run_ids=[run["id"]],
            artifact_ids=[candidate["id"]],
        )

    def _learn(self, task: dict[str, Any]) -> dict[str, Any]:
        self._checkpoint(task["id"], "Before learning")
        self.emit_event(task, "learning", "Reviewing new production evidence.")
        learned = self.learning.run()
        self._checkpoint(task["id"], "After learning")
        if learned.get("ran"):
            message = f"Learning review complete. I proposed {len(learned.get('learnings', []))} Brain update(s)."
        else:
            message = "Learning check complete. There was no new evidence to process."
        return self.complete_task(task, {"message": message, "learning": learned})

    def _brain_query(self, task: dict[str, Any]) -> dict[str, Any]:
        lower = task["user_instruction"].lower()
        if "waiting" in lower or "approval" in lower:
            pending = self.approvals()
            message = f"You have {len(pending['comics'])} comic, {len(pending['concepts'])} concept, and {len(pending['brain_updates'])} Brain decisions waiting."
            result: dict[str, Any] = {"message": message, "approvals": pending}
        elif "working" in lower:
            running = self.tasks.list_tasks(status="running", limit=10)
            queued = self.tasks.list_tasks(status="queued", limit=10)
            message = f"I am working on {len(running)} assignment(s), with {len(queued)} queued."
            result = {"message": message, "running": running, "queued": queued}
        else:
            learnings = self.learning.recent_learnings(8)
            message = "Here are my latest evidence-linked Brain updates." if learnings else "I do not have a new evidence-backed learning yet."
            result = {"message": message, "learnings": learnings}
        return self.complete_task(task, result)

    def _handle_approval(self, task: dict[str, Any]) -> dict[str, Any]:
        context = task.get("context") or {}
        action = context.get("action")
        item_type = context.get("item_type")
        item_id = context.get("item_id")
        if not item_id:
            recent = context.get("recent_artifact_ids") or context.get("recent_run_ids") or []
            item_id = recent[0] if recent else None
        if not item_id or not action:
            raise RepositoryError("I need a recent item and a clear approval action")
        if item_type == "concept":
            if action == "edit":
                if not context.get("notes"):
                    raise RepositoryError("Describe the concept edit before saving it")
                record = self.concepts.edit(item_id, {"why_it_may_work": context["notes"]})
                return self.complete_task(task, {"message": "Concept edit saved for review.", "concept": record})
            if action == "more_like_this":
                task["context"] = {**context, "recent_artifact_ids": [item_id]}
                task["user_instruction"] = "I love this concept. Give me more like this."
                return self.handle_feedback(task)
            record = (
                self.concepts.approve(item_id)
                if action == "approve"
                else self.concepts.pass_concept(item_id, context.get("notes"))
            )
            return self.complete_task(task, {"message": f"Concept {action.replace('_', ' ')} recorded.", "concept": record})
        if item_type == "brain_update":
            if action == "edit":
                if not context.get("notes"):
                    raise RepositoryError("Enter the revised Brain learning before saving it")
                record = self.update_memory(item_id, "proposed")
                record["statement"] = context["notes"]
                for path in MEMORY_PATHS:
                    records = self.repository.read_json(path, [])
                    if any(item.get("id") == item_id for item in records):
                        self.repository.write_json(path, [record if item.get("id") == item_id else item for item in records])
                        break
                return self.complete_task(task, {"message": "Brain update revision saved for review.", "learning": record})
            record = self.update_memory(item_id, "active" if action == "approve" else "rejected")
            return self.complete_task(task, {"message": f"Brain update {action} recorded.", "learning": record})
        if item_type == "comic":
            run = self.generation.get(item_id)
            if action == "approve":
                if not run.get("selected_candidate_id"):
                    candidate = next((item for item in run["candidates"] if item.get("recommended")), None)
                    if not candidate:
                        raise RepositoryError("Choose a candidate before approval")
                    self.generation.select_candidate(candidate["id"])
                approved = self.generation.approve(item_id, task.get("source_user_id") or "Human reviewer")
                self._complete_source_generation_task(item_id, approved)
                self.tasks.create_task(
                    source_channel="learning",
                    source_thread_id=f"approval-{item_id}",
                    user_instruction=f"Learn from approved generation {item_id}",
                    task_type="learn",
                    dedupe_key=f"learning:approval:{item_id}",
                )
                # Learning stays in the same persisted queue. Running it inline
                # made Slack approval requests block and could orphan the
                # approval task if the HTTP/Socket request ended first.
                return self.complete_task(task, {"message": "Comic approved and saved to History.", "run": approved}, run_ids=[item_id])
            if action in {"pass", "reject"}:
                rejected = self.generation.reject(item_id, context.get("notes"))
                self._complete_source_generation_task(item_id, rejected, decision="passed")
                return self.complete_task(task, {"message": "Comic passed. The candidates remain in History.", "run": rejected}, run_ids=[item_id])
            if action == "more_like_this":
                return self.handle_feedback({**task, "user_instruction": "I love this. Give me more concepts like this."})
            task["context"] = {**context, "recent_run_ids": [item_id]}
            return self._repair_comic(task)
        raise RepositoryError("Unknown approval item type")

    def _complete_source_generation_task(
        self,
        run_id: str,
        approved: dict[str, Any],
        *,
        decision: str = "approved",
    ) -> None:
        """Close the persisted generation task that owns an approved run."""
        source = next(
            (
                candidate
                for candidate in self.tasks.list_tasks(status="waiting_for_human", limit=500)
                if run_id in candidate.get("run_ids", [])
                and candidate.get("task_type") in {"generate_comic", "repair_comic", "review_comic"}
            ),
            None,
        )
        if not source:
            return
        prior = source.get("result") or {}
        message = "Comic approved and saved to History." if decision == "approved" else "Comic passed. The candidates remain in History."
        completed = self.tasks.complete(
            source["id"],
            {**prior, "message": message, "run": approved},
            run_ids=[run_id],
            artifact_ids=source.get("artifact_ids", []),
        )
        event_type = "comic_approved" if decision == "approved" else "comic_passed"
        self.visual.transition(
            "success",
            message,
            source_run_id=source["id"],
            details={"event_type": event_type, "task_id": source["id"], "run_id": run_id},
        )
        self.visual.record_activity(
            "Generation task completed after comic approval.",
            source_run_id=source["id"],
            details={
                "event_type": "task_completed",
                "task_id": completed["id"],
                "run_id": run_id,
                "status": completed["status"],
            },
        )
        if source.get("source_channel") == "slack":
            context = source.get("context") or {}
            message_id = context.get("slack_actions_ts") or context.get("slack_status_ts")
            if message_id:
                try:
                    self._channel(source).update_message(
                        str(message_id),
                        "APPROVED\nComic approved." if decision == "approved" else "PASSED\nComic passed.",
                        channel_id=context.get("slack_channel_id"),
                    )
                except RepositoryError:
                    self.visual.record_activity(
                        "Slack decision update failed; the web decision remains saved.",
                        details={"task_id": source["id"], "run_id": run_id},
                    )

    def _custom(self, task: dict[str, Any]) -> dict[str, Any]:
        raise RepositoryError("I can generate concepts or comics, review and repair artwork, learn, or report what is waiting.")

    def _persist_preference_links(self, preference: dict[str, Any]) -> None:
        records = self.repository.read_json("data/user_preferences.json", [])
        for index, record in enumerate(records):
            if record.get("id") == preference.get("id"):
                records[index] = preference
                self.repository.write_json("data/user_preferences.json", records)
                return

    def _resolve_generation(self, context: dict[str, Any]) -> dict[str, Any]:
        run_ids = context.get("recent_run_ids") or []
        if not run_ids:
            history = self.generation.history()
            if not history:
                raise RepositoryError("There is no recent comic generation to work on")
            return history[0]
        return self.generation.get(run_ids[0])

    @staticmethod
    def _resolve_candidate(run: dict[str, Any], label: str | None) -> dict[str, Any]:
        candidates = [item for item in run.get("candidates", []) if item.get("image_path")]
        if label:
            match = next((item for item in candidates if str(item.get("label", "")).startswith(label)), None)
            if match:
                return match
        selected = next((item for item in candidates if item.get("id") == run.get("selected_candidate_id")), None)
        recommended = next((item for item in candidates if item.get("recommended")), None)
        if selected or recommended or candidates:
            return selected or recommended or candidates[0]
        raise RepositoryError("The recent run has no generated candidate")

    def _global_recent_context(self) -> dict[str, Any]:
        recent = next(
            (
                task
                for task in self.tasks.list_tasks(limit=100)
                if task.get("status") in {"completed", "waiting_for_human"}
                and (task.get("run_ids") or task.get("artifact_ids"))
            ),
            None,
        )
        return {
            "recent_task_id": recent.get("id") if recent else None,
            "recent_run_ids": recent.get("run_ids", []) if recent else [],
            "recent_artifact_ids": recent.get("artifact_ids", []) if recent else [],
            "recent_result": recent.get("result", {}) if recent else {},
        }

    def _channel(self, task: dict[str, Any]) -> AgentChannel:
        if task["source_channel"] == "slack":
            from app.backend.services.slack_service import SlackService

            return SlackService(
                self.repository,
                self.tasks,
                self.receive_instruction,
                self.receive_approval,
            ).channel()
        return WebAgentChannel(self.tasks)

    def _notify_status(self, task: dict[str, Any], message: str) -> None:
        context = task.get("context") or {}
        try:
            channel = self._channel(task)
            if (
                task["source_channel"] == "slack"
                and isinstance(channel, SlackAgentChannel)
                and context.get("slack_status_ts")
                and context.get("slack_task_url")
            ):
                channel.update_buttons(
                    str(context["slack_status_ts"]),
                    message,
                    [self._slack_link_button(task, "See task running", str(context["slack_task_url"]))],
                    channel_id=context.get("slack_channel_id"),
                )
            else:
                channel.send_status(
                    task["source_thread_id"],
                    message,
                    channel_id=context.get("slack_channel_id"),
                    message_id=context.get("slack_status_ts"),
                )
            if task["source_channel"] == "slack":
                from app.backend.services.slack_service import SlackService

                SlackService(
                    self.repository,
                    self.tasks,
                    self.receive_instruction,
                    self.receive_approval,
                )._record_health(last_message_sent=datetime.now(UTC).isoformat())
        except RepositoryError:
            if task["source_channel"] == "slack":
                self.visual.record_activity("Slack delivery failed; the assignment remains saved.", details={"task_id": task["id"]})

    def _slack_generation_progress(self, task: dict[str, Any], progress: dict[str, Any]) -> None:
        if task.get("source_channel") != "slack":
            return
        stage = str(progress.get("stage") or "generate")
        completed = int(progress.get("completed") or 0)
        total = int(progress.get("total") or 4)
        active = {
            "generate": f"● Generating {completed} / {total}\n○ DINKLY layout\n○ QA\n○ Approval",
            "layout": f"✓ Generating {completed} / {total}\n● DINKLY layout\n○ QA\n○ Approval",
            "qa": f"✓ Generating {total} / {total}\n✓ DINKLY layout\n● QA {completed} / {total}\n○ Approval",
            "approval": f"✓ Generating {total} / {total}\n✓ DINKLY layout\n✓ QA {total} / {total}\n● Approval",
        }.get(stage, f"● {stage.replace('_', ' ').title()}")
        self._notify_status(
            self.tasks.get(task["id"]),
            "DINKLY Agent · Working\n\n✓ Story brief\n✓ Prompt compiled\n✓ DINKLY references\n" + active,
        )

    def _deliver_result(self, task: dict[str, Any]) -> None:
        result = task.get("result") or {}
        if task["source_channel"] != "slack":
            self._notify_status(task, self._status_message(task, "finished"))
            self._deliver_proactive(task)
            return
        if task.get("status") != "waiting_for_human":
            self._notify_status(task, self._status_message(task, "finished"))
            return
        channel = self._channel(task)
        context = task.get("context") or {}
        thread_id = task["source_thread_id"]
        channel_id = context.get("slack_channel_id")
        candidate = result.get("recommended_candidate") or {}
        run_id = str(result.get("run_id") or "")
        review_url = self._review_url(run_id) if run_id else None
        ready_message = self._slack_ready_message(result)
        if (
            isinstance(channel, SlackAgentChannel)
            and context.get("slack_status_ts")
            and review_url
        ):
            with suppress(RepositoryError):
                channel.update_buttons(
                    str(context["slack_status_ts"]),
                    ready_message,
                    [self._slack_link_button(task, "View comic", review_url, item_type="comic", item_id=run_id)],
                    channel_id=channel_id,
                )
        else:
            self._notify_status(task, ready_message)
        image_details = " · ".join(
            value for value in (str(result.get("model") or ""), str(result.get("qa_summary") or "")) if value
        )
        delivery_status = "failed"
        delivery_error: str | None = None
        final_path = candidate.get("final_image_path") or candidate.get("image_path")
        if isinstance(channel, SlackAgentChannel) and final_path:
            try:
                channel.send_file(
                    thread_id,
                    self.repository.path(str(final_path)),
                    result.get("concept_title") or "DINKLY comic",
                    channel_id=channel_id,
                    details=image_details or None,
                )
                delivery_status = "image_sent"
            except (RepositoryError, OSError) as exc:
                delivery_error = self._slack_delivery_issue(str(exc))
        if delivery_status == "failed":
            image_url = public_asset_url(
                settings.public_base_url,
                str(candidate.get("final_asset_url") or candidate.get("asset_url") or ""),
            )
            if image_url:
                try:
                    channel.send_image(
                        thread_id,
                        image_url,
                        result.get("concept_title") or "DINKLY candidate",
                        channel_id=channel_id,
                        details=image_details or None,
                    )
                    delivery_status = "link_sent"
                    delivery_error = None
                except RepositoryError as exc:
                    delivery_error = self._slack_delivery_issue(str(exc))
        self.tasks.update(
            task["id"],
            result={
                **result,
                "slack_delivery_status": delivery_status,
                **({"slack_delivery_issue": delivery_error} if delivery_error else {}),
            },
        )
        if run_id:
            with suppress(RepositoryError):
                self.generation.record_slack_delivery(run_id, status=delivery_status, issue=delivery_error)
        if delivery_status == "failed":
            self.visual.record_activity(
                "Slack image delivery failed; the comic remains ready in DINKLY.",
                source_run_id=task["id"],
                details={"task_id": task["id"], "run_id": run_id, "slack_delivery_status": "failed"},
            )
        if result.get("run_id"):
            value = json.dumps(
                {
                    "item_type": "comic",
                    "item_id": result["run_id"],
                    "task_id": task["id"],
                    "candidate_id": result.get("recommended_candidate_id"),
                    "workspace_id": self._slack_workspace_id(),
                }
            )
            try:
                delivered = channel.send_buttons(
                    thread_id,
                    ("Comic is ready.\n\n" if delivery_status == "failed" else "") + self._slack_result_summary({**result, "slack_delivery_status": delivery_status}),
                    [
                        {"label": "Approve", "action_id": "dinkly_approve", "value": value, "style": "primary"},
                        {"label": "Pass", "action_id": "dinkly_pass", "value": value},
                        {"label": "Fix Issues", "action_id": "dinkly_fix", "value": value},
                        {
                            "label": "Open in DINKLY",
                            "action_id": "dinkly_open_comic",
                            "value": value,
                            **({"url": review_url} if review_url else {}),
                        },
                    ],
                    channel_id=channel_id,
                )
                if delivered.get("ts"):
                    self.tasks.update(task["id"], context={**context, "slack_actions_ts": delivered["ts"]})
            except RepositoryError as exc:
                current = self.tasks.get(task["id"])
                current_result = current.get("result") or {}
                self.tasks.update(
                    task["id"],
                    result={
                        **current_result,
                        "slack_delivery_status": "failed",
                        "slack_delivery_issue": self._slack_delivery_issue(str(exc)),
                    },
                )
        elif result.get("concept_ids"):
            first = result["concept_ids"][0]
            concept_value = json.dumps({"item_type": "concept", "item_id": first})
            channel.send_buttons(
                thread_id,
                result["message"],
                [
                    {"label": "Approve first", "action_id": "dinkly_approve", "value": concept_value, "style": "primary"},
                    {"label": "Pass first", "action_id": "dinkly_pass", "value": concept_value},
                    {"label": "More Like This", "action_id": "dinkly_more_like_this", "value": concept_value},
                    {
                        "label": "Open Batch",
                        "action_id": "dinkly_open_batch",
                        "value": concept_value,
                        **({"url": f"{settings.app_url.rstrip('/')}/approvals?concept_id={first}"} if settings.app_url else {}),
                    },
                ],
                channel_id=channel_id,
            )

    def _deliver_failure(self, task: dict[str, Any]) -> None:
        if task.get("source_channel") != "slack":
            return
        context = task.get("context") or {}
        value = json.dumps({"item_type": "task", "task_id": task["id"], "workspace_id": self._slack_workspace_id()})
        buttons = [{"label": "Retry", "action_id": "dinkly_retry_task", "value": value, "style": "primary"}]
        review_url = self._review_url(str(task.get("run_ids", [""])[0])) if task.get("run_ids") else (
            f"{settings.app_url.rstrip('/')}/history" if settings.app_url else None
        )
        if review_url:
            buttons.append({"label": "Open in DINKLY", "action_id": "dinkly_open_task", "value": value, "url": review_url})
        try:
            self._channel(task).send_buttons(
                task["source_thread_id"],
                f"DINKLY hit an issue while generating this comic.\n\n{self._slack_failure_reason(str(task.get('error') or 'generation failed'))}",
                buttons,
                channel_id=context.get("slack_channel_id"),
            )
        except RepositoryError:
            return

    @staticmethod
    def _slack_failure_reason(message: str) -> str:
        lower = message.lower()
        if "quota" in lower or "rate limit" in lower:
            return "Gemini quota reached"
        if "timeout" in lower or "timed out" in lower:
            return "Nano Banana timeout"
        if "gemini_api_key" in lower or "api key" in lower:
            return "API key unavailable"
        if "layout" in lower:
            return "Layout failed"
        if "qa" in lower:
            return "QA failed"
        if "cancel" in lower:
            return "Task cancelled"
        return "Generation failed"

    @staticmethod
    def _slack_delivery_issue(message: str) -> str:
        """Return an actionable Slack delivery reason without exposing secrets or URLs."""
        lower = message.lower()
        api_error = re.search(r"slack api error:\s*([a-z0-9_]+)", lower)
        if api_error:
            return f"Slack API error: {api_error.group(1)}"
        http_error = re.search(r"slack api http error:\s*(\d{3})", lower)
        if http_error:
            return f"Slack API HTTP error: {http_error.group(1)}"
        if "image file is unavailable" in lower or "file is unavailable" in lower:
            return "Final image file unavailable"
        if "certificate" in lower or "tls" in lower:
            return "Slack TLS verification failed"
        if "dns" in lower:
            return "Slack API DNS lookup failed"
        if "timeout" in lower or "timed out" in lower:
            return "Slack image upload timed out"
        if "upload destination" in lower:
            return "Slack did not provide an image upload destination"
        if "backend" in lower or "unavailable" in lower:
            return "Slack API unavailable"
        return "Slack image upload failed"

    @staticmethod
    def _review_url(run_id: str) -> str | None:
        return f"{settings.app_url.rstrip('/')}/comics/{run_id}" if settings.app_url else None

    def _slack_link_button(
        self,
        task: dict[str, Any],
        label: str,
        url: str,
        *,
        item_type: str = "task",
        item_id: str | None = None,
    ) -> dict[str, str]:
        return {
            "label": label,
            "action_id": "dinkly_open_comic" if item_type == "comic" else "dinkly_open_task",
            "value": json.dumps(
                {
                    "item_type": item_type,
                    "item_id": item_id,
                    "task_id": task["id"],
                    "workspace_id": self._slack_workspace_id(),
                }
            ),
            "url": url,
        }

    @staticmethod
    def _slack_ready_message(result: dict[str, Any]) -> str:
        candidate = result.get("recommended_candidate") or {}
        label = str(candidate.get("label") or "").removeprefix("Candidate ")
        recommended = f"\nRecommended: Candidate {label}" if label else ""
        return (
            "DINKLY Agent · Ready for you\n\n"
            "✓ Story\n✓ Generation\n✓ DINKLY layout\n✓ QA"
            f"{recommended}"
        )

    @staticmethod
    def _slack_result_summary(result: dict[str, Any]) -> str:
        candidate = result.get("recommended_candidate") or {}
        model = str(result.get("model") or candidate.get("model_display_name") or "Nano Banana")
        power = str(candidate.get("model_power_label") or "BALANCED")
        qa = str(candidate.get("qa_status") or result.get("qa_summary") or "Completed")
        label = str(candidate.get("label") or "")
        summary = (
            f"*{result.get('concept_title') or 'DINKLY comic'}*\n\n"
            f"{power} · {model}\n\nQA: {qa}"
        )
        return f"{summary}\nDINKLY recommends Candidate {label}." if label else summary

    def _slack_workspace_id(self) -> str | None:
        from app.backend.services.slack_service import SlackService

        return SlackService(self.repository, self.tasks, self.receive_instruction, self.receive_approval).status().get("workspace_id")

    def _deliver_proactive(self, task: dict[str, Any]) -> None:
        context = task.get("context") or {}
        proactive = task["source_channel"] in {"scheduled", "learning"} or bool(context.get("notify_slack"))
        if not proactive:
            return
        from app.backend.services.slack_service import SlackService

        slack = SlackService(self.repository, self.tasks, self.receive_instruction, self.receive_approval)
        slack_state = slack.status()
        if not slack_state["connected"] or not slack_state.get("default_channel"):
            return
        notification_key = "generation_failed" if task.get("status") == "failed" else {
            "generate_concepts": "daily_concepts_ready",
            "generate_comic": "comic_ready_for_approval",
            "learn": "meaningful_new_learning",
        }.get(task["task_type"])
        if notification_key and not slack_state["notifications"].get(notification_key, False):
            return
        slack.channel().send_message("", (task.get("result") or {}).get("message", "DINKLY Agent work updated."))

    def _append_agent_message(self, task: dict[str, Any], message: str) -> None:
        if task["source_channel"] not in {"web", "slack"}:
            return
        self.tasks.append_message(
            channel=task["source_channel"],
            thread_id=task["source_thread_id"],
            role="agent",
            message=message,
            linked_task_ids=[task["id"]],
            linked_run_ids=task.get("run_ids", []),
            linked_artifact_ids=task.get("artifact_ids", []),
        )

    @staticmethod
    def _acknowledgement(task_type: str) -> str:
        return {
            "generate_concepts": "I added the concept assignment to my work queue.",
            "generate_comic": "I added the comic assignment to my work queue.",
            "repair_comic": "I added the repair to my work queue.",
            "feedback": "I added your feedback to my learning queue.",
        }.get(task_type, "I added this to my work queue.")

    @staticmethod
    def _status_message(task: dict[str, Any], stage: str) -> str:
        if stage == "started":
            return f"DINKLY Agent · Started\n● {task['user_instruction']}"
        if stage == "generating":
            return "DINKLY Agent · Generating\n✓ Story brief\n✓ Prompt compiled\n✓ References loaded\n● Generating candidates\n○ QA\n○ Human review"
        marker = "Ready for you" if task.get("status") == "waiting_for_human" else "Complete" if task.get("status") == "completed" else "Needs attention"
        return f"DINKLY Agent · {marker}\n{(task.get('result') or {}).get('message') or task.get('error') or 'Assignment updated.'}"

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = " ".join(str(exc).split()) or type(exc).__name__
        return message[:500]
