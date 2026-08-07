from __future__ import annotations

import asyncio
from collections.abc import Set

from tracesurface.urls import dedup_key


class ReplayDedupStore:
    def __init__(self) -> None:
        self._run_seen: set[str] = set()
        self._lock = asyncio.Lock()

    async def claim(
        self,
        method: str,
        url: str,
        *,
        db_seen_keys: Set[str] | None = None,
    ) -> bool:
        key = dedup_key(method, url)
        db_seen = db_seen_keys or ()

        async with self._lock:
            if key in db_seen or key in self._run_seen:
                return False
            self._run_seen.add(key)
            return True
