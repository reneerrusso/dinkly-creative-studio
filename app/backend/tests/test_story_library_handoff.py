from app.backend.routers.story_library import get_story, parsed_stories


def test_seed_ids_are_unique_across_story_categories() -> None:
    stories = parsed_stories()
    ids = [story["id"] for story in stories]
    assert len(ids) == len(set(ids))


def test_story_detail_returns_full_prompt_handoff_data() -> None:
    laundry = next(story for story in parsed_stories() if story["title"] == "Laundry")
    detail = get_story(laundry["id"])
    assert detail["title_direction"] == "LAUNDRY / LAUNDRY WITH YOU"
    assert detail["concept"] == "Chores become companionship"
    assert "baskets" in detail["visual_distinction"].lower()


def test_party_seed_contains_a_balanced_complete_scene() -> None:
    party = next(story for story in parsed_stories() if story["id"] == "story-v2-party")
    assert party["left_character"] == "boy"
    assert party["right_characters"] == "boy_and_girl"
    assert party["left_setting"] == "a small minimalist indoor party room"
    assert any("deflated balloons" in prop for prop in party["left_props"])
    assert any("floating balloons" in prop for prop in party["right_props"])
    assert party["shared_environment"]
    assert party["environmental_contrast"]
    assert party["scene_richness"] == "Balanced"
    assert party["migration_version"] == 2
