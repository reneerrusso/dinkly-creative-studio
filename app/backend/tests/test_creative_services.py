from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.backend.models.concepts import ConceptCreate
from app.backend.models.prompts import PromptGenerateRequest
from app.backend.models.reviews import EditPromptRequest
from app.backend.services.art_review_service import ArtReviewService
from app.backend.services.concept_service import ConceptService
from app.backend.services.markdown_service import MarkdownService
from app.backend.services.prompt_service import PromptService
from app.backend.services.reference_analysis_service import ReferenceAnalysisService
from app.backend.services.repository_service import RepositoryService
from app.backend.services.story_normalization import normalize_story_record, scene_richness, scene_warnings


def test_prompt_templates_are_available_to_the_studio_brain(repository: RepositoryService) -> None:
    templates = MarkdownService(repository).markdown_files("PROMPT_TEMPLATES")

    assert templates
    assert all(item["title"] and item["content"].startswith("#") for item in templates)
    assert any(item["slug"] == "xwithyou" for item in templates)


def test_concept_scoring_is_directional_and_saved(
    repository: RepositoryService, sample_concept_payload: dict
) -> None:
    service = ConceptService(repository)
    concept, _ = service.create(ConceptCreate(**sample_concept_payload))
    score, backup = service.score(concept["id"], save=True)
    assert score["evaluation_label"] == "directional creative evaluation, not a performance prediction"
    assert 1 <= score["directional_total"] <= 10
    assert score["weakest_criterion"]
    assert backup is not None


def test_concept_delete_removes_record_and_directional_scores(
    repository: RepositoryService, sample_concept_payload: dict
) -> None:
    service = ConceptService(repository)
    concept, _ = service.create(ConceptCreate(**sample_concept_payload))
    service.score(concept["id"], save=True)

    deleted, backups = service.delete(concept["id"])

    assert deleted["id"] == concept["id"]
    assert backups
    assert all(record.get("id") != concept["id"] for record in repository.read_json("app-data/concepts.json"))
    assert all(
        record.get("storyline_id") != concept["id"]
        for record in repository.read_json("data/storyline_scores.json")
    )
    assert all(record.get("id") != concept["id"] for record in service.list(include_archived=True))


def test_prompt_generation_uses_relevant_protection(
    repository: RepositoryService, sample_concept_payload: dict, monkeypatch
) -> None:
    import scripts.generate_prompt_brief as generator

    monkeypatch.setattr(generator, "TEMPLATE_DIR", repository.path("PROMPT_TEMPLATES"))
    concepts = ConceptService(repository)
    concept, _ = concepts.create(ConceptCreate(**sample_concept_payload))
    service = PromptService(repository, concepts)
    result = service.generate(PromptGenerateRequest(concept_id=concept["id"], format="x-with-you"))
    assert "exactly two hair tufts" in result["prompt"]
    assert "visible legs" in result["prompt"]
    assert result["sections"]
    assert all("{{" not in section["content"] for section in result["sections"])


def test_prompt_generation_accepts_inline_concept_without_saved_id(
    repository: RepositoryService, monkeypatch
) -> None:
    import scripts.generate_prompt_brief as generator

    monkeypatch.setattr(generator, "TEMPLATE_DIR", repository.path("PROMPT_TEMPLATES"))
    service = PromptService(repository, ConceptService(repository))
    result = service.generate(
        PromptGenerateRequest(
            concept_id=None,
            format="x-with-you",
            title_pair={"left": "RAIN", "right": "RAIN WITH YOU"},
            left_scene="Dinko waits alone under an umbrella with a neutral expression.",
            right_scene="Dinka and Dinko share the same umbrella in the same rainy setting.",
            emotional_insight="The ordinary wait feels warmer when shelter is shared.",
            recommended_background_color="custom pale storm blue",
            recommended_accent_color="custom muted coral",
            recommended_camera_angle="medium straight-on",
            props=["one shared umbrella"],
        )
    )

    assert "RAIN WITH YOU" in result["prompt"]
    assert "custom pale storm blue" in result["prompt"]
    assert "custom muted coral" in result["prompt"]
    assert "Dinka and Dinko share the same umbrella" in result["prompt"]


