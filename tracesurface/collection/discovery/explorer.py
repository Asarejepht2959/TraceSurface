from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Explorer(Protocol):
    name: str
    run_once: bool

    async def discover(self, session, round_num: int = 0) -> ExplorerResult: ...


@dataclass(frozen=True, slots=True)
class ExplorerResult:
    new_js: int = 0
    new_html: int = 0
    new_routes: int = 0
    new_cdp: int = 0
