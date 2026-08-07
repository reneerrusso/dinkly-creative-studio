from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.backend.models.sprites import SpriteAnimationCreate, SpriteCharacterCreate, SpriteFrameUpdate


def test_sprite_character_accepts_normalized_bottom_center_anchor() -> None:
    record = SpriteCharacterCreate(name="Dinko", slug="dinko-copy", character_type="dinko")
    assert record.default_anchor_x == 0.5
    assert record.default_anchor_y == 1


def test_sprite_anchor_rejects_values_outside_zero_to_one() -> None:
    with pytest.raises(ValidationError):
        SpriteFrameUpdate(anchor_x=1.2)


def test_animation_rejects_unknown_loop_mode() -> None:
    with pytest.raises(ValidationError):
        SpriteAnimationCreate(
            name="Blink",
            character_id="sprite-character-dinko",
            category="facial",
            loop_mode="boomerang",
        )


def test_animation_rejects_inverted_loop_range() -> None:
    with pytest.raises(ValidationError):
        SpriteAnimationCreate(
            name="Blink",
            character_id="sprite-character-dinko",
            category="facial",
            loop_start_frame=2,
            loop_end_frame=1,
        )
