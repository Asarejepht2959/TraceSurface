from __future__ import annotations

from tracesurface.models import (
    APIMatch,
    CallerInfo,
    ClientRef,
    Lit,
    RequestFact,
    SourceLocation,
    UrlTemplate,
)


def match_to_request_fact(m: APIMatch) -> RequestFact:
    location = SourceLocation(
        url=m.url, line=m.line, col_start=m.col_start, col_end=m.col_end
    )
    caller = CallerInfo(
        module_id=m.module_id,
        caller_var=m.caller_var,
        caller_prop=m.caller_prop,
        require_id=m.require_id,
    )

    template = (
        m.url_template if m.url_template is not None else UrlTemplate((Lit(m.path),))
    )
    client_refs: tuple[ClientRef, ...] = (
        (m.client_ref,) if m.client_ref is not None else ()
    )
    return RequestFact(
        request_id=f"{m.url}:{m.line}:{m.col_start}",
        method=m.method,
        path=m.path,
        url_template=template,
        client_refs=client_refs,
        params=tuple(m.params),
        location=location,
        caller=caller,
        pattern=m.pattern,
    )