def test_prompt_generation_allows_optional_captions_scenes_and_insight(
    repository: RepositoryService, monkeypatch
) -> None:
    import scripts.generate_prompt_brief as generator

    monkeypatch.setattr(generator, "TEMPLATE_DIR", repository.path("PROMPT_TEMPLATES"))
    service = PromptService(repository, ConceptService(repository))
    result = service.generate(PromptGenerateRequest(format="x-with-you"))

    prompt = result["prompt"]
    assert "Do not render a caption" in prompt
    assert "Create a simple ordinary-alone moment from a simple, relatable everyday routine" in prompt
    assert "Create a warmer together version from a simple, relatable everyday routine" in prompt
    assert "{{" not in prompt


@pytest.mark.parametrize("left_character", ["boy", "girl"])
def test_concept_accepts_each_approved_left_character(
    sample_concept_payload: dict, left_character: str
) -> None:
    payload = {**sample_concept_payload, "left_character": left_character}
    assert ConceptCreate(**payload).left_character == left_character


def test_concept_rejects_invalid_left_character(sample_concept_payload: dict) -> None:
    with pytest.raises(ValidationError):
        ConceptCreate(**{**sample_concept_payload, "left_character": "either"})


def test_old_story_record_normalizes_without_losing_scene_summary() -> None:
    legacy = {
        "id": "legacy-rain",
        "title_pair": {"left": "RAIN", "right": "RAIN WITH YOU"},
        "left_scene": "Dinka waits alone under an umbrella.",
        "right_scene": "Dinka and Dinko share the umbrella.",
    }
    normalized = normalize_story_record(legacy)
    assert normalized["left_scene"] == legacy["left_scene"]
    assert normalized["right_scene"] == legacy["right_scene"]
    assert normalized["left_character"] == "girl"
    assert normalized["left_props"] == []
    assert normalized["right_props"] == []
    assert normalized["migration_version"] == 2


@pytest.mark.parametrize(
    ("left_character", "expected_left_rule"),
    [("boy", "Boy DINKLY matches the official reference exactly"), ("girl", "Girl DINKLY matches the official reference exactly")],
)
def test_scene_rich_prompt_uses_selected_left_character_and_complete_scene(
    repository: RepositoryService, monkeypatch, left_character: str, expected_left_rule: str
) -> None:
    import scripts.generate_prompt_brief as generator

    monkeypatch.setattr(generator, "TEMPLATE_DIR", repository.path("PROMPT_TEMPLATES"))
    result = PromptService(repository, ConceptService(repository)).generate(
        PromptGenerateRequest(
            format="x-with-you",
            title_pair={"left": "PARTY", "right": "PARTY WITH YOU"},
            left_character=left_character,
            left_character_action="stands alone holding one red plastic cup",
            left_setting="a small indoor party room",
            left_props=["red plastic cup", "deflated balloons", "snack table"],
            left_emotion="Nervous and unsure where to stand.",
            right_character_actions="laugh and dance together while looking at each other",
            right_setting="the same small indoor party room",
            right_props=["two red cups", "floating balloons", "colorful snacks"],
            right_emotion="Lively and warm because they are together.",
            shared_environment="Same small party room with one snack table and balloons.",
            environmental_contrast="Left is sparse and still; right adds floating balloons and movement.",
        )
    )
    prompt = result["prompt"]
    assert expected_left_rule in prompt
    assert "Boy DINKLY and Girl DINKLY" in prompt
    assert "Same small party room with one snack table and balloons." in prompt
    assert "red plastic cup; deflated balloons; snack table" in prompt
    assert "two red cups; floating balloons; colorful snacks" in prompt
    assert "## SHARED ENVIRONMENT" in prompt
    assert "## ENVIRONMENTAL CONTRAST" in prompt


