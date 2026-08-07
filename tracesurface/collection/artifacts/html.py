from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from tracesurface.collection import route
from tracesurface.collection.discovery.fact_store import clean_url
from tracesurface.htmlast import extract_inline_scripts


@dataclass(frozen=True, slots=True)
class HtmlAssetResult:
    js_urls: frozenset[str] = field(default_factory=frozenset)
    router_routes: frozenset[str] = field(default_factory=frozenset)
    named_routes: frozenset[str] = field(default_factory=frozenset)
    w3c_routes: frozenset[str] = field(default_factory=frozenset)


class _HTMLAssetParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        tag_name = tag.lower()

        if tag_name == "script":
            src = attr.get("src", "")
            if src:
                self._add(src)
            return
        if tag_name != "link":
            return

        rel = {part.strip().lower() for part in attr.get("rel", "").split()}
        as_attr = attr.get("as", "").lower()
        href = attr.get("href", "")
        if href and (
            "modulepreload" in rel or ("preload" in rel and as_attr == "script")
        ):
            self._add(href)

    def _add(self, href: str) -> None:
        url = clean_url(urljoin(self.base_url, href))
        if urlparse(url).path.endswith((".js", ".mjs")):
            self.urls.add(url)


def extract_html_js_urls(html: str, base_url: str) -> set[str]:
    parser = _HTMLAssetParser(base_url)
    parser.feed(html or "")
    return parser.urls


class HtmlAssetExtractor:
    def extract(self, html: str, base_url: str) -> HtmlAssetResult:
        router_routes: set[str] = set()
        named_routes: set[str] = set()
        w3c_routes: set[str] = set()

        for _line, script in extract_inline_scripts(html or ""):
            try:
                inline_router, inline_named, inline_w3c = route.extract_route_sets(
                    script
                )
            except Exception:
                continue
            router_routes |= inline_router
            named_routes |= inline_named
            w3c_routes |= inline_w3c
        return HtmlAssetResult(
            js_urls=frozenset(extract_html_js_urls(html, base_url)),
            router_routes=frozenset(router_routes),
            named_routes=frozenset(named_routes),
            w3c_routes=frozenset(w3c_routes),
        )
