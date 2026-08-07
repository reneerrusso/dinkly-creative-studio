from __future__ import annotations

import json

import pytest

from app.backend.services.repository_service import RepositoryError, RepositoryService


def test_path_traversal_is_blocked(repository: RepositoryService) -> None:
    with pytest.raises(RepositoryError, match="inside the repository"):
        repository.path("../outside.json")


def test_atomic_write_preserves_valid_json_and_creates_backup(repository: RepositoryService) -> None:
    first = [{"id": "one"}]
    repository.write_json("app-data/concepts.json", first)
    backup = repository.write_json("app-data/concepts.json", [{"id": "two"}])
    assert backup is not None
    assert repository.read_json("app-data/concepts.json") == [{"id": "two"}]
    backup_path = repository.path(backup)
    assert json.loads(backup_path.read_text(encoding="utf-8")) == first


def test_schema_validation_rejects_invalid_record(repository: RepositoryService) -> None:
    with pytest.raises(RepositoryError, match="Schema validation failed"):
        repository.write_json(
            "data/social_posts.json",
            [{"id": "incomplete"}],
            schema_relative="schemas/social_post.schema.json",
            validate_each=True,
        )


def test_upload_rules_and_safe_unique_name(repository: RepositoryService) -> None:
    record = repository.save_upload("My Comic.PNG", b"valid-local-image-bytes")
    assert record["path"].startswith("app-data/uploads/my-comic-")
    assert record["path"].endswith(".png")
    assert repository.path(record["path"]).is_file()
    with pytest.raises(RepositoryError, match="Only PNG"):
        repository.save_upload("notes.txt", b"no")


def test_markdown_update_creates_backup(repository: RepositoryService) -> None:
    updated = repository.write_markdown("readme", "# Updated\n\n" + "Useful local content. " * 10)
    assert updated["backup"]
    assert repository.path(updated["backup"]).exists()