def test_scene_richness_and_warnings_are_directional() -> None:
    sparse = {"left_setting": "", "right_setting": "room", "left_props": [], "right_props": ["cup"]}
    balanced = {"left_setting": "room", "right_setting": "same room", "left_props": ["cup", "table"], "right_props": ["two cups", "table"]}
    detailed = {"left_setting": "room", "right_setting": "same room", "left_props": [str(index) for index in range(6)], "right_props": ["table", "cup"]}
    assert scene_richness(sparse) == "Sparse"
    assert scene_richness(balanced) == "Balanced"
    assert scene_richness(detailed) == "Detailed"
    assert "not contain enough visual context" in scene_warnings(sparse)[0]
    assert "too many competing props" in scene_warnings(detailed)[0]


def test_scene_reference_preserves_story_but_never_controls_dinkly_identity(
    repository: RepositoryService, monkeypatch
) -> None:
    import scripts.generate_prompt_brief as generator

    monkeypatch.setattr(generator, "TEMPLATE_DIR", repository.path("PROMPT_TEMPLATES"))
    uploaded = repository.save_upload("reference-comic.png", b"local-reference-image")
    service = PromptService(repository, ConceptService(repository))
    result = service.generate(
        PromptGenerateRequest(
            format="x-with-you",
            title_pair={"left": "WAITING", "right": "WAITING WITH YOU"},
            left_scene="Dinko waits alone beside a simple station bench.",
            right_scene="Dinka and Dinko wait together beside the same station bench.",
            scene_reference_path=uploaded["path"],
            scene_reference_analysis=(
                "Square wide station scene. Dinko waits alone beside a low bench on the left; "
                "Dinka and Dinko wait together beside the same bench on the right."
            ),
            scene_reference_notes="Keep the low bench, wide framing, and gentle anticipation.",
        )
    )

    prompt = result["prompt"]
    assert "SOURCE COMIC ANALYSIS — SELF-CONTAINED DINKLY ADAPTATION" in prompt
    assert "The original source image will not be available" in prompt
    assert "Square wide station scene" in prompt
    assert "environment, storyline, camera framing" in prompt
    assert "Do not copy any character identity" in prompt
    assert "exactly two hair tufts" in prompt
    assert "bright-red bow" in prompt
    assert "official DINKLY rules always win" in prompt
    assert "Attach this same image" not in prompt
    assert result["scene_reference_path"] == uploaded["path"]


def test_local_reference_analysis_builds_an_editable_self_contained_brief(
    repository: RepositoryService, monkeypatch
) -> None:
    uploaded = repository.save_upload("source-comic.png", b"image-bytes")
    signals = {
        "width": 1080,
        "height": 1080,
        "orientation": "square",
        "classification_labels": [
            {"label": "living room", "confidence": 0.82},
            {"label": "companionship", "confidence": 0.61},
        ],
        "recognized_text": [{"text": "SUNDAYS WITH YOU", "horizontal": "right", "vertical": "lower"}],
        "faces": [{"horizontal": "right", "vertical": "middle"}],
        "human_figures": [],
        "average_color": "#F5E5BE",
    }

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout=json.dumps(signals))

    monkeypatch.setattr("app.backend.services.reference_analysis_service.subprocess.run", fake_run)
    result = ReferenceAnalysisService(repository).analyze(uploaded["path"])

    assert result["signals"] == signals
    assert "living room" in result["scene_brief"]
    assert "SUNDAYS WITH YOU" in result["scene_brief"]
    assert "original reference image will not accompany" in result["scene_brief"]


def test_art_review_recommends_regeneration_for_identity_failure(repository: RepositoryService) -> None:
    service = ArtReviewService(repository)
    result = service.edit_prompt(EditPromptRequest(failures=["Wrong eyes"], notes="Both characters drifted."))
    assert result["regenerate"] is True
    assert result["recommendation"] == "full regeneration"
    assert "Restore the exact black oval eyes" in result["edit_prompt"]


def test_art_review_builds_targeted_prompt_for_local_error(repository: RepositoryService) -> None:
    service = ArtReviewService(repository)
    result = service.edit_prompt(EditPromptRequest(failures=["Text error"]))
    assert result["regenerate"] is False
    assert "no quotation marks" in result["edit_prompt"]
