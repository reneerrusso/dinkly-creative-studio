from scripts.validate_migrations import validate


def test_cloud_migrations_are_complete_and_non_destructive() -> None:
    assert validate() == []
