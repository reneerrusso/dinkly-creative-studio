from __future__ import annotations

import pytest

from app.backend.models.social_posts import SocialPostInput
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.social_learning_service import SocialLearningService


def test_social_rates_and_missing_metrics(repository: RepositoryService) -> None:
    service = SocialLearningService(repository)
    post, _ = service.create_post(
        SocialPostInput(title="Coffee", views=1000, shares=100, likes=None, format="x-with-you")
    )
    assert post["rates"]["share_rate"] == 0.1
    assert post["rates"]["like_rate"] is None
    assert post["metric_completeness"] == {"known": 2, "total": 5, "percent": 0.4}


def test_duplicate_post_prevention(repository: RepositoryService) -> None:
    service = SocialLearningService(repository)
    payload = SocialPostInput(title="Walks", platform="instagram", post_date="2026-08-05")
    service.create_post(payload)
    with pytest.raises(RepositoryError, match="Likely duplicate"):
        service.create_post(payload)


def test_analysis_writes_report_and_backup(repository: RepositoryService) -> None:
    service = SocialLearningService(repository)
    service.create_post(SocialPostInput(title="Sundays", views=5000, shares=250))
    result = service.analyze()
    assert result["post_count"] == 1
    assert repository.path(result["report_path"]).exists()
    assert "Top posts by share rate" in result["generated"]

