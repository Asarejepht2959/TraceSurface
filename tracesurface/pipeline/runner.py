from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from tracesurface.config import DEFAULT_SETTINGS
from tracesurface.pipeline.lifecycle import ScanLifecycle
from tracesurface.pipeline.messages import BatchScanOutcome, NoMoreInference, ScanOutput
from tracesurface.pipeline.outcome import OutcomeRecorder
from tracesurface.pipeline.replay_scheduler import ReplayScheduler
from tracesurface.pipeline.storage_coordinator import StorageCoordinator
from tracesurface.pipeline.workers import PipelineQueues, RunConfig, StageWorkers
from tracesurface.storage.sqlite.writer import open_writer
from tracesurface.ui import configure_worker_logging


@dataclass(frozen=True, slots=True)
class ScanRequest:
    urls: tuple[str, ...]
    wait_ms: int
    site_concurrency: int
    replay_concurrency: int
    do_replay: bool
    output: ScanOutput
    extraction_workers: int = DEFAULT_SETTINGS.workers.extraction_workers
    inference_workers: int = DEFAULT_SETTINGS.workers.inference_workers
    replay_workers: int = DEFAULT_SETTINGS.workers.replay_workers
    auth_state: dict[str, Any] | None = None
    headed: bool = False
    allow_destructive: bool = False


class PipelineRunner:
    async def run(self, request: ScanRequest) -> list[BatchScanOutcome]:
        from tracesurface.replay.service import run_replay_job

        config = RunConfig.of(
            site_concurrency=request.site_concurrency,
            extraction_workers=request.extraction_workers,
            inference_workers=request.inference_workers,
            replay_workers=request.replay_workers,
            replay_concurrency=request.replay_concurrency,
        )

        replayed_key_counts: dict[str, int] = {}
        if request.do_replay:
            replayed_key_counts = await asyncio.to_thread(_load_replayed_keys)

        results: list[BatchScanOutcome] = []
        recorder = OutcomeRecorder(
            total=len(request.urls),
            output=request.output,
            results=results,
        )

        queues = PipelineQueues.create(config)

        storage_writer = open_writer()
        await storage_writer.start()
        lifecycle = ScanLifecycle(
            storage_writer=storage_writer,
            target_replay_key_counts_loader=_load_target_replayed_keys,
            cdp_replay_targets_loader=_load_cdp_replay_targets,
            wait_ms=request.wait_ms,
            do_replay=request.do_replay,
            replayed_key_counts=replayed_key_counts,
        )
        replay_scheduler = ReplayScheduler(
            storage_writer=storage_writer,
            replay_workers=config.replay_workers,
            replay_concurrency=config.replay_concurrency,
            output_queue=queues.storage,
            run_replay_job=run_replay_job,
        )
        coordinator = StorageCoordinator(
            lifecycle=lifecycle,
            replay_scheduler=replay_scheduler,
            recorder=recorder,
            do_replay=request.do_replay,
            allow_destructive=request.allow_destructive,
        )

        queues.seed_jobs(request.urls, config.site_concurrency)

        collector_executor = ProcessPoolExecutor(
            max_workers=config.site_concurrency,
            initializer=configure_worker_logging,
        )
        extraction_executor = ProcessPoolExecutor(
            max_workers=config.extraction_workers,
            initializer=configure_worker_logging,
        )
        inference_executor = ProcessPoolExecutor(
            max_workers=config.inference_workers,
            initializer=configure_worker_logging,
        )

        workers = StageWorkers(
            queues=queues,
            loop=asyncio.get_running_loop(),
            lifecycle=lifecycle,
            collector_executor=collector_executor,
            extraction_executor=extraction_executor,
            inference_executor=inference_executor,
            auth_state=request.auth_state,
            headed=request.headed,
        )

        try:
            collectors = [
                asyncio.create_task(workers.run_collector())
                for _ in range(config.site_concurrency)
            ]
            extractors = [
                asyncio.create_task(workers.run_extraction())
                for _ in range(config.extraction_workers)
            ]
            inferers = [
                asyncio.create_task(workers.run_inference())
                for _ in range(config.inference_workers)
            ]

            storage_task = asyncio.create_task(coordinator.run(queues.storage))

            await asyncio.gather(*collectors)

            for _ in extractors:
                await queues.collection.put(None)
            await asyncio.gather(*extractors)

            for _ in inferers:
                await queues.extraction.put(None)
            await asyncio.gather(*inferers)

            await queues.storage.put(NoMoreInference())
            await storage_task

            await replay_scheduler.join()
        finally:
            cleanup_error: BaseException | None = None
            try:
                await replay_scheduler.shutdown()
            except Exception as exc:
                cleanup_error = cleanup_error or exc
            try:
                await storage_writer.stop()
            except Exception as exc:
                cleanup_error = cleanup_error or exc

            for executor in (
                inference_executor,
                extraction_executor,
                collector_executor,
            ):
                try:
                    executor.shutdown(wait=True, cancel_futures=True)
                except Exception as exc:
                    cleanup_error = cleanup_error or exc

            if cleanup_error is not None and sys.exc_info()[1] is None:
                raise cleanup_error

        return results


def _load_replayed_keys() -> dict[str, int]:
    from tracesurface.storage.sqlite.connection import init
    from tracesurface.storage.sqlite.repositories import load_replayed_key_counts

    init()
    return load_replayed_key_counts()


def _load_target_replayed_keys(target_url: str) -> dict[str, int]:
    from tracesurface.storage.sqlite.connection import init
    from tracesurface.storage.sqlite.repositories import (
        load_replayed_key_counts_for_target,
    )

    init()
    return load_replayed_key_counts_for_target(target_url)


def _load_cdp_replay_targets(scan_id: int) -> list[dict[str, Any]]:
    from tracesurface.storage.sqlite.connection import init
    from tracesurface.storage.sqlite.repositories import load_cdp_replay_targets

    init()
    return load_cdp_replay_targets(scan_id)
