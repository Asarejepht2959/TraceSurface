from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx


class HttpClientTimeoutError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DiscoveryDeps:
    http: HttpTextClient
    page: Any | None = None
    browser: Any | None = None
    context_kwargs: dict[str, Any] | None = None


class HttpTextClient:
    def __init__(self, client) -> None:
        self.client = client

    async def get_text(
        self,
        url: str,
        *,
        timeout_s: float,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        try:
            resp = await self.client.get(url, timeout=timeout_s, headers=headers)
        except httpx.TimeoutException as exc:
            raise HttpClientTimeoutError(str(exc)) from exc
        return resp.status_code, resp.text or "", resp.headers.get("content-type", "")

    async def get(self, url: str, **kwargs) -> httpx.Response:
        try:
            return await self.client.get(url, **kwargs)
        except httpx.TimeoutException as exc:
            raise HttpClientTimeoutError(str(exc)) from exc

    def stream(self, method: str, url: str, **kwargs):
        return self._stream(method, url, **kwargs)

    @asynccontextmanager
    async def _stream(self, method: str, url: str, **kwargs):
        try:
            async with self.client.stream(method, url, **kwargs) as response:
                yield response
        except httpx.TimeoutException as exc:
            raise HttpClientTimeoutError(str(exc)) from exc
