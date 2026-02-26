from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from loguru import logger
from PIL import Image

from backend.ocr.classifier import classify_page
from backend.ocr.pdf_pages import iter_pdf_pages_as_png_bytes
from backend.ocr.providers.base import OCRProvider
from backend.ocr.repository import OCRRepository
from backend.ocr.types import OCRPageResult, OCRPageTask, OCRSourceDocument
from backend.scrapers.utils import get_url


@dataclass(slots=True)
class OCRPipelineConfig:
    prompt: str = "<image>\nFree OCR."
    queue_maxsize: int = 32
    workers: int = 1
    page_dpi: int = 220
    documents_limit: int | None = None
    include_bills: bool = True
    include_motions: bool = True
    only_without_pages: bool = True


@dataclass(slots=True)
class OCRPipelineStats:
    documents_scanned: int = 0
    documents_completed: int = 0
    documents_failed: int = 0
    pages_processed: int = 0
    pages_failed: int = 0


async def _download_pdf(url: str) -> bytes | None:
    response = await asyncio.to_thread(get_url, url)
    if response is None:
        return None

    try:
        response.raise_for_status()
    except Exception:
        return None

    return response.content


async def _producer(
    documents: list[OCRSourceDocument],
    task_queue: asyncio.Queue,
    config: OCRPipelineConfig,
    stats: OCRPipelineStats,
    doc_status: dict[int, bool],
) -> None:
    for source in documents:
        stats.documents_scanned += 1
        pdf_bytes = await _download_pdf(source.url)
        if not pdf_bytes:
            logger.warning(f"Failed to download PDF: {source.url}")
            doc_status[source.parent_doc_id] = False
            continue

        try:
            for page_number, image_bytes in iter_pdf_pages_as_png_bytes(
                pdf_bytes, dpi=config.page_dpi
            ):
                await task_queue.put(
                    OCRPageTask(
                        source=source,
                        page_number=page_number,
                        image_bytes=image_bytes,
                    )
                )
        except Exception as exc:
            logger.warning(
                f"Failed to split PDF for parent_doc_id={source.parent_doc_id}: {exc}"
            )
            doc_status[source.parent_doc_id] = False

    for _ in range(config.workers):
        await task_queue.put(None)


async def _worker(
    provider: OCRProvider,
    prompt: str,
    task_queue: asyncio.Queue,
    result_queue: asyncio.Queue,
) -> None:
    while True:
        task = await task_queue.get()
        if task is None:
            await result_queue.put(None)
            task_queue.task_done()
            return

        assert isinstance(task, OCRPageTask)

        text = ""
        error = None
        processed = False
        page_type = "other"

        try:
            image = Image.open(BytesIO(task.image_bytes)).convert("RGB")
            text = await asyncio.to_thread(provider.extract_text, image, prompt)
            page_type = classify_page(text)
            processed = True
        except Exception as exc:
            error = str(exc)

        result = OCRPageResult(
            source=task.source,
            page_number=task.page_number,
            text=text,
            page_type=page_type,
            ocr_provider=provider.name,
            ocr_model=provider.model_name,
            prompt=prompt,
            processed=processed,
            timestamp=datetime.now(),
            error=error,
        )
        await result_queue.put(result)
        task_queue.task_done()


async def _writer(
    repository: OCRRepository,
    result_queue: asyncio.Queue,
    workers: int,
    stats: OCRPipelineStats,
    doc_status: dict[int, bool],
) -> None:
    done_workers = 0
    while done_workers < workers:
        result = await result_queue.get()
        if result is None:
            done_workers += 1
            result_queue.task_done()
            continue

        assert isinstance(result, OCRPageResult)
        try:
            await asyncio.to_thread(repository.upsert_page_result, result)
            stats.pages_processed += 1
        except Exception as exc:
            logger.warning(
                "Failed to persist OCR page "
                f"parent_doc_id={result.source.parent_doc_id} page={result.page_number}: {exc}"
            )
            stats.pages_failed += 1
            doc_status[result.source.parent_doc_id] = False
        else:
            if result.error:
                stats.pages_failed += 1
                doc_status[result.source.parent_doc_id] = False
            else:
                doc_status.setdefault(result.source.parent_doc_id, True)

        result_queue.task_done()


async def run_ocr_pipeline_async(
    *,
    repository: OCRRepository,
    provider: OCRProvider,
    config: OCRPipelineConfig,
) -> OCRPipelineStats:
    docs = repository.fetch_pending_documents(
        limit=config.documents_limit,
        include_bills=config.include_bills,
        include_motions=config.include_motions,
        only_without_pages=config.only_without_pages,
    )

    stats = OCRPipelineStats()
    if not docs:
        return stats

    task_queue: asyncio.Queue = asyncio.Queue(maxsize=config.queue_maxsize)
    result_queue: asyncio.Queue = asyncio.Queue(maxsize=config.queue_maxsize)

    doc_status: dict[int, bool] = {}

    producer_task = asyncio.create_task(
        _producer(docs, task_queue, config, stats, doc_status)
    )
    worker_tasks = [
        asyncio.create_task(_worker(provider, config.prompt, task_queue, result_queue))
        for _ in range(config.workers)
    ]
    writer_task = asyncio.create_task(
        _writer(repository, result_queue, config.workers, stats, doc_status)
    )

    await producer_task
    await task_queue.join()
    await asyncio.gather(*worker_tasks)
    await result_queue.join()
    await writer_task

    grouped_sources: dict[int, OCRSourceDocument] = {
        source.parent_doc_id: source for source in docs
    }

    for parent_doc_id, source in grouped_sources.items():
        success = doc_status.get(parent_doc_id, False)
        await asyncio.to_thread(
            repository.mark_parent_document_processed,
            source,
            success=success,
        )
        if success:
            stats.documents_completed += 1
        else:
            stats.documents_failed += 1

    return stats


def run_ocr_pipeline(
    *,
    repository: OCRRepository,
    provider: OCRProvider,
    config: OCRPipelineConfig,
) -> OCRPipelineStats:
    logger.info(
        "Starting page-level OCR pipeline with "
        f"provider={provider.name} model={provider.model_name}"
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_ocr_pipeline_async(
                repository=repository,
                provider=provider,
                config=config,
            )
        )

    raise RuntimeError(
        "run_ocr_pipeline() cannot be called from a running event loop. "
        "In notebooks, use: `await run_ocr_pipeline_async(...)`."
    )
