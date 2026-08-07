from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from app.backend.models.dinkly_agent import AgentVisualState, ExpressionState
from app.backend.services.repository_service import RepositoryError, RepositoryService

STATE_PATH = "app-data/dinkly-agent/state.json"
EVENTS_PATH = "app-data/dinkly-agent/events.json"
CHAT_PATH = "app-data/dinkly-agent/chat.json"
CHECKPOINT_PATH = "app-data/dinkly-agent/learning-checkpoint.json"
SETTINGS_PATH = "app-data/dinkly-agent/settings.json"
GENERATION_LEARNINGS_PATH = "data/generation_learnings.json"
PROMPT_LEARNINGS_PATH = "data/prompt_learnings.json"
QA_LEARNINGS_PATH = "data/qa_learnings.json"
USER_PREFERENCES_PATH = "data/user_preferences.json"

ACTIVE_STATES = {"learning", "preparing", "generating", "reviewing", "repairing"}
EXPRESSION_STATES = {"idle", "learning", "generating", "reviewing", "repairing", "waiting", "success", "error"}

STATE_PRESENTATION: dict[str, dict[str, str]] = {
    "idle": {"status": "ONLINE", "status_kind": "Idle", "message": "Ready when you are."},
    "learning": {"status": "LEARNING", "status_kind": "Active", "message": "Reviewing new production evidence."},
    "preparing": {"status": "PREPARING", "status_kind": "Active", "message": "Building the story brief."},
    "generating": {"status": "GENERATING", "status_kind": "Active", "message": "Creating DINKLY candidates."},
    "reviewing": {"status": "REVIEWING", "status_kind": "Active", "message": "Checking character consistency."},
    "repairing": {"status": "FIXING", "status_kind": "Active", "message": "Applying a targeted repair."},
    "waiting_for_human": {"status": "WAITING FOR YOU", "status_kind": "Waiting", "message": "A candidate is ready for approval."},
    "success": {"status": "DONE", "status_kind": "Idle", "message": "Comic approved."},
    "error": {"status": "NEEDS ATTENTION", "status_kind": "Warning", "message": "The current task needs attention."},
}


