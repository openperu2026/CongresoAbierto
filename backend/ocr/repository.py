from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, exists, select, update
from sqlalchemy.orm import sessionmaker

from backend.database.raw_models import (
    Base as RawBase,
    RawBillDocument,
    RawDocumentPage,
    RawMotionDocument,
)
from backend.ocr.types import OCRPageResult, OCRSourceDocument


class OCRRepository:
    def __init__(self, raw_db_url: str):
        self.engine = create_engine(raw_db_url, pool_pre_ping=True)
        RawBase.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def fetch_pending_documents(
        self,
        *,
        limit: int | None = None,
        include_bills: bool = True,
        include_motions: bool = True,
        only_without_pages: bool = True,
    ) -> list[OCRSourceDocument]:
        docs: list[OCRSourceDocument] = []

        with self.Session() as session:
            if include_bills:
                stmt = select(RawBillDocument).where(RawBillDocument.last_update.is_(True))
                if only_without_pages:
                    stmt = stmt.where(
                        ~exists(
                            select(RawDocumentPage.id).where(
                                RawDocumentPage.parent_type == "bill",
                                RawDocumentPage.parent_doc_id == RawBillDocument.id,
                            )
                        )
                    )
                if limit is not None:
                    stmt = stmt.limit(limit)

                for row in session.scalars(stmt).all():
                    docs.append(
                        OCRSourceDocument(
                            parent_type="bill",
                            parent_doc_id=row.id,
                            parent_natural_id=row.bill_id,
                            seguimiento_id=str(row.seguimiento_id),
                            archivo_id=str(row.archivo_id),
                            url=row.url,
                        )
                    )

            if include_motions:
                motion_limit = None
                if limit is not None:
                    motion_limit = max(limit - len(docs), 0)
                    if motion_limit == 0:
                        return docs

                stmt = select(RawMotionDocument).where(
                    RawMotionDocument.last_update.is_(True)
                )
                if only_without_pages:
                    stmt = stmt.where(
                        ~exists(
                            select(RawDocumentPage.id).where(
                                RawDocumentPage.parent_type == "motion",
                                RawDocumentPage.parent_doc_id == RawMotionDocument.id,
                            )
                        )
                    )
                if motion_limit is not None:
                    stmt = stmt.limit(motion_limit)

                for row in session.scalars(stmt).all():
                    docs.append(
                        OCRSourceDocument(
                            parent_type="motion",
                            parent_doc_id=row.id,
                            parent_natural_id=row.motion_id,
                            seguimiento_id=str(row.seguimiento_id),
                            archivo_id=str(row.archivo_id),
                            url=row.url,
                        )
                    )

        return docs

    def upsert_page_result(self, result: OCRPageResult) -> None:
        with self.Session() as session:
            existing = session.scalar(
                select(RawDocumentPage).where(
                    RawDocumentPage.parent_type == result.source.parent_type,
                    RawDocumentPage.parent_doc_id == result.source.parent_doc_id,
                    RawDocumentPage.page_number == result.page_number,
                    RawDocumentPage.ocr_model == result.ocr_model,
                )
            )

            if existing:
                existing.timestamp = result.timestamp
                existing.text = result.text
                existing.page_type = result.page_type
                existing.ocr_provider = result.ocr_provider
                existing.prompt = result.prompt
                existing.error = result.error
                existing.processed = result.processed
                existing.last_update = True
            else:
                page = RawDocumentPage(
                    timestamp=result.timestamp,
                    parent_type=result.source.parent_type,
                    parent_doc_id=result.source.parent_doc_id,
                    parent_natural_id=result.source.parent_natural_id,
                    seguimiento_id=result.source.seguimiento_id,
                    archivo_id=result.source.archivo_id,
                    url=result.source.url,
                    page_number=result.page_number,
                    text=result.text,
                    page_type=result.page_type,
                    ocr_provider=result.ocr_provider,
                    ocr_model=result.ocr_model,
                    prompt=result.prompt,
                    error=result.error,
                    processed=result.processed,
                    last_update=True,
                )
                session.add(page)

            session.commit()

    def mark_parent_document_processed(self, source: OCRSourceDocument, *, success: bool) -> None:
        text_stmt = select(RawDocumentPage.text).where(
            RawDocumentPage.parent_type == source.parent_type,
            RawDocumentPage.parent_doc_id == source.parent_doc_id,
        )
        with self.Session() as session:
            page_texts = [text for text in session.scalars(text_stmt).all() if text]
            aggregated = "\n\n".join(page_texts)

            if source.parent_type == "bill":
                session.execute(
                    update(RawBillDocument)
                    .where(RawBillDocument.id == source.parent_doc_id)
                    .values(text=aggregated, processed=success, timestamp=datetime.now())
                )
            else:
                session.execute(
                    update(RawMotionDocument)
                    .where(RawMotionDocument.id == source.parent_doc_id)
                    .values(text=aggregated, processed=success, timestamp=datetime.now())
                )

            session.commit()
