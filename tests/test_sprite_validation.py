from __future__ import annotations

from app.backend.models.sprites import FrameAlignRequest, FrameReorderRequest, SpriteFrameUpdate
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.sprite_service import SpriteService


def test_upload_duplicate_reorder_align_and_manual_approval(
    sprite_repository: RepositoryService,
    technical_frame_bytes: list[bytes],
) -> None:
    service = SpriteService(sprite_repository)
    animation_id = "sprite-animation-dinko-blink"
    frames, _ = service.upload_frames(
        animation_id,
        [(f"technical-{index}.png", content) for index, content in enumerate(technical_frame_bytes)],
    )
    assert len(frames) == 3
    assert all(frame["transparent"] for frame in frames)

    try:
        service.upload_frames(animation_id, [("duplicate.png", technical_frame_bytes[0])])
    except RepositoryError as exc:
        assert "Duplicate" in str(exc)
    else:
        raise AssertionError("duplicate frame was accepted")

    reversed_ids = [frame["id"] for frame in reversed(frames)]
    reordered, _ = service.reorder_frames(animation_id, FrameReorderRequest(frame_ids=reversed_ids))
    assert [frame["id"] for frame in reordered] == reversed_ids
    aligned, _ = service.align_frames(animation_id, FrameAlignRequest(mode="bottom_center"))
    assert all(frame["anchor_x"] == 0.5 and frame["anchor_y"] == 1 for frame in aligned)

    for frame in aligned:
        service.update_frame(frame["id"], SpriteFrameUpdate(review_status="Pass", approved=True))
    approved, _ = service.approve_animation(animation_id)
    assert approved["approved"] is True
    assert approved["approval_level"] == "Approved"


def test_character_checklists_are_identity_specific(sprite_repository: RepositoryService) -> None:
    service = SpriteService(sprite_repository)
    dinko = service.get_animation("sprite-animation-dinko-blink")
    dinka = service.get_animation("sprite-animation-dinka-blink")
    assert "Exactly two hair tufts" in dinko["validation_checklist"]
    assert "Exact bright red bow" in dinka["validation_checklist"]
    assert "Connected ponytail" in dinka["validation_checklist"]

