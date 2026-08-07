from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from tracesurface.models import (
    CollectionBundle,
    ExtractionResult,
    InferenceResult,
    ScanJob,
)
from tracesurface.pipeline.lifecycle import ScanLifecycle
from tracesurface.pipeline.messages import (
    CollectedItem,
    ExtractedItem,
    InferredItem,
    NoMoreInference,
    ReplayDoneItem,
    SkippedItem,
    StageFailure,
)


@dataclass(frozen=True, slots=True)
class RunConfig:
    site_concurrency: int
    extraction_workers: int
    inference_workers: int
    replay_workers: int
    replay_concurrency: int

    @classmethod
    def of(
        cls,
        *,
        site_concurrency: int,
        extraction_workers: int,
        inference_workers: int,
        replay_workers: int,
        replay_concurrency: int,
    ) -> "RunConfig":
        return cls(
            site_concurrency=max(1, site_concurrency),
            extraction_workers=max(1, extraction_workers),
            inference_workers=max(1, inference_workers),
            replay_workers=max(1, replay_workers),
            replay_concurrency=max(1, replay_concurrency),
        )


@dataclass(frozen=True, slots=True)
class PipelineQueues:
    job: asyncio.Queue[str | None]
    collection: asyncio.Queue[CollectedItem | None]
    extraction: asyncio.Queue[ExtractedItem | None]
    storage: asyncio.Queue[
        InferredItem | SkippedItem | StageFailure | ReplayDoneItem | NoMoreInference
    ]

    @classmethod
    def create(cls, config: RunConfig) -> "PipelineQueues":
        return cls(
            job=asyncio.Queue(),
            collection=asyncio.Queue(maxsize=max(1, config.site_concurrency * 2)),
            extraction=asyncio.Queue(maxsize=max(1, config.extraction_workers * 2)),
            storage=asyncio.Queue(
                maxsize=max(1, config.inference_workers * 2 + config.replay_workers),
            ),
        )

    def seed_jobs(self, urls: tuple[str, ...], worker_count: int) -> None:
        for url in urls:
            self.job.put_nowait(url)

        for _ in range(worker_count):
            self.job.put_nowait(None)


@dataclass(slots=True)
class StageWorkers:
    queues: PipelineQueues
    loop: asyncio.AbstractEventLoop
    lifecycle: ScanLifecycle
    collector_executor: ProcessPoolExecutor
    extraction_executor: ProcessPoolExecutor
    inference_executor: ProcessPoolExecutor
    auth_state: dict[str, Any] | None = None
    headed: bool = False

    async def run_collector(self) -> None:
        while True:
            target_url = await self.queues.job.get()
            try:
                if target_url is None:
                    return
                started_at = time.perf_counter()

                scan_id: int | None = None
                try:
                    job = await self.lifecycle.prepare_target(target_url)
                    scan_id = job.scan_id

                    bundle = await self.loop.run_in_executor(
                        self.collector_executor,
                        _collect,
                        job,
                        self.auth_state,
                        self.headed,
                    )

                    if bundle.skipped:
                        await self.queues.storage.put(
                            SkippedItem(
                                job=job,
                                warnings=tuple(bundle.warnings),
                                started_at=started_at,
                            )
                        )
                        continue

                    await self.queues.collection.put(
                        CollectedItem(job=job, bundle=bundle, started_at=started_at)
                    )
                except Exception as exc:
                    await self.queues.storage.put(
                        StageFailure(
                            url=target_url,
                            scan_id=scan_id,
                            stage="collect",
                            error=exc,
                            started_at=started_at,
                        )
                    )
            finally:
                self.queues.job.task_done()

    async def run_extraction(self) -> None:
        await self._consume(
            self.queues.collection,
            self.queues.extraction,
            self._extract_one,
            "extraction",
        )

    async def run_inference(self) -> None:
        await self._consume(
            self.queues.extraction,
            self.queues.storage,
            self._infer_one,
            "inference",
        )

    async def _extract_one(self, item: CollectedItem) -> ExtractedItem:
        extraction = await self.loop.run_in_executor(
            self.extraction_executor,
            _extract,
            item.bundle,
        )
        return ExtractedItem(
            job=item.job,
            bundle=item.bundle,
            extraction=extraction,
            started_at=item.started_at,
        )

    async def _infer_one(self, item: ExtractedItem) -> InferredItem:
        inference = await self.loop.run_in_executor(
            self.inference_executor,
            _infer,
            item.bundle,
            item.extraction,
        )
        return InferredItem(
            job=item.job,
            inference=inference,
            started_at=item.started_at,
        )

    async def _consume(
        self,
        in_queue: asyncio.Queue[Any],
        out_queue: asyncio.Queue[Any],
        process: Callable[[Any], Awaitable[Any]],
        stage: str,
    ) -> None:
        while True:
            item = await in_queue.get()
            try:
                if item is None:
                    return
                try:
                    await out_queue.put(await process(item))
                except Exception as exc:
                    await self.queues.storage.put(
                        StageFailure(
                            url=item.job.target_url,
                            scan_id=item.job.scan_id,
                            stage=stage,
                            error=exc,
                            started_at=item.started_at,
                        )
                    )
            finally:
                in_queue.task_done()


def _collect(
    job: ScanJob,
    auth_state: dict[str, Any] | None,
    headed: bool,
) -> CollectionBundle:
    from tracesurface.collection.worker import collect_job

    return collect_job(job, auth_state=auth_state, headed=headed)


def _extract(bundle: CollectionBundle) -> ExtractionResult:
    from tracesurface.extraction.extractor import extract_collection

    return extract_collection(bundle)


def _infer(bundle: CollectionBundle, extraction: ExtractionResult) -> InferenceResult:
    from tracesurface.inference.service import infer

    return infer(bundle, extraction)
