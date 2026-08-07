from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Page

from tracesurface.collection.runtime.activity import (
    UniqueActivityTracker,
    wait_for_unique_activity,
)
from tracesurface.collection.runtime.request_classifier import (
    RequestClassifier,
    is_business_js,
)
from tracesurface.config import DEFAULT_SETTINGS
from tracesurface.models import CDPRequest, CDPResult, StackFrame
from tracesurface.policies import ResponseCapturePolicy, TargetContext


def _expand_stack(stack: dict[str, Any]) -> list[StackFrame]:
    frames = []

    current = stack
    while current:
        for f in current.get("callFrames", []):
            url = f.get("url", "")

            if not url or url.startswith("chrome://"):
                continue
            frames.append(
                StackFrame(
                    url=url.split("?")[0],
                    func=f.get("functionName", "") or "(匿名)",
                    line=f.get("lineNumber", 0),
                    col=f.get("columnNumber", 0),
                )
            )

        current = current.get("parent")
    return frames


@dataclass(frozen=True, slots=True)
class CDPCollectRequest:
    target_url: str
    wait_ms: int
    goto_timeout_ms: int
    total_timeout_ms: int | None = None
    unique_activity_wait: bool = False
    full_wait: bool = False


class CDPTraceSession:
    def __init__(
        self,
        request_classifier: RequestClassifier | None = None,
        capture_policy: ResponseCapturePolicy | None = None,
    ) -> None:
        self.request_classifier = request_classifier or RequestClassifier()
        self.capture_policy = capture_policy or ResponseCapturePolicy()

    async def collect(self, page: Page, request: CDPCollectRequest) -> CDPResult:
        target_url = request.target_url
        wait_ms = request.wait_ms
        goto_timeout_ms = request.goto_timeout_ms
        route_total_timeout_ms = request.total_timeout_ms
        unique_activity_wait = request.unique_activity_wait
        full_wait = request.full_wait

        loop = asyncio.get_running_loop()
        classifier = self.request_classifier
        capture = self.capture_policy
        target_context = TargetContext(requested_url=target_url)

        deadline_at = (
            loop.time() + max(0, route_total_timeout_ms) / 1000
            if route_total_timeout_ms is not None
            else None
        )

        bootstrap_deadline_at: float | None = None

        def _seconds_until(deadline: float | None, cap: float | None = None) -> float:
            if deadline is None:
                return cap if cap is not None else float("inf")
            remaining = max(0.0, deadline - loop.time())
            return min(remaining, cap) if cap is not None else remaining

        def _remaining_seconds(cap: float | None = None) -> float:
            return _seconds_until(deadline_at, cap)

        def _remaining_ms(cap_ms: int) -> int:
            if deadline_at is None:
                return cap_ms
            return max(1, min(cap_ms, int(_remaining_seconds() * 1000)))

        js_urls: set[str] = set()
        requests: list[CDPRequest] = []

        requests_by_id: dict[str, CDPRequest] = {}

        text_body_pending: set[str] = set()

        json_response_bodies: dict[str, str] = {}

        dropped_no_stack_count = 0
        dropped_no_stack_samples: list[str] = []
        activity = UniqueActivityTracker()
        timed_out = False
        timeout_reasons: list[str] = []
        collection_error = ""
        navigation_ok = True

        track_unique_activity = unique_activity_wait or route_total_timeout_ms is None

        def _add_timeout_reason(reason: str) -> None:
            if reason and reason not in timeout_reasons:
                timeout_reasons.append(reason)

        pending_body_tasks: list[asyncio.Task[None]] = []

        client = await page.context.new_cdp_session(page)
        try:
            await client.send("Network.enable")
            await client.send("Debugger.enable")
            await client.send(
                "Debugger.setAsyncCallStackDepth",
                {"maxDepth": DEFAULT_SETTINGS.collection.cdp_stack_depth},
            )

            def on_request(params):
                nonlocal dropped_no_stack_count
                url = params["request"]["url"]
                req_type = params.get("type", "")
                classification = classifier.classify_cdp_request(
                    url,
                    req_type,
                    target_context,
                )

                if classification.is_js:
                    clean_url = url.split("?")[0]
                    if is_business_js(
                        clean_url, target_context, classifier.third_party
                    ):
                        js_urls.add(clean_url)
                        if track_unique_activity:
                            activity.mark_js(
                                clean_url, asyncio.get_running_loop().time()
                            )
                    return

                if req_type not in ("Fetch", "XHR"):
                    return
                if not classification.keep:
                    return

                stack = params.get("initiator", {}).get("stack")
                if not stack:
                    dropped_no_stack_count += 1
                    if len(dropped_no_stack_samples) < 5:
                        dropped_no_stack_samples.append(url)
                    return

                req = params["request"]
                parsed = urlparse(url)
                req_headers = req.get("headers", {}) or {}
                cdp_req = CDPRequest(
                    request_url=url,
                    request_path=parsed.path,
                    method=req["method"],
                    query_string=parsed.query,
                    post_data=req.get("postData", ""),
                    content_type=req_headers.get("Content-Type", "")
                    or req_headers.get("content-type", ""),
                    frames=_expand_stack(stack),
                    request_headers=dict(req_headers),
                )
                requests.append(cdp_req)
                if track_unique_activity:
                    activity.mark_request(
                        cdp_req.method,
                        cdp_req.request_url,
                        asyncio.get_running_loop().time(),
                    )

                request_id = params.get("requestId")
                if request_id:
                    requests_by_id[request_id] = cdp_req

            def on_response(params):
                resp = params.get("response", {})
                req_type = params.get("type", "")

                if req_type not in ("Fetch", "XHR"):
                    return
                request_id = params.get("requestId")
                if not request_id or request_id not in requests_by_id:
                    return

                cdp_req = requests_by_id[request_id]
                cdp_req.response_status = resp.get("status") or None
                headers = resp.get("headers", {}) or {}
                cdp_req.response_headers = dict(headers)

                if capture.is_text_mime(resp.get("mimeType", "")):
                    text_body_pending.add(request_id)

            async def on_loading_finished(params):
                request_id = params.get("requestId")
                if not request_id or request_id not in text_body_pending:
                    return
                text_body_pending.discard(request_id)
                cdp_req = requests_by_id.get(request_id)
                if cdp_req is None:
                    return

                if params.get("encodedDataLength", 0) > capture.body_capture_limit:
                    return

                try:
                    result = await client.send(
                        "Network.getResponseBody",
                        {"requestId": request_id},
                    )
                except Exception:
                    return
                body = result.get("body", "")

                if result.get("base64Encoded"):
                    return
                if len(body) > capture.body_capture_limit:
                    return
                cdp_req.response_body = body
                cdp_req.response_size = len(body.encode("utf-8", errors="replace"))

                ct = ""
                for k, v in cdp_req.response_headers.items():
                    if k.lower() == "content-type":
                        ct = (v or "").lower()
                        break
                if "json" in ct:
                    json_response_bodies[cdp_req.request_url.split("?")[0]] = body

            def _dispatch_body(p):
                pending_body_tasks.append(asyncio.create_task(on_loading_finished(p)))

            client.on("Network.requestWillBeSent", on_request)
            client.on("Network.responseReceived", on_response)
            client.on("Network.loadingFinished", _dispatch_body)

            try:
                await page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=_remaining_ms(goto_timeout_ms),
                )

                if route_total_timeout_ms is None:
                    bootstrap_deadline_at = loop.time() + max(0, wait_ms) / 1000
            except Exception as exc:
                if route_total_timeout_ms is None:
                    raise
                collection_error = repr(exc)
                navigation_ok = False
                timed_out = deadline_at is not None and loop.time() >= deadline_at

                if timed_out or "Timeout" in collection_error:
                    _add_timeout_reason("goto_timeout")

            if unique_activity_wait and navigation_ok:
                if deadline_at is not None and loop.time() < deadline_at:
                    activity_timed_out = await wait_for_unique_activity(
                        activity,
                        deadline_at=deadline_at,
                    )
                    if activity_timed_out:
                        _add_timeout_reason("unique_activity_deadline")
                    timed_out = activity_timed_out or timed_out

            elif navigation_ok and bootstrap_deadline_at is not None:
                if full_wait:
                    await asyncio.sleep(max(0.0, bootstrap_deadline_at - loop.time()))

                    bootstrap_deadline_at = loop.time() + max(0, goto_timeout_ms) / 1000
                else:
                    activity_timed_out = await wait_for_unique_activity(
                        activity,
                        deadline_at=bootstrap_deadline_at,
                        min_observe_ms=DEFAULT_SETTINGS.collection.bootstrap_min_observe_ms,
                        quiet_ms=DEFAULT_SETTINGS.collection.bootstrap_activity_quiet_ms,
                    )
                    if activity_timed_out:
                        _add_timeout_reason("unique_activity_deadline")
                    timed_out = activity_timed_out or timed_out
        finally:
            if pending_body_tasks:
                try:
                    timeout_s = _seconds_until(
                        deadline_at or bootstrap_deadline_at, 2.0
                    )

                    if timeout_s <= 0:
                        timed_out = timed_out or (
                            deadline_at is not None or bootstrap_deadline_at is not None
                        )
                        _add_timeout_reason("body_no_time_left")
                        raise asyncio.TimeoutError

                    await asyncio.wait_for(
                        asyncio.gather(*pending_body_tasks, return_exceptions=True),
                        timeout=timeout_s,
                    )
                except asyncio.TimeoutError:
                    timed_out = timed_out or (
                        deadline_at is not None or bootstrap_deadline_at is not None
                    )
                    _add_timeout_reason("body_gather_timeout")
                    for t in pending_body_tasks:
                        if not t.done():
                            t.cancel()

            await client.detach()

        seen = set()
        unique = []
        for r in requests:
            if r.dedup_key not in seen:
                seen.add(r.dedup_key)
                unique.append(r)

        html_content = ""
        try:
            if navigation_ok:
                content_timeout_s = _seconds_until(
                    deadline_at or bootstrap_deadline_at,
                )

                if content_timeout_s <= 0:
                    timed_out = timed_out or (
                        deadline_at is not None or bootstrap_deadline_at is not None
                    )
                    _add_timeout_reason("page_content_no_time_left")
                else:
                    html_content = await asyncio.wait_for(
                        page.content(),
                        timeout=content_timeout_s,
                    )
        except asyncio.TimeoutError:
            timed_out = timed_out or (
                deadline_at is not None or bootstrap_deadline_at is not None
            )
            _add_timeout_reason("page_content_timeout")
        except Exception as exc:
            collection_error = collection_error or f"{type(exc).__name__}: {exc}"

        if timed_out and not timeout_reasons:
            _add_timeout_reason("deadline")

        last_activity_age_ms = 0
        if activity.last_activity > 0:
            last_activity_age_ms = max(
                0, int((loop.time() - activity.last_activity) * 1000)
            )

        return CDPResult(
            target_url=target_url,
            js_urls=js_urls,
            requests=unique,
            html_content=html_content,
            json_response_bodies=json_response_bodies,
            dropped_no_stack_count=dropped_no_stack_count,
            dropped_no_stack_samples=dropped_no_stack_samples,
            timed_out=timed_out,
            timeout_reasons=timeout_reasons,
            unique_activity_count=len(activity.keys),
            last_activity_age_ms=last_activity_age_ms,
            pending_body_task_count=len(pending_body_tasks),
            unfinished_body_task_count=sum(
                1 for t in pending_body_tasks if not t.done()
            ),
            collection_error=collection_error,
        )
