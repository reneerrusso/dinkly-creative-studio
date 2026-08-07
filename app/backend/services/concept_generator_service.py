"""Canonical Concept Generator service export.

The implementation intentionally retains legacy storage paths. This avoids a
risky migration while preserving every batch, preference, chat message,
feedback record, and used storyline.
"""

from app.backend.services.content_agent_service import ConceptGeneratorService

__all__ = ["ConceptGeneratorService"]
