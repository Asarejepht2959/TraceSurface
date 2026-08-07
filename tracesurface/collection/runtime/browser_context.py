from __future__ import annotations

from playwright.async_api import Browser, Playwright


async def launch_browser(playwright: Playwright, *, headless: bool = True) -> Browser:
    try:
        return await playwright.chromium.launch(headless=headless)
    except Exception:
        return await playwright.chromium.launch(headless=headless, channel="chrome")
