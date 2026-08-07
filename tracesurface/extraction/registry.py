from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from tracesurface.extraction.matcher_context import MatcherContext
from tracesurface.models import APIMatch

MatcherFn = Callable[[Node, MatcherContext], APIMatch | None]


def build_default_matcher_registry() -> tuple[tuple[str, MatcherFn], ...]:
    from tracesurface.extraction.matchers.fetch_call import match_fetch_call
    from tracesurface.extraction.matchers.member_method import match_member_method
    from tracesurface.extraction.matchers.object_config import match_object_config
    from tracesurface.extraction.matchers.split_wrapper import match_split_wrapper
    from tracesurface.extraction.matchers.wrapped_call import match_wrapped_call
    from tracesurface.extraction.matchers.xhr_open import match_xhr_open

    return (
        ("split-wrapper", match_split_wrapper),
        ("member-method", match_member_method),
        ("object-config", match_object_config),
        ("fetch-call", match_fetch_call),
        ("xhr-open", match_xhr_open),
        ("wrapped-call", match_wrapped_call),
    )
