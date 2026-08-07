from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.backend.models.stories import StoryCreate
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.story_library_service import StoryLibraryService
from app.backend.services.story_normalization import normalize_story_record

router = APIRouter(prefix="/api/story-library", tags=["story library"])
repository = RepositoryService()
service = StoryLibraryService(repository)


def parsed_stories() -> list[dict]:
    return service.list()


@router.get("")
def list_stories() -> list[dict]:
    return parsed_stories()


@router.get("/{story_id}")
def get_story(story_id: str) -> dict:
    for story in parsed_stories():
        if story.get("id") == story_id:
            return story
    raise HTTPException(status_code=404, detail="Story Library seed not found")


@router.post("")
def create_story(payload: StoryCreate) -> dict:
    records = repository.read_json("app-data/story_library.json", [])
    record = payload.model_dump(mode="json")
    record.update(
        {
            "id": f"story-{uuid.uuid4().hex[:10]}",
            "source": "app",
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    records.append(record)
    backup = repository.write_json("app-data/story_library.json", records)
    return {"story": normalize_story_record(record, source="app"), "backup": backup}


@router.put("/{story_id}")
def update_story(story_id: str, payload: StoryCreate) -> dict:
    records = repository.read_json("app-data/story_library.json", [])
    for index, record in enumerate(records):
        if record.get("id") == story_id:
            records[index] = {**record, **payload.model_dump(mode="json")}
            backup = repository.write_json("app-data/story_library.json", records)
            return {"story": normalize_story_record(records[index], source="app"), "backup": backup}
    raise RepositoryError("Only app-created stories can be edited; duplicate a seeded story first")
