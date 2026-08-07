from __future__ import annotations

from app.backend.services.repository_service import RepositoryError, RepositoryService


def test_sprite_paths_cannot_escape_repository(sprite_repository: RepositoryService) -> None:
    try:
        sprite_repository.path("../../outside.png")
    except RepositoryError:
        pass
    else:
        raise AssertionError("path traversal was accepted")


def test_atomic_write_creates_timestamped_backup(sprite_repository: RepositoryService) -> None:
    target = sprite_repository.path("app-data/sprites/frames.json")
    sprite_repository.atomic_write_bytes(target, b"[]\n")
    backup = sprite_repository.atomic_write_bytes(target, b"[{}]\n")
    assert backup is not None
    assert sprite_repository.path(backup).is_file()

