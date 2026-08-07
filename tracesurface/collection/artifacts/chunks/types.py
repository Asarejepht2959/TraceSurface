from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from tree_sitter import Node


@dataclass(frozen=True, slots=True)
class SourceDocument:
    url: str
    text: str
    tree_root: Node | None = None


@dataclass(slots=True)
class ChunkContext:
    page: Any
    base_url: str


@dataclass(frozen=True, slots=True)
class ChunkResult:
    urls: frozenset[str] = field(default_factory=frozenset)


class ChunkStrategy(Protocol):
    name: str

    def supports(self, source: SourceDocument) -> bool: ...

    async def discover(
        self,
        source: SourceDocument,
        ctx: ChunkContext,
    ) -> ChunkResult: ...
