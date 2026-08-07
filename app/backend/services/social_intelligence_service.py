from __future__ import annotations

import csv
import io
import json
import threading
import uuid
from datetime import UTC, datetime
from statistics import mean, median
from typing import Any

from pydantic import ValidationError

from app.backend.models.concepts import ConceptCreate
from app.backend.models.social_intelligence import (
    BulkHandleInput,
    ConceptDirectionRequest,
    HandleSelection,
    ManualPostInput,
    MonitoredHandleInput,
    MonitoredHandleUpdate,
    RefreshRequest,
    RunStatus,
)
from app.backend.providers.social_data import (
    ApifyInstagramProvider,
    ApifyTikTokProvider,
    BrightDataProvider,
    CustomProvider,
    ManualImportProvider,
    OfficialInstagramProvider,
    OfficialTikTokProvider,
    ProviderError,
    SocialDataProvider,
)
from app.backend.services.actor_registry_service import ActorRegistry
from app.backend.services.agent_runtime_service import AgentRuntimeService
from app.backend.services.budget_service import BudgetService, BudgetStopped
from app.backend.services.circuit_breaker_service import CircuitBreakerService
from app.backend.services.concept_service import ConceptService
from app.backend.services.creative_classification_service import MetadataClassifier
from app.backend.services.handle_utils import parse_bulk_handles
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.secrets_service import SecretsService

HANDLES_PATH = "data/monitored_handles.json"
PROFILES_PATH = "data/competitor_profiles.json"
POSTS_PATH = "data/competitor_posts.json"
SNAPSHOTS_PATH = "data/competitor_snapshots.json"
LEARNINGS_PATH = "data/competitor_learnings.json"
DIRECTIONS_PATH = "data/competitor_concept_directions.json"


