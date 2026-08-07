from __future__ import annotations

import asyncio
import atexit
import logging
from typing import Any

import httpx
from playwright.async_api import Browser, Playwright, async_playwright

from tracesurface.config import DEFAULT_SETTINGS
from tracesurface.models import CollectionBundle, ScanJob

_loop: asyncio.AbstractEventLoop | None = None
_playwright: Playwright | None = None
_browser: Browser | None = None
_http_client: httpx.AsyncClient | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop

    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


async def _ensure_resources(*, headed: bool) -> tuple[Browser, httpx.AsyncClient]:
    global _playwright, _browser, _http_client

    if _browser is not None and not _browser.is_connected():
        _browser = None

    if _browser is None:
        from tracesurface.collection.runtime.browser_context import launch_browser

        if _playwright is None:
            _playwright = await async_playwright().start()
        _browser = await launch_browser(_playwright, headless=not headed)

    if _http_client is None:
        _http_client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_SETTINGS.browser.user_agent},
            verify=DEFAULT_SETTINGS.http.tls_verify,
        )

    return _browser, _http_client


async def _collect_async(
    job: ScanJob,
    *,
    auth_state: dict[str, Any] | None,
    headed: bool,
) -> CollectionBundle:
    from tracesurface.collection.service import collect_site

    browser, http_client = await _ensure_resources(headed=headed)
    http_client.cookies.clear()

    try:
        return await collect_site(
            target_url=job.target_url,
            browser=browser,
            wait_ms=job.wait_ms,
            http_client=http_client,
            scan_id=job.scan_id,
            auth_state=auth_state,
            headed=headed,
        )
    finally:
        http_client.cookies.clear()


def collect_job(
    job: ScanJob,
    *,
    auth_state: dict[str, Any] | None = None,
    headed: bool = False,
) -> CollectionBundle:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return _get_loop().run_until_complete(
        _collect_async(job, auth_state=auth_state, headed=headed),
    )


async def _shutdown_async() -> None:
    global _playwright, _browser, _http_client

    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None


def shutdown_collector_worker() -> None:
    loop = _loop

    if loop is None or loop.is_closed():
        return

    loop.run_until_complete(_shutdown_async())
    loop.close()


atexit.register(shutdown_collector_worker)
