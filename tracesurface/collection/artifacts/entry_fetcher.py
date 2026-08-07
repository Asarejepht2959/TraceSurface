from __future__ import annotations

from tracesurface.collection.artifacts.html import extract_html_js_urls
from tracesurface.collection.discovery.fact_store import clean_url
from tracesurface.collection.session import DiscoverySession
from tracesurface.config import DEFAULT_SETTINGS


class MFEEntryFetcher:
    async def fetch(self, state: DiscoverySession) -> int:
        graph = state.facts

        pending = sorted(graph.mfe_entry_urls - graph.fetched_mfe_entries)
        if not pending:
            return 0

        fetched = 0

        headers = {"Referer": state.target_url}

        for url in pending:
            graph.fetched_mfe_entries.add(url)
            try:
                resp = await state.ports.http.get(
                    url,
                    timeout=DEFAULT_SETTINGS.http.timeout_s,
                    headers=headers,
                    follow_redirects=True,
                )

            except Exception:
                continue
            if resp.status_code != 200:
                continue

            text = resp.text or ""
            ct = (resp.headers.get("content-type", "") or "").lower()
            if "html" not in ct and "<script" not in text.lower():
                continue

            final_url = clean_url(str(resp.url))
            if state.add_html_source(final_url, text, source="mfe_entry_html"):
                fetched += 1
                state.add_js_urls(
                    extract_html_js_urls(text, final_url),
                    source="mfe_entry_html",
                    evidence_url=final_url,
                )
        return fetched
