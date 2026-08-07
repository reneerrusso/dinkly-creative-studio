from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.backend.services.cloud_persistence import cloud_database
from app.backend.services.memory_service import PERFORMANCE_PATH, PROPOSALS_PATH, MemoryService
from app.backend.services.repository_service import RepositoryError, RepositoryService

ALLOWED_BRAIN_TARGETS = {
    "CREATIVE_BIBLE.md",
    "CHARACTER_BIBLE.md",
    "STYLE_GUIDE.md",
    "NANO_BANANA_RULES.md",
    "FAILURES.md",
}


class LearningCostGuardrail:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def preflight(self, task_id: str, estimated_cost: float) -> dict[str, Any]:
        configured = self.repository.settings
        now = datetime.now(UTC)
        records = self._records()
        daily = sum(
            float(item.get("reported_cost") or item.get("estimated_cost") or 0)
            for item in records
            if str(item.get("created_at", ""))[:10] == now.date().isoformat()
        )
        monthly = sum(
            float(item.get("reported_cost") or item.get("estimated_cost") or 0)
            for item in records
            if str(item.get("created_at", ""))[:7] == now.strftime("%Y-%m")
        )
        reasons = []
        if estimated_cost > configured.learning_maximum_cost_per_task:
            reasons.append("maximum AI spend per learning task reached")
        if daily + estimated_cost > configured.learning_daily_budget:
            reasons.append("daily learning spend reached")
        if monthly + estimated_cost > configured.learning_monthly_budget:
            reasons.append("monthly learning spend reached")
        return {
            "allowed": not reasons,
            "reasons": reasons,
            "task_id": task_id,
            "estimated_cost": estimated_cost,
            "daily_spend": round(daily, 6),
            "monthly_spend": round(monthly, 6),
        }

    def record(self, task_id: str, estimated_cost: float, reported_cost: float | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        if self.repository.settings.app_mode == "cloud":
            cloud_database(self.repository.settings).upsert(
                "learning_cost_ledger",
                {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "estimated_cost": estimated_cost,
                    "reported_cost": reported_cost,
                    "created_at": now,
                },
            )
            return
        records = self.repository.read_json("app-data/dinkly-agent/learning-cost-ledger.json", [])
        records.append(
            {
                "id": f"learning-cost-{uuid.uuid4().hex[:12]}",
                "task_id": task_id,
                "estimated_cost": estimated_cost,
                "reported_cost": reported_cost,
                "created_at": now,
            }
        )
        self.repository.write_json("app-data/dinkly-agent/learning-cost-ledger.json", records)

    def _records(self) -> list[dict[str, Any]]:
        if self.repository.settings.app_mode == "cloud":
            return cloud_database(self.repository.settings).select(
                "learning_cost_ledger", params={"order": "created_at.desc", "limit": "5000"}
            )
        return self.repository.read_json("app-data/dinkly-agent/learning-cost-ledger.json", [])


class BrainProposalService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if self.repository.settings.app_mode == "cloud":
            params = {"order": "created_at.desc"}
            if status:
                params["status"] = f"eq.{status}"
            return cloud_database(self.repository.settings).select("brain_update_proposals", params=params)
        records = self.repository.read_json(PROPOSALS_PATH, [])
        if status:
            records = [item for item in records if item.get("status") == status]
        return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)

    def get(self, proposal_id: str) -> dict[str, Any]:
        record = next((item for item in self.list() if item.get("id") == proposal_id), None)
        if not record:
            raise RepositoryError("Brain Update Proposal not found")
        return record

    def propose_from_memory(self, memory_id: str, *, target_file: str) -> dict[str, Any]:
        if target_file not in ALLOWED_BRAIN_TARGETS:
            raise RepositoryError("Brain proposal target is not a curated DINKLY Brain file")
        memory = MemoryService(self.repository).get(memory_id)
        evidence = memory.get("evidence_ids") or []
        if len(evidence) < 2:
            raise RepositoryError("A permanent Brain proposal requires at least two evidence records")
        rule = str(memory["summary"])
        record = {
            "id": f"brain-proposal-{hashlib.sha256(f'{target_file}:{rule}'.encode()).hexdigest()[:16]}",
            "title": rule[:100],
            "proposed_rule": rule,
            "target_file": target_file,
            "evidence_ids": evidence,
            "confidence": memory.get("confidence", "low"),
            "status": "pending",
            "edited_rule": None,
            "record_json": {"source_memory_id": memory_id},
            "created_at": datetime.now(UTC).isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "application_status": "not_applied",
            "applied_at": None,
            "applied_commit_sha": None,
        }
        return self._save(record)

    def decide(
        self,
        proposal_id: str,
        *,
        decision: str,
        edited_rule: str | None,
        reviewed_by: str,
    ) -> dict[str, Any]:
        record = self.get(proposal_id)
        if record.get("status") != "pending" and decision != "edit":
            raise RepositoryError("Brain Update Proposal has already been decided")
        now = datetime.now(UTC).isoformat()
        if decision == "edit":
            if not edited_rule or len(edited_rule.strip()) < 4:
                raise RepositoryError("Enter the revised permanent rule")
            record.update(edited_rule=edited_rule.strip(), reviewed_at=now, reviewed_by=reviewed_by)
        elif decision == "reject":
            record.update(status="rejected", reviewed_at=now, reviewed_by=reviewed_by)
        elif decision == "approve":
            rule = (edited_rule or record.get("edited_rule") or record["proposed_rule"]).strip()
            record.update(status="approved", edited_rule=rule, reviewed_at=now, reviewed_by=reviewed_by)
            if self.repository.settings.app_mode == "local":
                self._apply_local(record)
                record.update(application_status="applied_locally", applied_at=now)
            else:
                # Cloud runtimes never mutate Git checkouts. An approved proposal
                # becomes an auditable patch awaiting the CI/Git Brain workflow.
                record["application_status"] = "approved_pending_git"
        else:
            raise RepositoryError("Unknown Brain proposal decision")
        return self._save(record)

    def _apply_local(self, record: dict[str, Any]) -> None:
        target = str(record["target_file"])
        if target not in ALLOWED_BRAIN_TARGETS:
            raise RepositoryError("Brain proposal target is not allowed")
        path = self.repository.path(target)
        content = path.read_text(encoding="utf-8")
        heading = "\n\n## Human-Approved Brain Updates\n"
        if "## Human-Approved Brain Updates" not in content:
            content = content.rstrip() + heading
        content = content.rstrip() + f"\n\n- {record['edited_rule']}\n"
        self.repository.atomic_write_bytes(path, content.encode("utf-8"))

    def _save(self, record: dict[str, Any]) -> dict[str, Any]:
        if self.repository.settings.app_mode == "cloud":
            rows = cloud_database(self.repository.settings).upsert("brain_update_proposals", record)
            return rows[0] if rows else record
        records = self.repository.read_json(PROPOSALS_PATH, [])
        index = next((index for index, item in enumerate(records) if item.get("id") == record["id"]), None)
        if index is None:
            records.append(record)
        else:
            records[index] = record
        self.repository.write_json(PROPOSALS_PATH, records)
        return record


class PerformanceService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def add_snapshot(self, generation_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        record = {
            "id": str(uuid.uuid4()),
            "generation_id": generation_id,
            "captured_at": now,
            **metrics,
        }
        if self.repository.settings.app_mode == "cloud":
            rows = cloud_database(self.repository.settings).upsert("post_performance_snapshots", record)
            return rows[0] if rows else record
        records = self.repository.read_json(PERFORMANCE_PATH, [])
        records.append(record)
        self.repository.write_json(PERFORMANCE_PATH, records)
        return record


class DinklyLearningEngine:
    """Public boundary for proprietary memory, learning, and Brain proposals."""

    def __init__(self, repository: RepositoryService) -> None:
        self.memory = MemoryService(repository)
        self.proposals = BrainProposalService(repository)
        self.performance = PerformanceService(repository)
        self.costs = LearningCostGuardrail(repository)
