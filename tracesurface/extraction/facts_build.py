from __future__ import annotations

from tree_sitter import Node

from tracesurface.extraction.aliases import build_aliases
from tracesurface.extraction.base_facts import extract_base_facts
from tracesurface.extraction.request_facts import match_to_request_fact
from tracesurface.extraction.resolve import ResolveCtx
from tracesurface.models import APIMatch, ExtractionFacts


def build_file_facts(
    matches: list[APIMatch],
    root: Node,
    js_url: str,
    ctx: ResolveCtx,
) -> ExtractionFacts:
    requests = tuple(match_to_request_fact(m) for m in matches)
    bases = tuple(extract_base_facts(root, js_url, ctx))
    aliases = tuple(build_aliases(root, ctx))
    return ExtractionFacts(requests=requests, bases=bases, aliases=aliases)
