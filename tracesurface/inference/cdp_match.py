from __future__ import annotations

from dataclasses import dataclass

from tracesurface.models import (
    ApiCandidate,
    ApiResolution,
    CDPRequest,
    ConfirmedRequest,
    RequestFact,
)


@dataclass(frozen=True, slots=True)
class CDPASTMatchResult:
    resolutions: tuple[ApiResolution, ...]
    cdp_only: tuple[CDPRequest, ...]


def match_cdp_ast(
    cdp_requests: list[CDPRequest],
    request_facts: list[RequestFact],
) -> CDPASTMatchResult:
    facts_by_url: dict[str, list[RequestFact]] = {}
    for rf in request_facts:
        facts_by_url.setdefault(rf.location.url, []).append(rf)

    confirmed: dict[tuple[str, int, int], CDPRequest] = {}
    matched_req_keys: set[str] = set()

    for req in cdp_requests:
        for frame in req.frames:
            candidates = facts_by_url.get(frame.url, [])
            for rf in candidates:
                loc = rf.location

                if loc.line == frame.line and loc.col_start <= frame.col < loc.col_end:
                    key = (loc.url, loc.line, loc.col_start)
                    confirmed.setdefault(key, req)

                    matched_req_keys.add(req.dedup_key)

    resolutions: list[ApiResolution] = []
    for rf in request_facts:
        candidate = _request_fact_to_candidate(rf)
        loc = rf.location

        key = (loc.url, loc.line, loc.col_start)
        req = confirmed.get(key)
        if req is None:
            resolutions.append(
                ApiResolution(candidate=candidate, status="not_inferred")
            )
            continue

        request = ConfirmedRequest(
            method=req.method,
            url=req.request_url,
            path=req.request_path,
        )
        resolutions.append(
            ApiResolution(
                candidate=candidate,
                status="confirmed",
                full_url=req.request_url or None,
                confirmed=request,
            )
        )

    cdp_only = tuple(r for r in cdp_requests if r.dedup_key not in matched_req_keys)
    return CDPASTMatchResult(
        resolutions=tuple(resolutions),
        cdp_only=cdp_only,
    )


def _request_fact_to_candidate(rf: RequestFact) -> ApiCandidate:
    return ApiCandidate(
        path=rf.path,
        method=rf.method,
        pattern=rf.pattern,
        location=rf.location,
        params=tuple(rf.params),
        caller=rf.caller,
        url_template=rf.url_template,
        client_refs=rf.client_refs,
    )