class SocialIntelligenceService:
    _active_lock = threading.RLock()
    _active_providers: dict[str, SocialDataProvider] = {}

    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository
        self.secrets = SecretsService(repository)
        self.actors = ActorRegistry(repository)
        self.budget = BudgetService(repository)
        self.circuit = CircuitBreakerService(repository)
        self.runtime = AgentRuntimeService(repository)
        self.classifier = MetadataClassifier()
        self.concepts = ConceptService(repository)

    def providers(self) -> list[dict[str, Any]]:
        status = self.secrets.get_provider_configuration_status()
        credentials = self.secrets.get_apify_credentials()
        platform_statuses = {
            platform: self.actors.platform_status(platform, credentials[f"APIFY_{platform.upper()}_ACTOR_ID"])
            for platform in ("instagram", "tiktok")
        }
        circuit = self.circuit.state("apify")
        summary = self.budget.usage_summary()
        apify_state = circuit.get("status") if circuit.get("paused") or circuit.get("circuit_state") == "Open" else (
            "Configured" if status["configured"] else "Not configured"
        )
        return [
            {
                **status,
                "platforms": platform_statuses,
                "name": "Apify",
                "state": apify_state,
                "circuit_state": circuit["circuit_state"],
                "paused": circuit["paused"],
                "last_success_at": circuit.get("last_success_at"),
                "last_error_code": circuit.get("last_error_code"),
                "message": circuit["message"] if circuit.get("paused") or circuit["circuit_state"] == "Open" else (
                    "Apify is configured. Test the connection before a paid refresh."
                    if status["configured"]
                    else "Add an Apify API key or use manual import."
                ),
                "budget": summary,
            },
            ManualImportProvider().get_provider_status(),
            OfficialInstagramProvider().get_provider_status(),
            OfficialTikTokProvider().get_provider_status(),
            BrightDataProvider().get_provider_status(),
            CustomProvider().get_provider_status(),
        ]

    def test_apify_connection(self, provider_factory=None) -> dict[str, Any]:
        credentials = self.secrets.get_apify_credentials()
        if provider_factory is not None:
            result = provider_factory(credentials).validate_credentials()
            if result.get("connected"):
                self.circuit.record_success("apify")
            return result
        if not credentials["APIFY_API_TOKEN"]:
            return {
                "connected": False,
                "token": {"status": "Not configured", "connected": False},
                "platforms": {
                    platform: self.actors.verify(platform, "", credentials[f"APIFY_{platform.upper()}_ACTOR_ID"])
                    for platform in ("instagram", "tiktok")
                },
                "message": "Add an Apify API key before testing Actors.",
            }
        factory = provider_factory or (
            lambda values: ApifyInstagramProvider(
                values["APIFY_API_TOKEN"], self.actors.get_effective("instagram", values["APIFY_INSTAGRAM_ACTOR_ID"])["actor_id"]
            )
        )
        result = factory(credentials).validate_credentials()
        platforms = {
            platform: self.actors.verify(platform, credentials["APIFY_API_TOKEN"], credentials[f"APIFY_{platform.upper()}_ACTOR_ID"])
            for platform in ("instagram", "tiktok")
        } if result.get("connected") else {
            platform: {**self.actors.platform_status(platform, credentials[f"APIFY_{platform.upper()}_ACTOR_ID"]), "ready": False, "status": "Not tested", "message": "Token validation failed."}
            for platform in ("instagram", "tiktok")
        }
        if result.get("connected") and any(item["ready"] for item in platforms.values()):
            self.circuit.record_success("apify")
        elif result.get("error_code"):
            error = ProviderError(str(result["error_code"]), str(result.get("message") or "Connection failed"))
            self.circuit.record_error(error, "apify")
        return {
            "connected": bool(result.get("connected")),
            "token": {"status": "Connected" if result.get("connected") else "Unavailable", "connected": bool(result.get("connected")), "message": result.get("message")},
            "platforms": platforms,
            "message": "Apify token checked; platform results are shown separately.",
        }

    def configure_apify(self, token: str, instagram_override: str = "", tiktok_override: str = "", instagram_enabled: bool = True, tiktok_enabled: bool = True) -> dict[str, Any]:
        self.secrets.set_apify_token(token)
        self.actors.validate_override("instagram", token, instagram_override)
        self.actors.validate_override("tiktok", token, tiktok_override)
        status = self.secrets.set_actor_ids(instagram_override, tiktok_override)
        self.actors.set_enabled(instagram_enabled, tiktok_enabled)
        return {"configuration": status, "health": self.test_apify_connection(), "message": "Saved securely. Recommended Actors were checked automatically."}

    def update_actor_settings(self, instagram_override: str = "", tiktok_override: str = "", instagram_enabled: bool = True, tiktok_enabled: bool = True) -> dict[str, Any]:
        token = self.secrets.get_apify_credentials()["APIFY_API_TOKEN"]
        if not token:
            raise RepositoryError("Add an Apify API key before changing Actor overrides")
        self.actors.validate_override("instagram", token, instagram_override)
        self.actors.validate_override("tiktok", token, tiktok_override)
        status = self.secrets.set_actor_ids(instagram_override, tiktok_override)
        self.actors.set_enabled(instagram_enabled, tiktok_enabled)
        return {"configuration": status, "message": "Platform settings saved. Blank overrides use recommended Actors."}

    def list_handles(self) -> list[dict[str, Any]]:
        return self.repository.read_json(HANDLES_PATH, [])

    def add_handle(self, payload: MonitoredHandleInput) -> tuple[dict[str, Any], str | None]:
        records = self.list_handles()
        if any(item.get("platform") == payload.platform.value and item.get("username") == payload.username for item in records):
            raise RepositoryError("This platform and handle are already monitored")
        now = datetime.now(UTC).isoformat()
        record = {
            "id": f"handle-{uuid.uuid4().hex[:12]}",
            "platform": payload.platform.value,
            "username": payload.username,
            "canonical_url": self._profile_url(payload.platform.value, payload.username),
            "display_name": None,
            "category": payload.category.value,
            "enabled": payload.enabled,
            "provider": payload.provider,
            "posts_per_refresh": payload.posts_per_refresh,
            "refresh_frequency": payload.refresh_frequency,
            "last_checked_at": None,
            "last_success_at": None,
            "last_error": None,
            "profile_id": None,
            "profile_image_url": None,
            "follower_count": None,
            "following_count": None,
            "post_count": None,
            "notes": payload.notes,
            "created_at": now,
            "updated_at": now,
        }
        records.append(record)
        backup = self.repository.write_json(
            HANDLES_PATH,
            records,
            schema_relative="schemas/monitored_handle.schema.json",
            validate_each=True,
        )
        return record, backup

    def preview_bulk_handles(self, payload: BulkHandleInput) -> dict[str, Any]:
        records = parse_bulk_handles(payload.text, payload.default_platform.value if payload.default_platform else None)
        existing = {(item["platform"], item["username"]) for item in self.list_handles()}
        return {
            "handles": [
                {
                    **item,
                    "canonical_url": self._profile_url(item["platform"], item["username"]),
                    "duplicate": (item["platform"], item["username"]) in existing,
                    "category": payload.category.value,
                }
                for item in records
            ],
            "count": len(records),
        }

    def add_bulk_handles(self, payload: BulkHandleInput) -> list[dict[str, Any]]:
        preview = self.preview_bulk_handles(payload)
        created: list[dict[str, Any]] = []
        for item in preview["handles"]:
            if item["duplicate"]:
                continue
            handle, _ = self.add_handle(
                MonitoredHandleInput(
                    platform=item["platform"],
                    username=item["username"],
                    category=payload.category,
                )
            )
            created.append(handle)
        return created

    def update_handle(self, handle_id: str, payload: MonitoredHandleUpdate) -> tuple[dict, str | None]:
        records = self.list_handles()
        for index, record in enumerate(records):
            if record.get("id") == handle_id:
                changes = payload.model_dump(mode="json", exclude_none=True)
                if "category" in changes and hasattr(changes["category"], "value"):
                    changes["category"] = changes["category"].value
                updated = {**record, **changes, "updated_at": datetime.now(UTC).isoformat()}
                records[index] = updated
                backup = self.repository.write_json(
                    HANDLES_PATH,
                    records,
                    schema_relative="schemas/monitored_handle.schema.json",
                    validate_each=True,
                )
                return updated, backup
        raise RepositoryError("Monitored handle not found")

    def remove_handle(self, handle_id: str) -> tuple[dict, str | None]:
        records = self.list_handles()
        target = next((item for item in records if item.get("id") == handle_id), None)
        if not target:
            raise RepositoryError("Monitored handle not found")
        backup = self.repository.write_json(
            HANDLES_PATH,
            [item for item in records if item.get("id") != handle_id],
            schema_relative="schemas/monitored_handle.schema.json",
            validate_each=True,
        )
        return target, backup

    def validate_handles(self, payload: HandleSelection) -> list[dict[str, Any]]:
        handles = self._select_handles(payload)
        providers = self._providers_by_platform()
        return [providers[item["platform"]].validate_handle(item["username"]) | {"handle_id": item["id"]} for item in handles]

    def preflight(self, payload: HandleSelection) -> dict[str, Any]:
        handles = self._select_handles(payload)
        if not handles:
            return {
                "handles": 0,
                "platforms": [],
                "maximum_posts": 0,
                "estimated_cost_low": None,
                "estimated_cost_high": None,
                "requires_confirmation": False,
                "can_run": False,
                "warnings": [],
                "hard_stops": ["Add and enable at least one Instagram or TikTok handle."],
            }
        settings = self.budget.get_settings()
        posts = payload.posts_per_handle or min(
            max(int(item.get("posts_per_refresh") or settings.maximum_posts_per_handle) for item in handles),
            settings.maximum_posts_per_handle,
        )
        providers = self._providers_by_platform()
        usage = self.budget.usage()
        estimates: list[dict] = []
        for platform in sorted({item["platform"] for item in handles}):
            count = sum(item["platform"] == platform for item in handles)
            estimates.append(providers[platform].estimate_run_cost(count, posts, usage))
        config = self.secrets.get_provider_configuration_status()
        requested_platforms = {item["platform"] for item in handles}
        actor_ids_ok = all(
            self.actors.get_effective(platform, config["instagram_actor_id"] if platform == "instagram" else config["tiktok_actor_id"])["actor_id"]
            for platform in requested_platforms
        )
        platforms_enabled = all(self.actors.get_default(platform)["enabled"] for platform in requested_platforms)
        circuit = self.circuit.state("apify")
        result = self.budget.preflight(
            handles=handles,
            posts_per_handle=posts,
            estimates=estimates,
            provider_configured=bool(config["configured"] and actor_ids_ok and platforms_enabled),
            provider_state=circuit["circuit_state"] if not circuit["paused"] else "Open",
            scheduled=payload.scheduled,
        )
        result["provider_health"] = (
            "Not tested" if config["configured"] and circuit["status"] == "Not configured" else circuit["status"]
        )
        result["provider_configured"] = config["configured"]
        result["manual_import_available"] = True
        return result

    def start_refresh(self, payload: RefreshRequest) -> dict[str, Any]:
        preflight = self.preflight(payload)
        if not preflight["can_run"]:
            raise RepositoryError(" ".join(preflight["hard_stops"]))
        if preflight["requires_confirmation"] and not payload.confirmed:
            raise RepositoryError("Review and explicitly confirm the estimated provider cost before starting this run.")
        run = self.runtime.create_run("social-intelligence-refresh", payload.model_dump(mode="json"))
        self.runtime.emit(run["id"], "preflight", self._preflight_message(preflight), preflight)
        return {"run": run, "preflight": preflight}

    def execute_refresh(self, run_id: str, payload: RefreshRequest) -> dict[str, Any]:
        handles = self._select_handles(payload)
        preflight = self.preflight(payload)
        summary: dict[str, Any] = {
            "handles_selected": len(handles),
            "handles_processed": 0,
            "posts_fetched": 0,
            "posts_skipped": 0,
            "snapshots_created": 0,
            "metrics_unavailable": 0,
            "estimated_cost": preflight.get("estimated_cost_high"),
            "provider_reported_cost": 0.0,
            "provider_reported_cost_complete": True,
            "learnings_created": 0,
            "concept_directions_created": 0,
        }
        warnings: list[str] = []
        successes: set[str] = set()
        failures: set[str] = set()
        failure_codes: set[str] = set()
        providers = self._providers_by_platform()
        requests_made = 0
        estimate_per_handle = (preflight.get("estimated_cost_high") or 0.0) / max(1, len(handles))
        self.runtime.emit(run_id, "scope", f"Loaded {len(handles)} monitored handles.")
        self.runtime.emit(
            run_id,
            "budget",
            f"Monthly provider budget remaining: ${preflight['monthly_budget_remaining']:.2f}.",
        )
        for handle in handles:
            handle_requests_before = requests_made
            platform = handle["platform"]
            provider = providers[platform]
            with self._active_lock:
                self._active_providers[run_id] = provider

            def guard(
                phase: str,
                active_provider: SocialDataProvider = provider,
                active_platform: str = platform,
            ) -> None:
                nonlocal requests_made
                if self.runtime.is_cancelled(run_id):
                    active_provider.cancel_active_request()
                    raise ProviderError("cancelled", "The run was cancelled.")
                self.budget.check_before_request(estimate_per_handle, request_count=requests_made, phase=phase)
                requests_made += 1
                self.runtime.emit(run_id, "provider-request", f"Starting provider request for {active_platform.title()} ({phase}).")

            if hasattr(provider, "request_guard"):
                provider.request_guard = guard  # type: ignore[attr-defined]
            try:
                self.circuit.ensure_available("apify")
                limit = min(
                    payload.posts_per_handle or int(handle.get("posts_per_refresh") or 20),
                    self.budget.get_settings().maximum_posts_per_handle,
                )
                posts = provider.fetch_recent_posts(handle["username"], limit)
                handle_result = self._store_provider_result(handle, posts, provider)
                summary["handles_processed"] += 1
                summary["posts_fetched"] += handle_result["created"]
                summary["posts_skipped"] += handle_result["skipped"]
                summary["snapshots_created"] += handle_result["snapshots"]
                summary["metrics_unavailable"] += handle_result["metrics_unavailable"]
                successes.add(platform)
                self._mark_handle_success(handle, handle_result.get("profile"))
                usage = provider.get_usage()
                actual = usage.get("actual_cost")
                if actual is None:
                    summary["provider_reported_cost_complete"] = False
                else:
                    summary["provider_reported_cost"] += float(actual)
                self.budget.record_usage(
                    {
                        "provider": "apify",
                        "actor_id": self._actor_id(platform),
                        "run_id": run_id,
                        "estimated_cost_before": round(estimate_per_handle, 4),
                        "actual_cost": actual,
                        "currency": usage.get("currency", "USD"),
                        "requests": requests_made - handle_requests_before,
                        "compute_units": usage.get("compute_units"),
                        "items_returned": len(posts),
                        "handles_processed": 1,
                        "platform": platform,
                        "billing_source": "apify Actor run",
                        "usage_source": usage.get("usage_source", "estimated"),
                        "status": "Completed",
                        "notes": "Provider-reported actual cost is null when Apify did not expose billing for the run.",
                    }
                )
                self.budget.check_after_usage()
                self.circuit.record_success("apify")
                self.runtime.emit(
                    run_id,
                    "fetch",
                    f"Fetched {len(posts)} public posts from @{handle['username']}.",
                    handle_result,
                )
                if handle_result["skipped"]:
                    self.runtime.emit(run_id, "deduplication", f"Skipped {handle_result['skipped']} posts already stored.")
            except BudgetStopped as exc:
                warnings.append(str(exc))
                self.circuit.pause(str(exc), "apify")
                self.runtime.emit(run_id, "budget-stop", str(exc), level="warning")
                with self._active_lock:
                    self._active_providers.pop(run_id, None)
                analysis = self.analyze_existing_data()
                summary.update(analysis)
                return self.runtime.finish(run_id, RunStatus.BUDGET_STOPPED, summary, warnings=warnings)
            except ProviderError as exc:
                failures.add(platform)
                failure_codes.add(exc.code)
                self._mark_handle_error(handle, exc.safe_message)
                state = self.circuit.record_error(exc, "apify")
                warnings.append(f"{platform.title()}: {exc.safe_message}")
                self.runtime.emit(run_id, "provider-warning", exc.safe_message, {"platform": platform, "code": exc.code}, level="warning")
                if exc.code == "cancelled":
                    with self._active_lock:
                        self._active_providers.pop(run_id, None)
                    return self.runtime.finish(run_id, RunStatus.CANCELLED, summary, warnings=warnings)
                if exc.code == "insufficient_credit":
                    self.circuit.pause(exc.safe_message, "apify")
                if exc.code in {"authentication", "insufficient_credit"} or state["circuit_state"] == "Open":
                    break
            except Exception as exc:
                safe = self.secrets.redact(str(exc))
                failures.add(platform)
                warnings.append(f"{platform.title()}: provider operation failed safely.")
                self._mark_handle_error(handle, "Provider operation failed safely.")
                self.runtime.emit(run_id, "provider-warning", "Provider operation failed safely.", {"platform": platform}, level="warning")
                if safe:
                    self.runtime.update(run_id, error="Provider operation failed safely.")
            finally:
                with self._active_lock:
                    self._active_providers.pop(run_id, None)
        analysis = self.analyze_existing_data()
        summary.update(analysis)
        summary["budget_remaining"] = self.budget.usage_summary()["monthly_remaining"]
        if successes and failures:
            self.runtime.emit(
                run_id,
                "partial-success",
                f"{' and '.join(item.title() for item in sorted(successes))} completed successfully. {' and '.join(item.title() for item in sorted(failures))} was unavailable.",
                level="warning",
            )
            status = RunStatus.WARNINGS
        elif successes:
            status = RunStatus.COMPLETED
        elif failures:
            codes = [warning.lower() for warning in warnings]
            if "insufficient_credit" in failure_codes:
                status = RunStatus.BUDGET_STOPPED
            else:
                status = RunStatus.RATE_LIMITED if any("rate limit" in item for item in codes) else RunStatus.PROVIDER_UNAVAILABLE
        else:
            status = RunStatus.FAILED
        return self.runtime.finish(run_id, status, summary, warnings=warnings)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        record = self.runtime.cancel(run_id)
        with self._active_lock:
            provider = self._active_providers.get(run_id)
        if provider:
            provider.cancel_active_request()
        return record

    def list_profiles(self) -> list[dict[str, Any]]:
        return self.repository.read_json(PROFILES_PATH, [])

    def list_posts(self) -> list[dict[str, Any]]:
        posts = self.repository.read_json(POSTS_PATH, [])
        return self._with_performance(posts)

    def get_post(self, post_id: str) -> dict[str, Any]:
        for post in self.list_posts():
            if post.get("id") == post_id:
                post["snapshots"] = self.snapshots(post_id)
                return post
        raise RepositoryError("Competitor post not found")

    def snapshots(self, post_id: str) -> list[dict[str, Any]]:
        return [item for item in self.repository.read_json(SNAPSHOTS_PATH, []) if item.get("post_id") == post_id]

    def add_manual_post(self, payload: ManualPostInput) -> dict[str, Any]:
        handle = self._get_handle(payload.handle_id)
        record = payload.model_dump(mode="json")
        record["platform"] = payload.platform.value
        record["provider"] = "manual_import"
        record["raw_metadata"] = {"source": "manual entry"}
        record["creative_attributes"] = self._classification(record, payload.creative_attributes)
        result = self._upsert_post(handle, record)
        return result

    def import_posts(self, filename: str, content: bytes) -> dict[str, Any]:
        if len(content) > self.repository.settings.max_upload_bytes:
            raise RepositoryError("Import exceeds the configured local upload limit")
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if suffix == "json":
            try:
                payload = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RepositoryError("Invalid JSON import") from exc
            rows = payload if isinstance(payload, list) else payload.get("posts", []) if isinstance(payload, dict) else []
        elif suffix == "csv":
            try:
                rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
            except UnicodeDecodeError as exc:
                raise RepositoryError("CSV import must use UTF-8 text") from exc
        else:
            raise RepositoryError("Manual import supports CSV and JSON files")
        if not isinstance(rows, list):
            raise RepositoryError("Import must contain a list of post records")
        created = skipped = snapshots = 0
        errors: list[str] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"Row {index + 1}: expected an object")
                continue
            try:
                handle = self._manual_handle(row)
                model = ManualPostInput(
                    handle_id=handle["id"],
                    platform=row.get("platform") or handle["platform"],
                    platform_post_id=str(row.get("platform_post_id") or row.get("post_id") or row.get("id") or ""),
                    post_url=self._blank_none(row.get("post_url") or row.get("url")),
                    caption=self._blank_none(row.get("caption")),
                    hashtags=self._list_value(row.get("hashtags")),
                    posted_at=self._blank_none(row.get("posted_at") or row.get("post_date")),
                    media_type=self._blank_none(row.get("media_type")),
                    media_url=self._blank_none(row.get("media_url")),
                    carousel_item_count=self._optional_int(row.get("carousel_item_count")),
                    view_count=self._optional_int(row.get("view_count") if "view_count" in row else row.get("views")),
                    like_count=self._optional_int(row.get("like_count") if "like_count" in row else row.get("likes")),
                    comment_count=self._optional_int(row.get("comment_count") if "comment_count" in row else row.get("comments")),
                    share_count=self._optional_int(row.get("share_count") if "share_count" in row else row.get("shares")),
                    follower_count=self._optional_int(row.get("follower_count") if "follower_count" in row else row.get("followers")),
                    audio_name=self._blank_none(row.get("audio_name")),
                    creative_attributes=row.get("creative_attributes") if isinstance(row.get("creative_attributes"), dict) else {},
                )
                result = self.add_manual_post(model)
                created += int(result["created"])
                skipped += int(result["skipped"])
                snapshots += int(result["snapshots"])
            except (RepositoryError, ValidationError, ValueError) as exc:
                errors.append(f"Row {index + 1}: {self.secrets.redact(str(exc))}")
        return {
            "source": "manual import",
            "fixture": False,
            "rows_received": len(rows),
            "posts_created": created,
            "posts_skipped": skipped,
            "snapshots_created": snapshots,
            "errors": errors,
        }

    def override_classification(self, post_id: str, attributes: dict[str, Any]) -> dict[str, Any]:
        records = self.repository.read_json(POSTS_PATH, [])
        for index, record in enumerate(records):
            if record.get("id") == post_id:
                current = dict(record.get("creative_attributes") or {})
                current.update(attributes)
                current.update(
                    {
                        "classification_source": "manual correction",
                        "classification_confidence": "manual",
                        "manual_override": True,
                    }
                )
                record["creative_attributes"] = current
                record["last_seen_at"] = datetime.now(UTC).isoformat()
                records[index] = record
                self.repository.write_json(
                    POSTS_PATH,
                    records,
                    schema_relative="schemas/competitor_post.schema.json",
                    validate_each=True,
                )
                return record
        raise RepositoryError("Competitor post not found")

    def list_learnings(self) -> list[dict[str, Any]]:
        return self.repository.read_json(LEARNINGS_PATH, [])

    def decide_learning(self, learning_id: str, decision: str, notes: str = "") -> dict[str, Any]:
        records = self.list_learnings()
        for index, record in enumerate(records):
            if record.get("id") == learning_id:
                record.update({"status": decision, "review_notes": notes, "reviewed_at": datetime.now(UTC).isoformat()})
                records[index] = record
                self.repository.write_json(
                    LEARNINGS_PATH,
                    records,
                    schema_relative="schemas/competitor_learning.schema.json",
                    validate_each=True,
                )
                return record
        raise RepositoryError("Competitor learning not found")

    def analyze_existing_data(self) -> dict[str, int]:
        posts = self.list_posts()
        if not posts:
            return {"learnings_created": 0, "concept_directions_created": 0}
        by_activity: dict[str, list[dict]] = {}
        for post in posts:
            activity = (post.get("creative_attributes") or {}).get("activity")
            if activity:
                by_activity.setdefault(str(activity), []).append(post)
        existing = self.list_learnings()
        known_keys = {item.get("pattern_key") for item in existing}
        created: list[dict] = []
        for activity, items in by_activity.items():
            standout = [item for item in items if (item.get("performance") or {}).get("multiplier") and (item["performance"]["multiplier"] >= 1.5)]
            if not standout:
                continue
            key = f"activity:{activity}"
            if key in known_keys:
                continue
            sample_size = len(items)
            confidence = "Medium" if sample_size >= 3 and len(standout) >= 2 else "Low"
            created.append(
                {
                    "id": f"learning-{uuid.uuid4().hex[:12]}",
                    "classification": "Observed pattern",
                    "pattern_key": key,
                    "pattern": f"Public posts about {activity} include {len(standout)} standout result{'s' if len(standout) != 1 else ''} within the monitored account baselines.",
                    "measured_fact": f"{len(standout)} of {sample_size} classified {activity} posts reached at least 1.5× their account median on the available primary metric.",
                    "hypothesis": f"The familiarity of {activity} may make the post easier to recognize and share; the available data does not establish causation.",
                    "recommendation": f"Test an original DINKLY {activity} moment while preserving DINKLY character, caption, layout, and emotional rules.",
                    "data_limitation": "Public metrics vary by platform and unavailable metrics were excluded, not treated as zero.",
                    "confidence": confidence,
                    "sample_size": sample_size,
                    "evidence_post_ids": [item["id"] for item in standout],
                    "status": "Pending",
                    "review_notes": "",
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
        if created:
            records = existing + created
            self.repository.write_json(
                LEARNINGS_PATH,
                records,
                schema_relative="schemas/competitor_learning.schema.json",
                validate_each=True,
            )
        directions = self.generate_directions(ConceptDirectionRequest(learning_ids=[item["id"] for item in created], limit=3)) if created else []
        return {"learnings_created": len(created), "concept_directions_created": len(directions)}

    def list_directions(self) -> list[dict[str, Any]]:
        return self.repository.read_json(DIRECTIONS_PATH, [])

    def generate_directions(self, payload: ConceptDirectionRequest) -> list[dict[str, Any]]:
        learnings = self.list_learnings()
        selected = [item for item in learnings if not payload.learning_ids or item.get("id") in payload.learning_ids]
        existing = self.list_directions()
        known = {item.get("source_learning_id") for item in existing}
        created: list[dict] = []
        palettes = [("warm cream", "muted coral"), ("powder blue", "soft mustard"), ("soft lavender", "warm sage")]
        for learning in selected:
            if learning.get("id") in known or len(created) >= payload.limit:
                continue
            activity = str(learning.get("pattern_key", "activity:quiet moments")).split(":", 1)[-1]
            title = self._original_title(activity)
            background, accent = palettes[len(created) % len(palettes)]
            created.append(
                {
                    "id": f"direction-{uuid.uuid4().hex[:12]}",
                    "source_learning_id": learning["id"],
                    "signal": learning["pattern"],
                    "source_pattern": f"The high-level activity signal is {activity}; no competitor caption, dialogue, layout, or pose is reused.",
                    "reusable_principle": "Use a familiar shared ritual with one clear emotional contrast.",
                    "must_not_copy": "Do not copy exact captions, dialogue, on-screen text, panel layouts, poses, punchlines, character designs, illustration styles, logos, watermarks, or branded artwork.",
                    "dinkly_emotional_angle": f"An ordinary {activity} moment feels warmer because Dinka and Dinko share it.",
                    "title_pair": {"left": title, "right": f"{title} WITH YOU"},
                    "left_character": "boy",
                    "left_scene": f"Boy DINKLY does the ordinary {activity} routine alone on the floor, looking neutral or gently bored.",
                    "right_scene": f"Boy DINKLY and Girl DINKLY share the same {activity} routine together in the same setting, close and warmly connected.",
                    "shared_setting": f"One simple rounded DINKLY environment designed specifically for the {activity} routine.",
                    "purposeful_props": self._props_for(activity),
                    "pastel_background": background,
                    "accent_color": accent,
                    "execution_risks": ["Do not copy the source post composition", "Keep both characters the same size", "No visible legs or human anatomy"],
                    "why_original": "The direction uses only a high-level activity and relationship principle, then rebuilds the story with DINKLY's locked characters and X / X WITH YOU structure.",
                    "why_someone_may_share": f"People may recognize the small relationship ritual of sharing {activity}; this is a creative hypothesis, not a performance prediction.",
                    "supporting_evidence": learning["evidence_post_ids"],
                    "confidence": learning["confidence"],
                    "status": "Draft",
                    "concept_id": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
        if created:
            self.repository.write_json(
                DIRECTIONS_PATH,
                existing + created,
                schema_relative="schemas/competitor_concept_direction.schema.json",
                validate_each=True,
            )
        return created

    def open_direction_in_prompt_builder(self, direction_id: str) -> dict[str, Any]:
        directions = self.list_directions()
        direction = next((item for item in directions if item.get("id") == direction_id), None)
        if not direction:
            raise RepositoryError("Competitor concept direction not found")
        if direction.get("concept_id"):
            return {"concept_id": direction["concept_id"], "href": f"/prompt-builder?concept={direction['concept_id']}"}
        concept, _ = self.concepts.create(
            ConceptCreate(
                format="x-with-you",
                title_pair=direction["title_pair"],
                left_scene=direction["left_scene"],
                right_scene=direction["right_scene"],
                emotional_insight=direction["dinkly_emotional_angle"],
                emotional_theme="companionship",
                category="Everyday routines",
                left_character=direction["left_character"],
                left_character_action=direction["left_scene"],
                left_setting=direction["shared_setting"],
                left_props=direction["purposeful_props"],
                right_character_actions=direction["right_scene"],
                right_setting=direction["shared_setting"],
                right_props=direction["purposeful_props"],
                shared_environment=direction["shared_setting"],
                environmental_contrast="The setting remains the same; emotional warmth and closeness change because the moment is shared.",
                recommended_background_color=direction["pastel_background"],
                recommended_accent_color=direction["accent_color"],
                recommended_camera_angle="medium straight-on",
                why_someone_would_share=direction["why_someone_may_share"],
                props=direction["purposeful_props"],
                execution_risks=direction["execution_risks"],
                novel_angle=direction["why_original"],
                notes=f"Source: Social Intelligence direction {direction_id}. Only high-level public patterns were used.",
            )
        )
        for index, record in enumerate(directions):
            if record.get("id") == direction_id:
                record["concept_id"] = concept["id"]
                record["status"] = "Opened in Prompt Builder"
                directions[index] = record
        self.repository.write_json(
            DIRECTIONS_PATH,
            directions,
            schema_relative="schemas/competitor_concept_direction.schema.json",
            validate_each=True,
        )
        return {"concept_id": concept["id"], "href": f"/prompt-builder?concept={concept['id']}"}

    def _providers_by_platform(self) -> dict[str, SocialDataProvider]:
        credentials = self.secrets.get_apify_credentials()
        settings = self.budget.get_settings()
        common = {
            "connection_timeout": settings.connection_timeout_seconds,
            "read_timeout": settings.read_timeout_seconds,
            "download_timeout": settings.download_timeout_seconds,
            "actor_timeout": settings.actor_run_timeout_seconds,
            "max_retries": settings.maximum_retries,
        }
        return {
            "instagram": ApifyInstagramProvider(
                credentials["APIFY_API_TOKEN"], self.actors.get_effective("instagram", credentials["APIFY_INSTAGRAM_ACTOR_ID"])["actor_id"], **common
            ),
            "tiktok": ApifyTikTokProvider(
                credentials["APIFY_API_TOKEN"], self.actors.get_effective("tiktok", credentials["APIFY_TIKTOK_ACTOR_ID"])["actor_id"], **common
            ),
        }

    def _select_handles(self, payload: HandleSelection) -> list[dict[str, Any]]:
        records = [item for item in self.list_handles() if item.get("enabled")]
        if payload.handle_ids:
            selected = set(payload.handle_ids)
            records = [item for item in records if item.get("id") in selected]
        if payload.platforms:
            platforms = {item.value for item in payload.platforms}
            records = [item for item in records if item.get("platform") in platforms]
        return records

    def _store_provider_result(self, handle: dict, posts: list[dict], provider: SocialDataProvider) -> dict[str, Any]:
        created = skipped = snapshots = metrics_unavailable = 0
        profile = None
        for post in posts:
            profile = profile or post.pop("profile", None)
            post["creative_attributes"] = self._classification(post, {})
            result = self._upsert_post(handle, post)
            created += int(result["created"])
            skipped += int(result["skipped"])
            snapshots += int(result["snapshots"])
            metrics_unavailable += int(result["metrics_unavailable"])
        if profile:
            profile = self._upsert_profile(handle, profile, provider.name)
        return {
            "created": created,
            "skipped": skipped,
            "snapshots": snapshots,
            "metrics_unavailable": metrics_unavailable,
            "profile": profile,
        }

    def _upsert_profile(self, handle: dict, payload: dict, provider: str) -> dict[str, Any]:
        records = self.repository.read_json(PROFILES_PATH, [])
        existing_index = next((index for index, item in enumerate(records) if item.get("handle_id") == handle["id"]), None)
        record = {
            "id": records[existing_index]["id"] if existing_index is not None else f"profile-{uuid.uuid4().hex[:12]}",
            "handle_id": handle["id"],
            "platform_profile_id": payload.get("platform_profile_id"),
            "username": payload.get("username") or handle["username"],
            "display_name": payload.get("display_name"),
            "bio": payload.get("bio"),
            "profile_image_url": payload.get("profile_image_url"),
            "followers": payload.get("followers"),
            "following": payload.get("following"),
            "post_count": payload.get("post_count"),
            "verified": bool(payload.get("verified")),
            "profile_url": payload.get("profile_url") or handle["canonical_url"],
            "retrieved_at": datetime.now(UTC).isoformat(),
            "provider": provider,
            "raw_metadata": {"source": "normalized provider profile"},
        }
        if existing_index is None:
            records.append(record)
        else:
            records[existing_index] = record
        self.repository.write_json(
            PROFILES_PATH,
            records,
            schema_relative="schemas/competitor_profile.schema.json",
            validate_each=True,
        )
        return record

    def _upsert_post(self, handle: dict, payload: dict) -> dict[str, Any]:
        platform = str(payload.get("platform") or handle["platform"])
        post_id = str(payload.get("platform_post_id") or "").strip()
        if not post_id:
            raise RepositoryError("Public post record is missing its platform post ID")
        now = datetime.now(UTC).isoformat()
        records = self.repository.read_json(POSTS_PATH, [])
        existing_index = next(
            (
                index
                for index, item in enumerate(records)
                if item.get("platform") == platform and item.get("platform_post_id") == post_id
            ),
            None,
        )
        existing = records[existing_index] if existing_index is not None else {}
        record = {
            "id": existing.get("id") or f"competitor-post-{uuid.uuid4().hex[:12]}",
            "handle_id": handle["id"],
            "platform": platform,
            "platform_post_id": post_id,
            "post_url": payload.get("post_url"),
            "caption": payload.get("caption"),
            "hashtags": payload.get("hashtags") or [],
            "posted_at": payload.get("posted_at"),
            "media_type": payload.get("media_type"),
            "thumbnail_path": payload.get("thumbnail_path"),
            "remote_thumbnail_url": payload.get("remote_thumbnail_url"),
            "media_url": payload.get("media_url"),
            "carousel_item_count": payload.get("carousel_item_count"),
            "duration_seconds": payload.get("duration_seconds"),
            "view_count": payload.get("view_count"),
            "like_count": payload.get("like_count"),
            "comment_count": payload.get("comment_count"),
            "share_count": payload.get("share_count"),
            "audio_name": payload.get("audio_name"),
            "creative_attributes": payload.get("creative_attributes") or existing.get("creative_attributes") or {},
            "first_seen_at": existing.get("first_seen_at") or now,
            "last_seen_at": now,
            "provider": payload.get("provider") or "apify",
            "raw_metadata": payload.get("raw_metadata") or {},
        }
        if existing_index is None:
            records.append(record)
        else:
            records[existing_index] = {**existing, **record}
        self.repository.write_json(
            POSTS_PATH,
            records,
            schema_relative="schemas/competitor_post.schema.json",
            validate_each=True,
        )
        snapshot = {
            "id": f"snapshot-{uuid.uuid4().hex[:12]}",
            "post_id": record["id"],
            "captured_at": now,
            "view_count": record["view_count"],
            "like_count": record["like_count"],
            "comment_count": record["comment_count"],
            "share_count": record["share_count"],
            "follower_count": payload.get("follower_count"),
            "provider": record["provider"],
        }
        snapshots = self.repository.read_json(SNAPSHOTS_PATH, [])
        snapshots.append(snapshot)
        self.repository.write_json(
            SNAPSHOTS_PATH,
            snapshots,
            schema_relative="schemas/competitor_snapshot.schema.json",
            validate_each=True,
        )
        missing = sum(record.get(field) is None for field in ("view_count", "like_count", "comment_count", "share_count"))
        return {
            "post": record,
            "created": existing_index is None,
            "skipped": existing_index is not None,
            "snapshots": 1,
            "metrics_unavailable": missing,
        }

    def _classification(self, post: dict[str, Any], manual: dict[str, Any]) -> dict[str, Any]:
        classified = self.classifier.classify(post)
        if manual:
            classified.update(manual)
            classified.update({"classification_source": "manual correction", "classification_confidence": "manual", "manual_override": True})
        return classified

    def _with_performance(self, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        handles = {item["id"]: item for item in self.list_handles()}
        grouped: dict[str, list[dict]] = {}
        for post in posts:
            grouped.setdefault(str(post.get("handle_id")), []).append(post)
        enriched: list[dict] = []
        for post in posts:
            cohort = grouped.get(str(post.get("handle_id")), [])
            primary_field = self._primary_metric_field(post, cohort)
            values = [item.get(primary_field) for item in cohort if isinstance(item.get(primary_field), (int, float))] if primary_field else []
            value = post.get(primary_field) if primary_field else None
            account_median = median(values) if values else None
            account_average = mean(values) if values else None
            multiplier = value / account_median if isinstance(value, (int, float)) and account_median and account_median > 0 else None
            rank = None
            if isinstance(value, (int, float)) and values:
                rank = sum(item <= value for item in values) / len(values) * 100
            snapshots = self.snapshots(str(post.get("id")))
            handle = handles.get(str(post.get("handle_id")), {})
            followers = next((item.get("follower_count") for item in reversed(snapshots) if item.get("follower_count") is not None), handle.get("follower_count"))
            performance = {
                "primary_metric": primary_field,
                "account_median": account_median,
                "account_average": account_average,
                "percentile_rank": round(rank, 1) if rank is not None else None,
                "multiplier": round(multiplier, 2) if multiplier is not None else None,
                "sample_size": len(values),
                "like_rate_by_followers": self._rate(post.get("like_count"), followers),
                "comment_rate_by_followers": self._rate(post.get("comment_count"), followers),
                "share_rate_by_views": self._rate(post.get("share_count"), post.get("view_count")),
                "engagement_rate_by_views": self._engagement_rate(post, post.get("view_count")),
                "engagement_rate_by_followers": self._engagement_rate(post, followers),
                "view_velocity": self._velocity(snapshots, "view_count"),
                "like_velocity": self._velocity(snapshots, "like_count"),
                "comment_velocity": self._velocity(snapshots, "comment_count"),
            }
            known = sum(post.get(field) is not None for field in ("view_count", "like_count", "comment_count", "share_count"))
            enriched.append(
                {
                    **post,
                    "handle": handle,
                    "performance": performance,
                    "metric_completeness": {"known": known, "total": 4, "percent": known / 4},
                    "snapshot_count": len(snapshots),
                    "velocity_message": None if len(snapshots) >= 2 else "More snapshots are needed to calculate velocity.",
                }
            )
        return enriched

    def _manual_handle(self, row: dict[str, Any]) -> dict[str, Any]:
        handle_id = row.get("handle_id")
        if handle_id:
            return self._get_handle(str(handle_id))
        platform = str(row.get("platform") or "").lower()
        username = row.get("username") or row.get("handle")
        if not username:
            raise RepositoryError("Manual import rows require handle_id or username")
        parsed = parse_bulk_handles(f"{platform},{username}")
        target = parsed[0]
        existing = next(
            (
                item
                for item in self.list_handles()
                if item.get("platform") == target["platform"] and item.get("username") == target["username"]
            ),
            None,
        )
        if existing:
            return existing
        created, _ = self.add_handle(MonitoredHandleInput(**target, provider="manual-import"))
        return created

    def _get_handle(self, handle_id: str) -> dict[str, Any]:
        for item in self.list_handles():
            if item.get("id") == handle_id:
                return item
        raise RepositoryError("Monitored handle not found")

    def _mark_handle_success(self, handle: dict, profile: dict | None) -> None:
        now = datetime.now(UTC).isoformat()
        records = self.list_handles()
        for index, record in enumerate(records):
            if record.get("id") == handle["id"]:
                record.update(
                    {
                        "last_checked_at": now,
                        "last_success_at": now,
                        "last_error": None,
                        "profile_id": profile.get("id") if profile else record.get("profile_id"),
                        "profile_image_url": profile.get("profile_image_url") if profile else record.get("profile_image_url"),
                        "display_name": profile.get("display_name") if profile else record.get("display_name"),
                        "follower_count": profile.get("followers") if profile else record.get("follower_count"),
                        "following_count": profile.get("following") if profile else record.get("following_count"),
                        "post_count": profile.get("post_count") if profile else record.get("post_count"),
                        "updated_at": now,
                    }
                )
                records[index] = record
        self.repository.write_json(HANDLES_PATH, records, schema_relative="schemas/monitored_handle.schema.json", validate_each=True)

    def _mark_handle_error(self, handle: dict, message: str) -> None:
        records = self.list_handles()
        now = datetime.now(UTC).isoformat()
        for index, record in enumerate(records):
            if record.get("id") == handle["id"]:
                record.update({"last_checked_at": now, "last_error": message, "updated_at": now})
                records[index] = record
        self.repository.write_json(HANDLES_PATH, records, schema_relative="schemas/monitored_handle.schema.json", validate_each=True)

    def _actor_id(self, platform: str) -> str | None:
        credentials = self.secrets.get_apify_credentials()
        return self.actors.get_effective(platform, credentials[f"APIFY_{platform.upper()}_ACTOR_ID"])["actor_id"]

    @staticmethod
    def _profile_url(platform: str, username: str) -> str:
        return f"https://www.instagram.com/{username}/" if platform == "instagram" else f"https://www.tiktok.com/@{username}"

    @staticmethod
    def _preflight_message(preflight: dict[str, Any]) -> str:
        low, high = preflight.get("estimated_cost_low"), preflight.get("estimated_cost_high")
        estimate = f"${low:.2f} to ${high:.2f}" if low is not None and high is not None else "unknown; confirmation required"
        return f"Estimated this run at {estimate}."

    @staticmethod
    def _rate(numerator: Any, denominator: Any) -> float | None:
        if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)) or denominator <= 0:
            return None
        return round(float(numerator) / float(denominator), 6)

    @classmethod
    def _engagement_rate(cls, post: dict[str, Any], denominator: Any) -> float | None:
        values = [post.get(field) for field in ("like_count", "comment_count", "share_count")]
        known = [value for value in values if isinstance(value, (int, float))]
        return cls._rate(sum(known), denominator) if known else None

    @staticmethod
    def _velocity(snapshots: list[dict[str, Any]], field: str) -> float | None:
        usable = [item for item in snapshots if isinstance(item.get(field), (int, float))]
        if len(usable) < 2:
            return None
        first, last = usable[0], usable[-1]
        try:
            start = datetime.fromisoformat(str(first["captured_at"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(last["captured_at"]).replace("Z", "+00:00"))
        except ValueError:
            return None
        hours = (end - start).total_seconds() / 3600
        if hours <= 0:
            return None
        return round((float(last[field]) - float(first[field])) / hours, 2)

    @staticmethod
    def _primary_metric_field(post: dict[str, Any], cohort: list[dict]) -> str | None:
        for field in ("view_count", "like_count", "comment_count", "share_count"):
            if post.get(field) is not None and any(item.get(field) is not None for item in cohort):
                return field
        return None

    @staticmethod
    def _original_title(activity: str) -> str:
        cleaned = " ".join(part for part in activity.upper().replace("_", " ").split() if part)
        return cleaned[:80] or "QUIET MOMENTS"

    @staticmethod
    def _props_for(activity: str) -> list[str]:
        mapping = {
            "coffee": ["two proportionate mugs", "rounded cafe table", "simple coffee machine"],
            "walk": ["small park bench", "one shared umbrella", "rounded path sign"],
            "movie": ["small television", "one popcorn bowl", "shared blanket"],
            "reading": ["two books", "rounded floor lamp", "soft rug"],
            "dinner": ["low dining table", "two plates", "one serving bowl"],
            "game": ["small board game", "two floor cushions", "one snack bowl"],
        }
        return mapping.get(activity, ["one activity-specific main prop", "one rounded furniture element"])

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in (None, "", "Unavailable", "Not collected", "Provider error"):
            return None
        try:
            parsed = int(float(str(value).replace(",", "")))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid metric value: {value}") from exc
        return max(0, parsed)

    @staticmethod
    def _blank_none(value: Any) -> str | None:
        return str(value).strip() if value not in (None, "") else None

    @staticmethod
    def _list_value(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
        if value in (None, ""):
            return []
        return [item.strip().lstrip("#") for item in str(value).replace(";", ",").split(",") if item.strip()]
