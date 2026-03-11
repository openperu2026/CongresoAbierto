from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path

from loguru import logger
from PIL import Image

from backend.ocr.classifier import classify_page
from backend.ocr.pdf_pages import iter_pdf_pages_as_png_bytes
from backend.ocr.providers.base import OCRProvider
from backend.ocr.repository import OCRRepository
from backend.ocr.storage import PDFSourceResolver, PDFStorageConfig
from backend.ocr.types import OCRPageResult, OCRPageTask, OCRSourceDocument


@dataclass(slots=True)
class OCRPipelineConfig:
    prompt: str = "<image>\nFree OCR."
    queue_maxsize: int = 32
    workers: int = 1
    page_dpi: int = 220
    documents_limit: int | None = None
    include_bills: bool = True
    include_motions: bool = True
    skip_processed_documents: bool = True
    only_without_pages: bool = True
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    prefer_s3: bool = True
    http_fallback: bool = True
    deepseek_json_backup_dir: str | None = None
    deepseek_json_pretty: bool = True


@dataclass(slots=True)
class OCRPipelineStats:
    documents_scanned: int = 0
    documents_completed: int = 0
    documents_failed: int = 0
    pages_processed: int = 0
    pages_failed: int = 0


async def _producer(
    documents: list[OCRSourceDocument],
    task_queue: asyncio.Queue,
    config: OCRPipelineConfig,
    stats: OCRPipelineStats,
    doc_status: dict[int, bool],
    resolver: PDFSourceResolver,
) -> None:
    for source in documents:
        stats.documents_scanned += 1
        pdf_bytes = await asyncio.to_thread(resolver.resolve_pdf_bytes, source)
        if not pdf_bytes:
            logger.warning(
                "Failed to load PDF bytes "
                f"parent_type={source.parent_type} parent_doc_id={source.parent_doc_id}"
            )
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


def _write_deepseek_json_backups(
    backup_dir: Path,
    *,
    by_doc: dict[int, list[OCRPageResult]],
    pretty: bool,
) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for parent_doc_id, results in by_doc.items():
        if not results:
            continue
        source = results[0].source
        ordered = sorted(results, key=lambda r: r.page_number)
        payload = {
            "parent_type": source.parent_type,
            "parent_doc_id": source.parent_doc_id,
            "parent_natural_id": source.parent_natural_id,
            "seguimiento_id": source.seguimiento_id,
            "archivo_id": source.archivo_id,
            "source_url": source.url,
            "ocr_provider": ordered[0].ocr_provider,
            "ocr_model": ordered[0].ocr_model,
            "created_at": datetime.now().isoformat(),
            "pages": [
                {
                    "page_number": item.page_number,
                    "page_type": item.page_type,
                    "processed": item.processed,
                    "error": item.error,
                    "text": item.text,
                }
                for item in ordered
            ],
        }
        filename = (
            f"{source.parent_type}_{source.parent_natural_id}_"
            f"{source.seguimiento_id}_{source.archivo_id}.json"
        )
        out_path = backup_dir / filename
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None),
            encoding="utf-8",
        )


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
        skip_processed_documents=config.skip_processed_documents,
        only_without_pages=config.only_without_pages,
    )

    stats = OCRPipelineStats()
    if not docs:
        return stats

    task_queue: asyncio.Queue = asyncio.Queue(maxsize=config.queue_maxsize)
    result_queue: asyncio.Queue = asyncio.Queue(maxsize=config.queue_maxsize)

    doc_status: dict[int, bool] = {}
    storage = PDFSourceResolver(
        PDFStorageConfig(
            s3_bucket=config.s3_bucket,
            s3_prefix=config.s3_prefix,
            prefer_s3=config.prefer_s3,
            http_fallback=config.http_fallback,
        )
    )

    producer_task = asyncio.create_task(
        _producer(docs, task_queue, config, stats, doc_status, storage)
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

    if provider.name == "deepseek" and config.deepseek_json_backup_dir:
        by_doc: dict[int, list[OCRPageResult]] = {}
        for source in docs:
            rows = await asyncio.to_thread(
                repository.fetch_page_results_for_document,
                source,
                provider.model_name,
            )
            by_doc[source.parent_doc_id] = rows
        await asyncio.to_thread(
            _write_deepseek_json_backups,
            Path(config.deepseek_json_backup_dir),
            by_doc=by_doc,
            pretty=config.deepseek_json_pretty,
        )

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
