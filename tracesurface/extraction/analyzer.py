from __future__ import annotations

from tracesurface.extraction.matcher_context import MatcherContext
from tracesurface.extraction.registry import MatcherFn
from tracesurface.htmlast import extract_inline_scripts
from tracesurface.jsast import (
    JsParser,
    walk_pre_iter,
)
from tracesurface.models import APIMatch


def build_byte_to_char_offsets(source: str) -> list[list[int]]:
    table = []
    for line in source.split("\n"):
        byte_to_char = []
        char_idx = 0

        for ch in line:
            for _ in range(len(ch.encode("utf-8"))):
                byte_to_char.append(char_idx)
            char_idx += 1

        byte_to_char.append(char_idx)
        table.append(byte_to_char)
    return table


def byte_col_to_char_col(table: list[list[int]], line: int, byte_col: int) -> int:
    if line >= len(table):
        return table[-1][-1]
    row = table[line]
    if byte_col >= len(row):
        return row[-1]
    return row[byte_col]


class ASTAnalyzer:
    def __init__(
        self,
        parser: JsParser,
        matchers: tuple[tuple[str, MatcherFn], ...],
    ) -> None:
        self.parser = parser
        self.matchers = matchers

    def _collect_matches(
        self,
        tree,
        source: str,
        js_url: str,
        wrapper_prefixes: dict[str, str] | None = None,
    ):
        matchers = self.matchers
        byte_to_char = build_byte_to_char_offsets(source)

        from tracesurface.extraction.caller import (
            extract_esm_imports,
            extract_module_requires_webpack,
            fill_caller_info,
            is_webpack,
        )

        is_webpack_fmt = is_webpack(source)
        module_requires: dict[str, dict[str, str]] = {}
        esm_imports: dict[str, tuple[str, str]] = {}

        if is_webpack_fmt:
            module_requires = extract_module_requires_webpack(tree.root_node)
        else:
            esm_imports = extract_esm_imports(source)

        from tracesurface.extraction.resolve import ResolveCtx, request_client_ref
        from tracesurface.extraction.scope import build_scope_index

        ctx = ResolveCtx(
            scope_index=build_scope_index(tree.root_node),
            is_webpack=is_webpack_fmt,
            js_url=js_url,
            module_requires=module_requires,
            esm_imports=esm_imports,
        )
        if wrapper_prefixes is None:
            from tracesurface.extraction.wrappers import learn_wrapper_prefixes

            wrapper_prefixes = learn_wrapper_prefixes(source)
        matcher_ctx = MatcherContext(ctx, wrapper_prefixes=wrapper_prefixes)

        matches: list[APIMatch] = []
        seen: set[str] = set()

        for node in walk_pre_iter(tree.root_node):
            for name, fn in matchers:
                result = fn(node, matcher_ctx)
                if result is None:
                    continue

                result.url = js_url
                result.pattern = name
                result.col_start = byte_col_to_char_col(
                    byte_to_char, result.line, result.col_start
                )
                result.col_end = byte_col_to_char_col(
                    byte_to_char, result.line, result.col_end
                )

                fill_caller_info(
                    node,
                    result,
                    module_requires,
                    esm_imports,
                    is_webpack_fmt,
                    js_url,
                )

                result.client_ref = request_client_ref(node, ctx)

                dedup_key = f"{result.path}:{result.line}:{result.col_start}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    matches.append(result)
                break

        return matches, ctx

    def analyze_js_all(
        self,
        source: str,
        js_url: str = "",
        wrapper_prefixes: dict[str, str] | None = None,
    ):
        from tracesurface.extraction.facts_build import build_file_facts

        source = self.parser.normalize(source)
        tree = self.parser.parse(source)
        matches, ctx = self._collect_matches(tree, source, js_url, wrapper_prefixes)
        return build_file_facts(matches, tree.root_node, js_url, ctx)

    def analyze_html_inline_all(
        self,
        html: str,
        js_url: str = "",
        wrapper_prefixes: dict[str, str] | None = None,
    ):
        from tracesurface.extraction.facts_build import build_file_facts
        from tracesurface.models import ExtractionFacts

        facts_acc = ExtractionFacts()
        for start_line, script in extract_inline_scripts(html):
            norm = self.parser.normalize(script)
            tree = self.parser.parse(norm)
            local_matches, ctx = self._collect_matches(
                tree, norm, js_url, wrapper_prefixes
            )
            for match in local_matches:
                match.line += start_line
            file_facts = build_file_facts(local_matches, tree.root_node, js_url, ctx)
            facts_acc = ExtractionFacts(
                requests=facts_acc.requests + file_facts.requests,
                bases=facts_acc.bases + file_facts.bases,
                aliases=facts_acc.aliases + file_facts.aliases,
            )
        return facts_acc
