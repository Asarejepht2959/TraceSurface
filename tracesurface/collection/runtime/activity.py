from __future__ import annotations

import asyncio

from tracesurface.config import DEFAULT_SETTINGS
from tracesurface.urls import dedup_key


class UniqueActivityTracker:
    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.last_activity: float = 0.0

    def mark(self, key: str, now: float) -> bool:
        if not key or key in self.keys:
            return False
        self.keys.add(key)
        self.last_activity = now
        return True

    def mark_js(self, url: str, now: float) -> bool:
        return self.mark(f"JS {url}", now)

    def mark_request(self, method: str, url: str, now: float) -> bool:
        return self.mark(f"REQ {dedup_key(method, url)}", now)


async def wait_for_unique_activity(
    tracker: UniqueActivityTracker,
    *,
    deadline_at: float,
    min_observe_ms: int = DEFAULT_SETTINGS.collection.route_min_observe_ms,
    quiet_ms: int = DEFAULT_SETTINGS.collection.route_activity_quiet_ms,
) -> bool:
    loop = asyncio.get_running_loop()
    start = loop.time()

    if tracker.last_activity <= 0:
        tracker.last_activity = start
    min_observe_s = max(0, min_observe_ms) / 1000
    quiet_s = max(0, quiet_ms) / 1000
    while True:
        now = loop.time()
        remaining = deadline_at - now

        if remaining <= 0:
            return True

        observed_enough = now - start >= min_observe_s
        quiet_enough = now - tracker.last_activity >= quiet_s
        if observed_enough and quiet_enough:
            return False

        await asyncio.sleep(min(0.05, remaining))
