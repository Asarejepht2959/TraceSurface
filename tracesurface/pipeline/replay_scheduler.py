from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from tracesurface.models import ReplayRecord, ReplayResult
from tracesurface.pipeline.messages import ReplayDoneItem, ReplayPendingItem
from tracesurface.replay.dedup import ReplayDedupStore
from tracesurface.storage.commands import Flush, SaveReplayRecord
from tracesurface.storage.sqlite.writer import StorageWriterPort


class ReplayScheduler:
    def __init__(
        self,
        *,
        storage_writer: StorageWriterPort,
        replay_workers: int,
        replay_concurrency: int,
        output_queue: asyncio.Queue[Any],
        run_replay_job: Callable[..., Awaitable[ReplayResult]],
    ) -> None:
        self.storage_writer = storage_writer
        self.replay_workers = max(1, replay_workers)
        self.replay_concurrency = max(1, replay_concurrency)
        self.output_queue = output_queue
        self.run_replay_job = run_replay_job
        self.pending: deque[ReplayPendingItem] = deque()
        self.tasks: set[asyncio.Task[None]] = set()
        self.run_dedup_store = ReplayDedupStore()
        self.active = 0
        self.stopping = False

    def submit(self, item: ReplayPendingItem) -> None:
        self.pending.append(item)

        self._pump()

    async def join(self) -> None:
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        self.stopping = True
        for task in self.tasks:
            task.cancel()
        await self.join()

    def _pump(self) -> None:
        if self.stopping:
            return

        while self.active < self.replay_workers and self.pending:
            self.active += 1
            task = asyncio.create_task(self._run_item(self.pending.popleft()))

            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    async def _run_item(self, item: ReplayPendingItem) -> None:
        async def save_replay_record(rec: ReplayRecord) -> None:
            await self.storage_writer.fire_and_forget(SaveReplayRecord(rec))

        try:
            replay_result = await self.run_replay_job(
                item.replay_job,
                concurrency=self.replay_concurrency,
                on_record=save_replay_record,
                dedup_store=self.run_dedup_store,
            )

            await self.storage_writer.submit(Flush())

            await self.output_queue.put(
                ReplayDoneItem(
                    job=item.job,
                    summary=item.summary,
                    replay_result=replay_result,
                    started_at=item.started_at,
                )
            )
        except Exception as exc:
            with suppress(Exception):
                await self.storage_writer.submit(Flush())

            await self.output_queue.put(
                ReplayDoneItem(
                    job=item.job,
                    summary=item.summary,
                    started_at=item.started_at,
                    error=exc,
                )
            )
        finally:
            self.active -= 1
            self._pump()
