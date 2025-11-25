import base64
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.scrapers.scrape_raw_bill_documents import (
    RawBillDocumentScraper,
    BASE_URL,
)
from backend.database.raw_models import Base, RawBill, RawBillDocuments
from sqlalchemy.exc import SQLAlchemyError


# ---------- helpers for in-memory DB ----------

def _setup_inmemory_db():
    """Create in-memory SQLite engine and session factory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# ---------- filter_steps ----------

def test_filter_steps_filters_existing(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    # Seed DB with some RawBillDocuments for a given bill_id
    with SessionLocal() as session:
        session.add_all(
            [
                RawBillDocuments(
                    timestamp=datetime.now(timezone.utc),
                    bill_id="2021_1",
                    step_date=datetime.now(timezone.utc),
                    seguimiento_id=1,
                    archivo_id=111,
                    url="http://example.com/a",
                    text="A",
                ),
                RawBillDocuments(
                    timestamp=datetime.now(timezone.utc),
                    bill_id="2021_1",
                    step_date=datetime.now(timezone.utc),
                    seguimiento_id=3,
                    archivo_id=333,
                    url="http://example.com/c",
                    text="C",
                ),
            ]
        )
        session.commit()

    extracted_steps = [
        {"seguimientoPleyId": 1},
        {"seguimientoPleyId": 2},
        {"seguimientoPleyId": 3},
    ]

    remaining = scraper.filter_steps(extracted_steps, bill_id="2021_1")
    # seguimiento 1 and 3 exist in DB => only 2 should remain
    assert len(remaining) == 1
    assert remaining[0]["seguimientoPleyId"] == 2


# ---------- get_bill_urls ----------

def test_get_bill_urls_raises_if_bill_not_found():
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    with pytest.raises(AssertionError):
        scraper.get_bill_urls(bill_id="2021_999")


def test_get_bill_urls_populates_urls_and_calls_render_pdf(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    # Create a RawBill with one step and one file
    bill_id = "2021_1"
    step_date_str = "2021-01-01T12:00:00.000000+0000"
    steps = [
        {
            "seguimientoPleyId": 10,
            "fecha": step_date_str,
            "archivos": [
                {
                    "proyectoArchivoId": 111,
                    "seguimientoPleyId": 10,
                }
            ],
        }
    ]

    with SessionLocal() as session:
        session.add(
            RawBill(
                id=bill_id,
                timestamp=datetime.now(timezone.utc),
                general=None,
                committees=None,
                congresistas=None,
                steps=json.dumps(steps),
            )
        )
        session.commit()

    # Patch render_pdf so we don't hit network/PDF
    calls = []

    def fake_render_pdf(url):
        calls.append(url)
        return f"TEXT_FROM_{url}"

    monkeypatch.setattr(
        "backend.scrapers.scrape_raw_bill_documents.render_pdf", fake_render_pdf
    )

    scraper.get_bill_urls(bill_id=bill_id)

    # Should have called render_pdf once
    assert len(calls) == 1
    # b64 of "111"
    expected_b64 = base64.b64encode(b"111").decode()
    expected_url = f"{BASE_URL}/archivo/{expected_b64}/pdf"
    assert calls[0] == expected_url

    # Scraper should have one RawBillDocuments object
    assert len(scraper.urls) == 1
    doc = scraper.urls[0]
    assert doc.bill_id == bill_id
    assert doc.archivo_id == 111
    assert doc.seguimiento_id == 10
    assert doc.url == expected_url
    assert doc.text == f"TEXT_FROM_{expected_url}"
    # step_date parsed correctly
    assert isinstance(doc.step_date, datetime)


def test_get_bill_urls_respects_update_flag(monkeypatch):
    """When update=False, filter_steps is used; when update=True, it should not be used."""
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    bill_id = "2021_2"
    steps = [
        {
            "seguimientoPleyId": 1,
            "fecha": "2021-01-01T00:00:00.000000+0000",
            "archivos": [
                {"proyectoArchivoId": 999, "seguimientoPleyId": 1},
            ],
        }
    ]

    with SessionLocal() as session:
        session.add(
            RawBill(
                id=bill_id,
                timestamp=datetime.now(timezone.utc),
                general=None,
                committees=None,
                congresistas=None,
                steps=json.dumps(steps),
            )
        )
        session.commit()

    # Patch render_pdf to avoid network
    monkeypatch.setattr(
        "backend.scrapers.scrape_raw_bill_documents.render_pdf",
        lambda url: "OK",
    )

    # Case 1: update=False and filter_steps returns empty -> no URLs
    def fake_filter_steps(_steps, _bill_id):
        return []

    monkeypatch.setattr(scraper, "filter_steps", fake_filter_steps)

    scraper.get_bill_urls(bill_id=bill_id, update=False)
    assert len(scraper.urls) == 0

    # Case 2: update=True should bypass filter_steps
    scraper.urls = []  # reset

    scraper.get_bill_urls(bill_id=bill_id, update=True)
    assert len(scraper.urls) == 1
    assert scraper.urls[0].bill_id == bill_id


# ---------- add_documents_to_db ----------

def test_add_documents_to_db_persists(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawBillDocumentScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    bill_id = "2021_3"
    doc = RawBillDocuments(
        timestamp=datetime.now(timezone.utc),
        bill_id=bill_id,
        step_date=datetime.now(timezone.utc),
        seguimiento_id=1,
        archivo_id=123,
        url="http://example.com/doc.pdf",
        text="SOME TEXT",
    )
    scraper.urls = [doc]

    assert scraper.add_documents_to_db() is True

    with SessionLocal() as session:
        count = session.query(RawBillDocuments).count()
        assert count == 1
        db_doc = session.query(RawBillDocuments).first()
        assert db_doc.bill_id == bill_id
        assert db_doc.archivo_id == '123'
        assert db_doc.text == "SOME TEXT"


def test_add_documents_to_db_asserts_when_empty():
    scraper = RawBillDocumentScraper()
    scraper.urls = []

    with pytest.raises(AssertionError):
        scraper.add_documents_to_db()


def test_add_documents_to_db_handles_sqlalchemy_error():
    scraper = RawBillDocumentScraper()
    scraper.urls = [
        RawBillDocuments(
            timestamp=datetime.now(timezone.utc),
            bill_id="2021_4",
            step_date=datetime.now(timezone.utc),
            seguimiento_id=1,
            archivo_id=1,
            url="http://example.com",
            text="TEXT",
        )
    ]

    class DummySession:
        def __init__(self):
            self.rolled_back = False

        def bulk_save_objects(self, objs):
            raise SQLAlchemyError("boom")

        def commit(self):
            pass

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    dummy_session = DummySession()

    def fake_sessionmaker():
        return dummy_session

    scraper.Session = fake_sessionmaker

    ok = scraper.add_documents_to_db()
    assert ok is False
    assert dummy_session.rolled_back is True


# ---------- load_raw_documents ----------

def test_load_raw_documents_calls_add_and_clears(monkeypatch):
    scraper = RawBillDocumentScraper()
    # Put a dummy object so assertion in add_documents_to_db would pass
    scraper.urls = ["dummy"]

    calls = {"added": False}

    def fake_add():
        calls["added"] = True
        return True

    monkeypatch.setattr(scraper, "add_documents_to_db", fake_add)

    scraper.load_raw_documents()

    assert calls["added"] is True
    assert scraper.urls == []
