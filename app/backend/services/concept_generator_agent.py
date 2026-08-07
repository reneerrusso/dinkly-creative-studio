"""Canonical model-provider surface for Concept Generator.

The legacy module remains importable for backward compatibility.
"""

from app.backend.services.content_agent import (
    ContentModelProvider as ConceptModelProvider,
)
from app.backend.services.content_agent import (
    DevelopmentFixtureProvider,
)
from app.backend.services.content_agent import (
    UnavailableContentModelProvider as UnavailableConceptModelProvider,
)
from app.backend.services.content_agent import (
    content_provider_from_environment as concept_provider_from_environment,
)

__all__ = [
    "ConceptModelProvider",
    "DevelopmentFixtureProvider",
    "UnavailableConceptModelProvider",
    "concept_provider_from_environment",
]
