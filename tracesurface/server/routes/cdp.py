from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

import tracesurface.storage.sqlite.queries as queries
from tracesurface.server.routes.common import parse_csv

router = APIRouter()


@router.get("/api/cdp_requests")
def cdp_requests_list(
    target: str = "",
    methods: str | None = None,
    q: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
):
    total, items = queries.query_cdp_requests(
        target=target,
        methods=parse_csv(methods),
        q=q,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "items": items}


@router.get("/api/cdp_requests/{req_id}")
def cdp_request_detail(req_id: int):
    request = queries.get_cdp_request(req_id)
    if not request:
        raise HTTPException(404, "cdp_request not found")
    return request
