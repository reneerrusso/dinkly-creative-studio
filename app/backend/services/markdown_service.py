from __future__ import annotations

import re
from typing import Any

from app.backend.services.repository_service import RepositoryService


class MarkdownService:
    def __init__(self, repository: RepositoryService) -> None:
        self.repository = repository

    def sections(self, relative: str) -> list[dict[str, Any]]:
        content = self.repository.path(relative).read_text(encoding="utf-8")
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for line in content.splitlines():
            match = re.match(r"^(#{2,3})\s+(.+)$", line)
            if match:
                if current:
                    current["content"] = "\n".join(current["lines"]).strip()
                    current.pop("lines")
                    sections.append(current)
                current = {"title": match.group(2).strip(), "level": len(match.group(1)), "lines": []}
            elif current:
                current["lines"].append(line)
        if current:
            current["content"] = "\n".join(current["lines"]).strip()
            current.pop("lines")
            sections.append(current)
        return sections

    def markdown_files(self, directory: str) -> list[dict[str, Any]]:
        target = self.repository.path(directory)
        records: list[dict[str, Any]] = []
        for path in sorted(target.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            title = next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), path.stem)
            records.append(
                {
                    "slug": path.stem.lower().replace(" ", "-"),
                    "title": title,
                    "path": self.repository.relative(path),
                    "content": content,
                    "last_modified": path.stat().st_mtime,
                }
            )
        return records
