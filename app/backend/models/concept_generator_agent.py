"""Canonical Concept Generator models.

Storage still uses the original ``content_*`` filenames and model names so all
existing records remain valid. These aliases provide the consolidated product
language without rewriting historical data.
"""

from app.backend.models.content_agent import (
    BatchRequest,
    ChatRequest,
    ComicBeat,
    ConceptActionRequest,
    ConceptEditRequest,
    PreferenceUpdateRequest,
    UsedStoryline,
)
from app.backend.models.content_agent import (
    ContentBatch as ConceptBatch,
)
from app.backend.models.content_agent import (
    ContentConcept as ConceptGeneratorConcept,
)
from app.backend.models.content_agent import (
    ContentFeedback as ConceptFeedback,
)
from app.backend.models.content_agent import (
    ContentFormat as ConceptFormat,
)
from app.backend.models.content_agent import (
    ContentPreference as ConceptGeneratorPreference,
)
from app.backend.models.content_agent import (
    ContentSettings as ConceptGeneratorSettings,
)

__all__ = [
    "BatchRequest",
    "ChatRequest",
    "ComicBeat",
    "ConceptActionRequest",
    "ConceptBatch",
    "ConceptEditRequest",
    "ConceptFeedback",
    "ConceptFormat",
    "ConceptGeneratorConcept",
    "ConceptGeneratorPreference",
    "ConceptGeneratorSettings",
    "PreferenceUpdateRequest",
    "UsedStoryline",
]
