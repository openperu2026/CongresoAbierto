from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.raw_models import (
    Base,
    RawBillDocument,
    RawDocumentPage,
)
from backend.ocr.repository import OCRRepository
from backend.ocr.types import OCRPageResult


def _make_repo(tmp_path):
    db_path = tmp_path / "raw.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:
        session.add(
            RawBillDocument(
                timestamp=datetime.now(),
                bill_id="2021_1",
                step_date=datetime.now(),
                seguimiento_id="10",
                archivo_id="100",
                url="https://example.com/a.pdf",
                text="",
                processed=False,
                last_update=True,
            )
        )
        session.commit()

    return OCRRepository(db_url)


def test_fetch_pending_documents(tmp_path):
    repo = _make_repo(tmp_path)
    docs = repo.fetch_pending_documents(include_motions=False)

    assert len(docs) == 1
    assert docs[0].parent_type == "bill"


def test_fetch_pending_documents_skips_processed_documents(tmp_path):
    repo = _make_repo(tmp_path)

    engine = create_engine(repo.engine.url)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        row = session.query(RawBillDocument).first()
        row.processed = True
        session.add(row)
        session.commit()

    docs = repo.fetch_pending_documents(include_motions=False)
    assert docs == []


def test_upsert_page_result_and_mark_parent_processed(tmp_path):
    repo = _make_repo(tmp_path)
    source = repo.fetch_pending_documents(include_motions=False)[0]

    result = OCRPageResult(
        source=source,
        page_number=1,
        text="Resultados de Votación",
        page_type="vote",
        ocr_provider="deepseek",
        ocr_model="deepseek-ai/DeepSeek-OCR",
        prompt="<image>\\nFree OCR.",
        processed=True,
        timestamp=datetime.now(),
    )

    repo.upsert_page_result(result)
    repo.mark_parent_document_processed(source, success=True)

    engine = create_engine(repo.engine.url)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        pages = session.query(RawDocumentPage).all()
        assert len(pages) == 1
        assert pages[0].page_type == "vote"

        parent = session.query(RawBillDocument).first()
        assert parent.processed is True
        assert "Votación" in parent.text
