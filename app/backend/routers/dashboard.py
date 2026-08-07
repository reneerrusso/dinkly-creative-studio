from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.backend.services.art_review_service import ArtReviewService
from app.backend.services.concept_service import ConceptService
from app.backend.services.prompt_service import PromptService
from app.backend.services.repository_service import RepositoryService
from app.backend.services.social_learning_service import SocialLearningService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
repository = RepositoryService()
concepts = ConceptService(repository)
prompts = PromptService(repository, concepts)
social = SocialLearningService(repository)
reviews = ArtReviewService(repository)


@router.get("")
def dashboard() -> dict[str, Any]:
    posts = social.posts()
    learnings = social.learnings()
    all_concepts = concepts.list()
    all_prompts = prompts.list()
    all_reviews = reviews.list()
    story_content = repository.path("STORY_LIBRARY.md").read_text(encoding="utf-8")
    failure_content = repository.path("FAILURES.md").read_text(encoding="utf-8")
    storylines = sum(1 for line in story_content.splitlines() if line.startswith("|") and "---" not in line) - 19
    failures = sum(1 for line in failure_content.splitlines() if line.startswith("|") and "---" not in line) - 1
    complete_metrics = sum(post.get("metric_completeness", {}).get("percent") == 1 for post in posts)
    high_confidence = [item for item in learnings if item.get("confidence") == "high"]
    strongest = sorted(
        learnings,
        key=lambda item: ({"high": 3, "medium": 2, "low": 1}.get(item.get("confidence"), 0), len(item.get("evidence_post_ids", []))),
        reverse=True,
    )[:4]
    return {
        "metrics": {
            "social_posts": len(posts),
            "posts_with_complete_metrics": complete_metrics,
            "high_confidence_learnings": len(high_confidence),
            "storylines": max(0, storylines),
            "approved_prompts": sum(item.get("status") == "approved" for item in all_prompts),
            "recorded_failures": max(0, failures),
        },
        "continue_working": {
            "concepts": all_concepts[:3],
            "prompt_drafts": [item for item in all_prompts if item.get("status") == "draft"][:3],
            "art_reviews": all_reviews[-3:][::-1],
            "social_analyses": social.reports()[:3],
        },
        "strongest_learnings": strongest,
        "performance": social.patterns(),
        "welcome": len(posts) == 0 and len(all_concepts) <= 1,
        "workflows": [
            {"name": "Learn", "description": "Turn strong posts into measured creative evidence."},
            {"name": "Ideate", "description": "Develop ordinary moments with a clear relationship truth."},
            {"name": "Build", "description": "Generate concise, scene-specific Nano Banana prompts."},
            {"name": "Review", "description": "Check character consistency and repair artwork precisely."},
            {"name": "Integrate", "description": "Place products naturally without losing the story."},
        ],
    }
