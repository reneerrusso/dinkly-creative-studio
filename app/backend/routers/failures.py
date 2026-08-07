from __future__ import annotations

from fastapi import APIRouter

from app.backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api/failures", tags=["failures"])
repository = RepositoryService()


def category_for(name: str) -> str:
    lowered = name.lower()
    if any(word in lowered for word in ("leg", "anatomy", "arms")):
        return "Anatomy"
    if any(word in lowered for word in ("eye", "tuft", "bow", "ponytail", "sizes")):
        return "Character identity"
    if any(word in lowered for word in ("table", "chair", "vanity", "island", "cart")):
        return "Furniture"
    if any(word in lowered for word in ("phone", "toothbrush", "mug")):
        return "Props"
    if "background" in lowered or "environment" in lowered:
        return "Background"
    if "color" in lowered:
        return "Color"
    if "product" in lowered or "packaging" in lowered or "brand" in lowered:
        return "Product integration"
    return "Composition"


@router.get("")
def list_failures() -> list[dict]:
    content = repository.path("FAILURES.md").read_text(encoding="utf-8")
    records: list[dict] = []
    for line in content.splitlines():
        if not line.startswith("|") or "---" in line or "Failure" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 6:
            records.append(
                {
                    "name": cells[0],
                    "category": category_for(cells[0]),
                    "what_it_looks_like": cells[0],
                    "why": cells[1],
                    "prevention": cells[2],
                    "when_to_simplify": cells[3],
                    "edit_language": cells[4],
                    "when_to_regenerate": cells[5],
                    "related_examples": [],
                }
            )
    return records

