from __future__ import annotations

from typing import Any

from tracesurface.collection.artifacts.chunks.types import (
    ChunkContext,
    ChunkResult,
    ChunkStrategy,
    SourceDocument,
)
from tracesurface.htmlast import extract_inline_scripts


class ChunkDiscoveryService:
    def __init__(self, strategies: tuple[ChunkStrategy, ...]) -> None:
        self.strategies = strategies

    async def discover(
        self,
        source: SourceDocument,
        ctx: ChunkContext,
    ) -> ChunkResult:
        urls: set[str] = set()

        for strategy in self.strategies:
            if strategy.supports(source):
                urls.update((await strategy.discover(source, ctx)).urls)
        return ChunkResult(frozenset(urls))

    async def extract_chunk_urls(
        self,
        page: Any,
        html_source: str,
        base_url: str,
        *,
        sink: set[str],
    ) -> int:
        before = len(sink)
        ctx = ChunkContext(page=page, base_url=base_url)

        for _line, script in extract_inline_scripts(html_source):
            result = await self.discover(SourceDocument("", script), ctx)
            sink.update(result.urls)
        return len(sink) - before

    async def extract_chunk_urls_from_tree(
        self,
        page: Any,
        source_url: str,
        source: str,
        tree_root,
        base_url: str,
        *,
        sink: set[str],
    ) -> int:
        before = len(sink)
        ctx = ChunkContext(page=page, base_url=base_url)

        result = await self.discover(
            SourceDocument(source_url, source, tree_root),
            ctx,
        )
        sink.update(result.urls)
        return len(sink) - before


def default_chunk_service() -> ChunkDiscoveryService:
    from tracesurface.collection.artifacts.chunks.vite import ViteChunkStrategy
    from tracesurface.collection.artifacts.chunks.webpack import WebpackChunkStrategy

    return ChunkDiscoveryService((WebpackChunkStrategy(), ViteChunkStrategy()))