class AgentVisualStateService:
    """Single source of truth for the one visible DINKLY Agent's truthful visual state."""

    _lock = threading.RLock()

    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self._ensure_files()

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = self.repository.read_json(STATE_PATH, {}) or self._idle_state()
            expires_at = self._parse_datetime(state.get("expires_at"))
            if expires_at and datetime.now(UTC) >= expires_at:
                state = self._persist_state("idle", STATE_PRESENTATION["idle"]["message"], emit=False)
            return {**state, "expression": self.expression_for(str(state.get("state", "idle")))}

    def transition(
        self,
        state: AgentVisualState,
        message: str | None = None,
        *,
        source_run_id: str | None = None,
        source_event_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            current = self.repository.read_json(STATE_PATH, {})
            if source_event_id and current.get("source_event_id") == source_event_id:
                return self.status()
            return self._persist_state(
                state,
                message or STATE_PRESENTATION[state]["message"],
                source_run_id=source_run_id,
                source_event_id=source_event_id,
                details=details,
                emit=True,
            )

    def handle_generation_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Map persisted backend events centrally; UI components never interpret raw stages."""
        data = event.get("data") or {}
        stage = data.get("stage")
        stage_status = data.get("status")
        kind = str(event.get("kind", ""))
        level = str(event.get("level", "info"))
        state: AgentVisualState | None = None

        if kind == "approval" or (stage == "human_review" and stage_status == "complete"):
            state = "success"
        elif level == "error" or (kind == "warning" and data.get("code")) or stage_status == "failed":
            state = "error"
        elif stage == "human_review" and stage_status == "active":
            state = "waiting_for_human"
        elif stage == "repair" and stage_status == "active":
            state = "repairing"
        elif (stage == "repair" and stage_status == "complete") or (
            stage == "qa" and stage_status in {"active", "complete"}
        ):
            state = "reviewing"
        elif stage == "generate" and stage_status in {"active", "complete", "warning"}:
            state = "generating"
        elif stage in {"story", "compile", "references"} and stage_status in {"active", "complete"}:
            state = "preparing"
        elif kind == "rejection":
            state = "idle"

        if state is None:
            self.record_activity(
                message=str(event.get("message", "Generation activity recorded.")),
                source_run_id=event.get("run_id"),
                source_event_id=event.get("id"),
                details={"kind": kind, **data},
            )
            return self.status()
        return self.transition(
            state,
            str(event.get("message") or STATE_PRESENTATION[state]["message"]),
            source_run_id=event.get("run_id"),
            source_event_id=event.get("id"),
            details={"kind": kind, **data},
        )

    def record_activity(
        self,
        message: str,
        *,
        source_run_id: str | None = None,
        source_event_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = self.status()
        return self._append_event(
            str(current["state"]),
            message,
            source_run_id=source_run_id,
            source_event_id=source_event_id,
            details=details,
        )

    def events(self, after: str | None = None, *, limit: int = 100) -> list[dict[str, Any]]:
        records = self.repository.read_json(EVENTS_PATH, [])
        if after:
            for index, record in enumerate(records):
                if record.get("id") == after:
                    records = records[index + 1 :]
                    break
        return records[-max(1, min(limit, 250)) :]

    def expression_for(self, state: str) -> dict[str, Any]:
        expression_state = "waiting" if state == "waiting_for_human" else "idle" if state == "preparing" else state
        if expression_state not in EXPRESSION_STATES:
            expression_state = "idle"
        relative = f"app/frontend/public/agents/dinkly-agent/{expression_state}.png"
        asset = self.repository.path(relative)
        exists = asset.is_file()
        return {
            "state": expression_state,
            "custom": exists,
            "path": f"/agents/dinkly-agent/{expression_state}.png" if exists else "/agents/social-intelligence.png",
            "fallback_path": "/agents/social-intelligence.png",
            "version": str(asset.stat().st_mtime_ns) if exists else "canonical",
        }

    def expressions(self) -> list[dict[str, Any]]:
        return [self.expression_for(state) for state in sorted(EXPRESSION_STATES)]

    def save_expression(self, state: ExpressionState, content: bytes) -> dict[str, Any]:
        if state not in EXPRESSION_STATES:
            raise RepositoryError("Unknown DINKLY Agent expression state")
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RepositoryError("DINKLY Agent expressions must be PNG images")
        if len(content) > self.repository.settings.max_upload_bytes:
            raise RepositoryError("DINKLY Agent expression exceeds the local upload limit")
        target = self.repository.path(f"app/frontend/public/agents/dinkly-agent/{state}.png")
        backup = self.repository.atomic_write_bytes(target, content)
        return {**self.expression_for(state), "backup": backup}

    def settings(self) -> dict[str, Any]:
        defaults = {"learning_interval_minutes": 60, "auto_apply_safe_learnings": False, "maximum_task_runtime_seconds": None}
        return {**defaults, **self.repository.read_json(SETTINGS_PATH, {})}

    def update_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        updated = {**self.settings(), **changes, "updated_at": datetime.now(UTC).isoformat()}
        self.repository.write_json(SETTINGS_PATH, updated)
        return updated

    def _persist_state(
        self,
        state: AgentVisualState,
        message: str,
        *,
        source_run_id: str | None = None,
        source_event_id: str | None = None,
        details: dict[str, Any] | None = None,
        emit: bool,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        presentation = STATE_PRESENTATION[state]
        expires_at = now + timedelta(seconds=3.5) if state == "success" else None
        record = {
            "state": state,
            "status": presentation["status"],
            "status_kind": presentation["status_kind"],
            "message": message,
            "last_event": message,
            "last_event_at": now.isoformat(),
            "source_run_id": source_run_id,
            "source_event_id": source_event_id,
            "details": details or {},
            "expires_at": expires_at.isoformat() if expires_at else None,
            "updated_at": now.isoformat(),
        }
        self.repository.write_json(STATE_PATH, record)
        if emit:
            self._append_event(
                state,
                message,
                source_run_id=source_run_id,
                source_event_id=source_event_id,
                details=details,
            )
        return {**record, "expression": self.expression_for(state)}

    def _append_event(
        self,
        state: str,
        message: str,
        *,
        source_run_id: str | None,
        source_event_id: str | None,
        details: dict[str, Any] | None,
    ) -> dict[str, Any]:
        records = self.repository.read_json(EVENTS_PATH, [])
        if source_event_id and any(item.get("source_event_id") == source_event_id for item in records[-500:]):
            return next(item for item in reversed(records) if item.get("source_event_id") == source_event_id)
        event = {
            "id": f"dinkly-event-{uuid.uuid4().hex[:12]}",
            "state": state,
            "message": message,
            "source_run_id": source_run_id,
            "source_event_id": source_event_id,
            "details": details or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        records.append(event)
        self.repository.write_json(EVENTS_PATH, records[-2000:])
        return event

    def _ensure_files(self) -> None:
        defaults: dict[str, Any] = {
            STATE_PATH: self._idle_state(),
            EVENTS_PATH: [],
            CHAT_PATH: [],
            SETTINGS_PATH: {"learning_interval_minutes": 60, "auto_apply_safe_learnings": False},
            GENERATION_LEARNINGS_PATH: [],
            PROMPT_LEARNINGS_PATH: [],
            QA_LEARNINGS_PATH: [],
            USER_PREFERENCES_PATH: [],
        }
        for relative, payload in defaults.items():
            if not self.repository.path(relative).exists():
                self.repository.write_json(relative, payload, create_backup=False)

    @staticmethod
    def _idle_state() -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        return {
            "state": "idle",
            "status": "ONLINE",
            "status_kind": "Idle",
            "message": "Ready when you are.",
            "last_event": "Ready when you are.",
            "last_event_at": now,
            "source_run_id": None,
            "source_event_id": None,
            "details": {},
            "expires_at": None,
            "updated_at": now,
        }

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None


class DinklyLearningLoop:
    """Local, checkpointed production learning. It never calls an image or language provider."""

    _lock = threading.Lock()

    def __init__(self, repository: RepositoryService, visual: AgentVisualStateService) -> None:
        self.repository = repository
        self.visual = visual
        self._initialize_checkpoint()

    def run_due(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        checkpoint = self.repository.read_json(CHECKPOINT_PATH, {})
        last = AgentVisualStateService._parse_datetime(checkpoint.get("last_checked_at"))
        interval = timedelta(minutes=int(self.visual.settings()["learning_interval_minutes"]))
        if last and now - last < interval:
            return {"ran": False, "reason": "not_due", "next_check_at": (last + interval).isoformat()}
        return self.run(now=now)

    def run(self, *, now: datetime | None = None, force: bool = False) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        if not self._lock.acquire(blocking=False):
            return {"ran": False, "reason": "already_running", "provider_calls": 0}
        try:
            evidence = self._collect_evidence()
            checkpoint = self.repository.read_json(CHECKPOINT_PATH, {})
            seen = set(checkpoint.get("seen_evidence_ids", []))
            changed = [item for item in evidence if item["id"] not in seen]
            if not changed and not force:
                self._save_checkpoint(evidence, now)
                return {"ran": False, "reason": "no_changes", "provider_calls": 0, "new_evidence": 0}

            counts = Counter(item["kind"] for item in changed)
            summary = ", ".join(f"{value} {key.replace('_', ' ')}" for key, value in sorted(counts.items()))
            self.visual.transition(
                "learning",
                f"Reviewing {summary or 'new production evidence'}.",
                details={"counts": dict(counts), "learning_job": True},
            )
            self.visual.record_activity(
                f"Loaded {len(changed)} new evidence records.",
                details={"counts": dict(counts), "learning_job": True},
            )
            learnings = self._analyze(changed, now)
            for learning in learnings:
                self._upsert_learning(learning)
                self.visual.record_activity(
                    learning["statement"],
                    details={"learning_id": learning["id"], "learning_type": learning["learning_type"]},
                )
            if not learnings:
                self.visual.record_activity(
                    "No production rule change was supported by the new evidence.",
                    details={"learning_job": True},
                )
            self._save_checkpoint(evidence, now)
            message = f"Learning review complete. Proposed {len(learnings)} concrete update{'s' if len(learnings) != 1 else ''}."
            self.visual.transition("success", message, details={"learning_ids": [item["id"] for item in learnings]})
            return {
                "ran": True,
                "reason": "new_evidence",
                "provider_calls": 0,
                "new_evidence": len(changed),
                "counts": dict(counts),
                "learnings": learnings,
            }
        finally:
            self._lock.release()

    def save_chat_preference(self, message: str) -> dict[str, Any]:
        cleaned = " ".join(message.strip().split())
        if len(cleaned) < 2:
            raise RepositoryError("Tell DINKLY what you want it to learn")
        self.visual.transition("learning", "Saving your feedback.", details={"chat_feedback": True})
        topic, direction, statement, reply = self._parse_preference(cleaned)
        now = datetime.now(UTC).isoformat()
        evidence_id = f"chat-{hashlib.sha256(cleaned.lower().encode()).hexdigest()[:16]}"
        record = {
            "id": f"preference-{uuid.uuid4().hex[:12]}",
            "learning_type": "user_preference",
            "statement": statement,
            "evidence_ids": [evidence_id],
            "confidence": "high",
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "topic": topic,
            "direction": direction,
            "source": "dinkly_agent_chat",
        }
        saved = self._upsert_learning(record)
        chat = self.repository.read_json(CHAT_PATH, [])
        chat.extend(
            [
                {"id": f"chat-{uuid.uuid4().hex[:12]}", "role": "user", "message": cleaned, "created_at": now},
                {"id": f"chat-{uuid.uuid4().hex[:12]}", "role": "agent", "message": reply, "created_at": now},
            ]
        )
        self.repository.write_json(CHAT_PATH, chat[-200:])
        self.visual.record_activity(reply, details={"preference_id": saved["id"], "chat_feedback": True})
        self.visual.transition("success", reply, details={"preference_id": saved["id"]})
        return {"preference": saved, "reply": reply, "state": self.visual.status()}

    def chat(self) -> list[dict[str, Any]]:
        return self.repository.read_json(CHAT_PATH, [])

    def recent_learnings(self, limit: int = 12) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in (GENERATION_LEARNINGS_PATH, PROMPT_LEARNINGS_PATH, QA_LEARNINGS_PATH, USER_PREFERENCES_PATH):
            records.extend(self.repository.read_json(path, []))
        return sorted(records, key=lambda item: item.get("updated_at", ""), reverse=True)[:limit]

    def _collect_evidence(self) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for relative in self.repository.list_json(
            "app-data/generation-engine/runs", suffix="/metadata.json"
        ):
            run = self.repository.read_json(relative, {})
            run_id = str(run.get("id"))
            if run.get("status") == "approved":
                evidence.append({"id": f"approval:{run_id}:{run.get('approved_at')}", "kind": "approval", "run": run})
            if run.get("status") == "rejected":
                evidence.append({"id": f"rejection:{run_id}:{run.get('completed_at')}", "kind": "rejection", "run": run})
            for candidate in run.get("candidates", []):
                candidate_id = str(candidate.get("id"))
                for finding in candidate.get("qa_findings", []):
                    if finding.get("status") in {"Warning", "Fail"}:
                        check = str(finding.get("check", "QA issue"))
                        evidence.append(
                            {
                                "id": f"qa:{candidate_id}:{self._fingerprint(finding)}",
                                "kind": "qa_failure",
                                "run": run,
                                "candidate": candidate,
                                "finding": finding,
                                "check": check,
                            }
                        )
                if candidate.get("repair_parent_id"):
                    evidence.append(
                        {
                            "id": f"repair:{candidate_id}:{candidate.get('created_at') or candidate.get('repair_number')}",
                            "kind": "repair_history",
                            "run": run,
                            "candidate": candidate,
                        }
                    )
        for index, record in enumerate(self.repository.read_json("data/used_storylines.json", [])):
            evidence.append({"id": f"used:{record.get('id') or index}:{record.get('date_used')}", "kind": "used_storyline", "record": record})
        for index, record in enumerate(self.repository.read_json("data/content_feedback.json", [])):
            evidence.append({"id": f"feedback:{record.get('id') or index}:{self._fingerprint(record)}", "kind": "explicit_feedback", "record": record})
        for index, record in enumerate(self.repository.read_json("data/social_posts.json", [])):
            metric_fingerprint = self._fingerprint({key: record.get(key) for key in ("views", "shares", "likes", "comments", "saves", "follows_generated")})
            evidence.append({"id": f"performance:{record.get('id') or index}:{metric_fingerprint}", "kind": "performance_data", "record": record})
        return evidence

    def _analyze(self, changed: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        qa = [item for item in changed if item["kind"] == "qa_failure"]
        checks = Counter(self._normalize_issue(item["check"]) for item in qa)
        for issue, count in checks.most_common(3):
            ids = [item["id"] for item in qa if self._normalize_issue(item["check"]) == issue]
            confidence = "high" if count >= 4 else "medium" if count >= 2 else "low"
            output.append(
                self._learning(
                    "failure_pattern",
                    f"{count} recent generation{'s' if count != 1 else ''} produced {issue}.",
                    ids,
                    confidence,
                    now,
                )
            )
        approvals = [item for item in changed if item["kind"] == "approval"]
        if approvals:
            simple = []
            for item in approvals:
                brief = item["run"].get("story_brief") or {}
                props = set((brief.get("left_props") or []) + (brief.get("right_props") or []))
                if len(props) <= 3:
                    simple.append(item)
            if simple:
                output.append(
                    self._learning(
                        "generation_preference",
                        f"{len(simple)} newly approved comic{'s' if len(simple) != 1 else ''} used restrained scenes with three or fewer distinct props.",
                        [item["id"] for item in simple],
                        "medium" if len(simple) >= 2 else "low",
                        now,
                    )
                )
        couch_rejections = [
            item
            for item in changed
            if item["kind"] in {"rejection", "explicit_feedback"} and "couch" in json.dumps(item, ensure_ascii=False).lower()
        ]
        if couch_rejections:
            output.append(
                self._learning(
                    "user_preference",
                    f"{len(couch_rejections)} new rejection signal{'s' if len(couch_rejections) != 1 else ''} referenced couch concepts; preference remains provisional until reviewed.",
                    [item["id"] for item in couch_rejections],
                    "medium" if len(couch_rejections) >= 2 else "low",
                    now,
                )
            )
        return output

    def _learning(
        self,
        learning_type: str,
        statement: str,
        evidence_ids: list[str],
        confidence: str,
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "id": f"dinkly-learning-{hashlib.sha256(statement.lower().encode()).hexdigest()[:12]}",
            "learning_type": learning_type,
            "statement": statement,
            "evidence_ids": evidence_ids,
            "confidence": confidence,
            "status": "proposed",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    def _upsert_learning(self, learning: dict[str, Any]) -> dict[str, Any]:
        path = {
            "prompt_rule": PROMPT_LEARNINGS_PATH,
            "failure_pattern": QA_LEARNINGS_PATH,
            "layout_rule": QA_LEARNINGS_PATH,
            "character_rule": QA_LEARNINGS_PATH,
            "prop_rule": QA_LEARNINGS_PATH,
            "user_preference": USER_PREFERENCES_PATH,
            "generation_preference": GENERATION_LEARNINGS_PATH,
        }.get(str(learning["learning_type"]), GENERATION_LEARNINGS_PATH)
        records = self.repository.read_json(path, [])
        for index, record in enumerate(records):
            if record.get("id") == learning["id"] or record.get("statement", "").lower() == learning["statement"].lower():
                record["evidence_ids"] = list(dict.fromkeys((record.get("evidence_ids") or []) + learning["evidence_ids"]))
                record["confidence"] = learning["confidence"]
                record["updated_at"] = learning["updated_at"]
                records[index] = record
                self.repository.write_json(path, records)
                return record
        records.append(learning)
        self.repository.write_json(path, records)
        return learning

    def _initialize_checkpoint(self) -> None:
        if self.repository.path(CHECKPOINT_PATH).exists():
            return
        now = datetime.now(UTC)
        self._save_checkpoint(self._collect_evidence(), now)

    def _save_checkpoint(self, evidence: list[dict[str, Any]], now: datetime) -> None:
        self.repository.write_json(
            CHECKPOINT_PATH,
            {
                "last_checked_at": now.isoformat(),
                "seen_evidence_ids": [item["id"] for item in evidence][-10000:],
                "evidence_count": len(evidence),
                "provider_calls": 0,
            },
        )

    @staticmethod
    def _parse_preference(message: str) -> tuple[str, str, str, str]:
        lower = message.lower()
        negative = any(token in lower for token in ("less", "stop", "avoid", "don't", "do not"))
        if "couch" in lower:
            topic = "couch concepts"
        elif "girl" in lower and "alone" in lower:
            topic = "Girl alone on the left"
        elif "prop" in lower and ("big" in lower or "large" in lower):
            topic = "prop scale"
            negative = True
        elif "background" in lower and ("simple" in lower or "simpler" in lower):
            topic = "simple backgrounds"
        elif "cozy" in lower:
            topic = "cozy scenes"
        elif match := re.search(r"candidate\s+([a-z])", lower):
            topic = f"Candidate {match.group(1).upper()} qualities"
        else:
            topic = re.sub(r"\b(i|want|please|more|less|use|make|keep|stop|making)\b", " ", lower)
            topic = " ".join(topic.split()).strip(" .") or "creative direction"
        direction = "less" if negative else "more"
        statement = f"User explicitly requested {direction} emphasis on {topic}."
        reply = f"Got it. I’ll {'reduce' if negative else 'give more weight to'} {topic} in future generation decisions."
        return topic, direction, statement, reply

    @staticmethod
    def _normalize_issue(value: str) -> str:
        cleaned = " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())
        if "mug" in cleaned and ("scale" in cleaned or "size" in cleaned or "oversized" in cleaned):
            return "oversized or inconsistent mug scale"
        return cleaned or "an unspecified QA issue"

    @staticmethod
    def _fingerprint(payload: Any) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]


class DinklyLearningScheduler:
    def __init__(self, loop: DinklyLearningLoop) -> None:
        self.loop = loop

    def run_due(self, now: datetime | None = None) -> dict[str, Any]:
        return self.loop.run_due(now)
