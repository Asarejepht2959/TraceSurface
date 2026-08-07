from __future__ import annotations

from tracesurface.collection import route
from tracesurface.collection.artifacts.chunks.service import (
    ChunkDiscoveryService,
    default_chunk_service,
)
from tracesurface.collection.artifacts.entry_fetcher import MFEEntryFetcher
from tracesurface.collection.artifacts.html import HtmlAssetExtractor
from tracesurface.collection.discovery.explorer import ExplorerResult
from tracesurface.collection.session import DiscoverySession
from tracesurface.jsast import parse_js
from tracesurface.sources import load_source


class ArtifactExplorer:
    name = "artifact"
    run_once = False

    def __init__(
        self,
        html_assets: HtmlAssetExtractor | None = None,
        chunk_service: ChunkDiscoveryService | None = None,
        entry_fetcher: MFEEntryFetcher | None = None,
    ) -> None:
        self.html_assets = html_assets or HtmlAssetExtractor()
        self.chunk_service = chunk_service or default_chunk_service()
        self.entry_fetcher = entry_fetcher or MFEEntryFetcher()

    async def discover(
        self,
        session: DiscoverySession,
        round_num: int = 0,
    ) -> ExplorerResult:
        del round_num

        pre_js = set(session.js_urls)
        pre_html = set(session.facts.html_facts)
        pre_routes = set(session.facts.route_facts)
        await self.discover_artifacts(session)
        return ExplorerResult(
            new_js=len(session.js_urls - pre_js),
            new_html=len(set(session.facts.html_facts) - pre_html),
            new_routes=len(set(session.facts.route_facts) - pre_routes),
        )

    async def discover_artifacts(
        self,
        state: DiscoverySession,
    ) -> None:
        graph = state.facts

        new_html_items = [
            (url, fact.ref)
            for url, fact in graph.html_facts.items()
            if url not in graph.processed_html_sources
        ]
        new_js_items = [
            (url, ref)
            for url, ref in state.js_sources.items()
            if url not in graph.processed_js_sources
        ]

        for html_url, ref in new_html_items:
            html = load_source(ref)

            html_result = self.html_assets.extract(html, html_url)
            state.add_js_urls(
                html_result.js_urls,
                source="html_asset",
                evidence_url=html_url,
            )

            state.add_route_facts(
                html_result.router_routes,
                source="html_inline_route",
                evidence_url=html_url,
            )
            state.add_route_facts(
                html_result.named_routes,
                source="named_navigation",
                evidence_url=html_url,
            )
            state.add_route_facts(
                html_result.w3c_routes,
                source="w3c_navigation",
                evidence_url=html_url,
            )

            await self._extract_chunks_from_html(state, html)

            graph.processed_html_sources.add(html_url)
            del html

        for js_url, ref in new_js_items:
            src = load_source(ref)
            try:
                tree_root = parse_js(src).root_node
            except Exception:
                tree_root = None

            if tree_root is not None:
                await self._scan_mfe_source(state, js_url, tree_root)

                await self._extract_chunks_from_tree(
                    state,
                    js_url,
                    src,
                    tree_root,
                )

                router_routes, named_routes, w3c_routes = (
                    route.extract_route_sets_from_tree(tree_root)
                )
            else:
                router_routes = set()
                named_routes = set()
                w3c_routes = set()
            state.add_route_facts(
                router_routes,
                source="router_table",
                evidence_url=js_url,
            )
            state.add_route_facts(
                named_routes,
                source="named_navigation",
                evidence_url=js_url,
            )
            state.add_route_facts(
                w3c_routes,
                source="w3c_navigation",
                evidence_url=js_url,
            )
            graph.processed_js_sources.add(js_url)
            del src

        from tracesurface.collection.artifacts.micro_frontend.service import (
            collect_micro_frontend,
        )

        await collect_micro_frontend(state)

        await self.entry_fetcher.fetch(state)

    async def _extract_chunks_from_html(
        self,
        state: DiscoverySession,
        html: str,
    ) -> int:
        page = state.ports.page
        if page is None:
            return 0
        sink: set[str] = set()
        added = await self.chunk_service.extract_chunk_urls(
            page,
            html,
            state.target_url,
            sink=sink,
        )
        state.add_js_urls(
            sink,
            source="bundler_runtime",
            evidence_url=state.target_url,
        )
        return added

    async def _extract_chunks_from_tree(
        self,
        state: DiscoverySession,
        source_url: str,
        source: str,
        tree_root,
    ) -> int:
        page = state.ports.page
        if page is None:
            return 0
        sink: set[str] = set()
        added = await self.chunk_service.extract_chunk_urls_from_tree(
            page,
            source_url,
            source,
            tree_root,
            state.target_url,
            sink=sink,
        )
        state.add_js_urls(
            sink,
            source="bundler_runtime",
            evidence_url=state.target_url,
        )
        return added

    async def _scan_mfe_source(
        self, state: DiscoverySession, js_url: str, tree_root
    ) -> None:
        if js_url not in state.cache.source_scans:
            from tracesurface.collection.artifacts.micro_frontend.scanner import (
                scan_source_tree,
            )

            state.cache.source_scans[js_url] = scan_source_tree(tree_root)


def default_artifact_explorer() -> ArtifactExplorer:
    return ArtifactExplorer()
