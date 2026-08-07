#!/usr/bin/env python3
"""Copy local DINKLY state to Supabase; never remove local data."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import tarfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.config import settings  # noqa: E402
from app.backend.services.cloud_persistence import (  # noqa: E402
    PostgresAgentStorage,
    SupabaseDataAPI,
    SupabaseDocumentStore,
    SupabaseObjectStorage,
)

AGENT_KEYS = {
    "app-data/dinkly-agent/tasks.json",
    "app-data/dinkly-agent/conversations.json",
    "app-data/dinkly-agent/processed-channel-events.json",
    "app-data/dinkly-agent/channel-outbox.json",
}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov"}


def json_files() -> list[Path]:
    files = list((ROOT / "data").rglob("*.json")) + list((ROOT / "app-data").rglob("*.json"))
    return sorted(path for path in files if "backups" not in path.parts and path.is_file())


def asset_files() -> list[Path]:
    roots = [
        ROOT / "references",
        ROOT / "app-data" / "generation-engine" / "runs",
        ROOT / "app-data" / "uploads",
        ROOT / "app-data" / "sprites",
    ]
    return sorted(
        path
        for base in roots
        if base.exists()
        for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES
    )


def backup() -> Path:
    directory = ROOT / "app-data" / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"pre-cloud-migration-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
    with tarfile.open(destination, "w:gz") as archive:
        for relative in (
            "data",
            "app-data/dinkly-agent",
            "app-data/generation-engine",
            "app-data/uploads",
            "app-data/sprites",
            "references",
        ):
            source = ROOT / relative
            if source.exists():
                archive.add(source, arcname=relative)
    return destination


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def mirror_special_tables(database: SupabaseDataAPI, key: str, payload: Any) -> None:
    if not isinstance(payload, list):
        return
    now = datetime.now(UTC).isoformat()
    if key == "data/used_storylines.json":
        rows = [
            {
                "id": item.get("id") or f"story-{index}",
                "title": item.get("title") or item.get("story_title"),
                "storyline": item.get("storyline") or item.get("title") or json.dumps(item),
                "generation_id": item.get("generation_id"),
                "date_used": item.get("date_used") or item.get("used_at"),
                "record_json": item,
            }
            for index, item in enumerate(payload)
            if isinstance(item, dict)
        ]
        if rows:
            database.upsert("used_storylines", rows)
    if key == "data/content_feedback.json":
        rows = [
            {
                "id": item.get("id") or f"feedback-{index}",
                "concept_id": item.get("concept_id"),
                "generation_id": item.get("generation_id"),
                "feedback": item.get("feedback") or item.get("notes") or item.get("message") or "Feedback",
                "sentiment": item.get("sentiment"),
                "channel": item.get("channel") or "web",
                "user_id": item.get("user_id"),
                "created_at": item.get("created_at") or now,
            }
            for index, item in enumerate(payload)
            if isinstance(item, dict)
        ]
        if rows:
            database.upsert("concept_feedback", rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Perform the copy; default is a read-only plan")
    args = parser.parse_args()
    documents = json_files()
    assets = asset_files()
    invalid = []
    for path in documents:
        try:
            load(path)
        except (OSError, json.JSONDecodeError) as exc:
            invalid.append(f"{path.relative_to(ROOT)}: {exc}")
    if invalid:
        raise SystemExit("Invalid JSON prevents migration:\n" + "\n".join(invalid))
    plan = {"json_documents": len(documents), "assets": len(assets), "execute": args.execute}
    print(json.dumps(plan, indent=2))
    if not args.execute:
        print("dry run only; use --execute after applying migrations")
        return 0

    required = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit("Missing environment variables: " + ", ".join(missing))
    backup_path = backup()
    cloud_settings = replace(
        settings,
        app_mode="cloud",
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "dinkly-assets"),
    )
    database = SupabaseDataAPI(cloud_settings)
    document_store = SupabaseDocumentStore(database)
    agent_store = PostgresAgentStorage(database)
    storage = SupabaseObjectStorage(cloud_settings)
    document_checksums: dict[str, str] = {}
    for path in documents:
        key = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        payload = json.loads(raw)
        (agent_store if key in AGENT_KEYS else document_store).write(key, payload)
        mirror_special_tables(database, key, payload)
        document_checksums[key] = hashlib.sha256(raw).hexdigest()
    asset_checksums: dict[str, str] = {}
    for path in assets:
        key = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        uploaded = storage.upload(key, raw, content_type=mimetypes.guess_type(path.name)[0])
        database.upsert(
            "assets",
            {
                "id": f"asset-{hashlib.sha256(key.encode()).hexdigest()[:16]}",
                "asset_type": (
                    "generation"
                    if "generation-engine/runs" in key
                    else "sprite"
                    if key.startswith("app-data/sprites/")
                    else "upload"
                    if key.startswith("app-data/uploads/")
                    else "reference"
                ),
                "storage_bucket": uploaded["bucket"],
                "storage_path": uploaded["path"],
                "content_type": uploaded["content_type"],
                "sha256": uploaded["sha256"],
                "size_bytes": uploaded["size_bytes"],
                "metadata_json": {"local_source": key},
            },
        )
        asset_checksums[key] = uploaded["sha256"]
    manifest = {
        "migrated_at": datetime.now(UTC).isoformat(),
        "backup": str(backup_path.relative_to(ROOT)),
        "documents": document_checksums,
        "assets": asset_checksums,
        "local_data_deleted": False,
    }
    manifest_path = ROOT / "app-data" / "backups" / "last-cloud-migration-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "backup": manifest["backup"], "documents": len(document_checksums), "assets": len(asset_checksums)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
