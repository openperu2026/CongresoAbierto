from datetime import datetime

import pytest
from lxml.html import fromstring
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.scrapers.committees import (
    RawCommitteeScraper,
    BASE_URL,
)
from backend.database.raw_models import Base, RawCommittee


# ---------- helpers for DB tests ----------


def _setup_inmemory_db():
    """Create in-memory SQLite engine and session factory for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# ---------- get_options ----------


def test_get_options_parses_select(monkeypatch):
    scraper = RawCommitteeScraper()

    def fake_parse_url(url, *args, **kwargs):
        assert url == BASE_URL
        html = """
        <html><body>
          <select name="idRegistroPadre">
            <option value="2021">2021</option>
            <option value="2022">2022</option>
            <option>--Seleccione--</option>
          </select>
        </body></html>
        """
        return fromstring(html)

    monkeypatch.setattr("backend.scrapers.committees.parse_url", fake_parse_url)

    options = scraper.get_options(url=BASE_URL, select_name="idRegistroPadre")

    # At least the real options should be present
    assert options["2021"] == "2021"
    assert options["2022"] == "2022"
    # Placeholder may or may not be present; if it is, value can be None
    if "--Seleccione--" in options:
        assert options["--Seleccione--"] is None


# ---------- get_html_with_selections ----------


def test_get_html_with_selections_success(monkeypatch):
    scraper = RawCommitteeScraper()

    # Fake webdriver + Select so no real browser is used
    class FakeElement:
        def __init__(self, name):
            self.name = name

    class FakeDriver:
        def __init__(self, *args, **kwargs):
            self.got_url = None
            self._page_source = "<html>OK</html>"

        def get(self, url):
            self.got_url = url

        def find_element(self, by, value):
            # Just return a dummy element for both selects
            return FakeElement(value)

        @property
        def page_source(self):
            return self._page_source

        def quit(self):
            pass

    class FakeSelect:
        def __init__(self, element):
            self.element = element
            self.selected_value = None

        def select_by_value(self, value):
            self.selected_value = value

    # Patch Chrome constructor and Select inside the scraper module
    monkeypatch.setattr(
        "backend.scrapers.committees.webdriver.Chrome",
        lambda *a, **k: FakeDriver(),
    )
    monkeypatch.setattr(
        "backend.scrapers.committees.Select",
        FakeSelect,
    )

    html = scraper.get_html_with_selections(BASE_URL, "2021", "COM")
    assert html == "<html>OK</html>"


def test_get_html_with_selections_handles_no_such_element(monkeypatch):
    from selenium.common.exceptions import NoSuchElementException

    scraper = RawCommitteeScraper()

    class FakeDriver:
        def get(self, url):
            pass

        def find_element(self, by, value):
            raise NoSuchElementException("not found")

        @property
        def page_source(self):
            return "<html>SHOULD NOT SEE</html>"

        def quit(self):
            pass

    monkeypatch.setattr(
        "backend.scrapers.committees.webdriver.Chrome",
        lambda *a, **k: FakeDriver(),
    )

    html = scraper.get_html_with_selections(BASE_URL, "2021", "COM")
    assert html is None


# ---------- get_raw_committees ----------


def test_get_raw_committees_builds_committee_list(monkeypatch):
    scraper = RawCommitteeScraper()

    # 2 years x 2 types = 4 combinations
    def fake_get_options(url, select_name="idRegistroPadre"):
        if select_name == "idRegistroPadre":
            return {"2021": "2021", "2022": "2022"}
        if select_name == "fld_78_Comision":
            return {"Permanente": "1", "Especial": "2"}
        raise AssertionError("Unexpected select_name")

    # For simplicity, return non-None HTML for only some combos
    def fake_get_html_with_selections(url, year_value, committee_value):
        # Return None for one particular combo to test skipping
        if year_value == "2022" and committee_value == "2":
            return None
        return f"<html>Year={year_value},Type={committee_value}</html>"

    monkeypatch.setattr(scraper, "get_options", fake_get_options)
    monkeypatch.setattr(
        scraper, "get_html_with_selections", fake_get_html_with_selections
    )

    scraper.get_raw_committees()

    # 3 non-None combos should produce 3 RawCommittee objects
    assert hasattr(scraper, "committee_list")
    assert len(scraper.committee_list) == 3

    for rc in scraper.committee_list:
        assert isinstance(rc, RawCommittee)
        assert isinstance(rc.timestamp, datetime)
        assert rc.legislative_year in (2021, 2022)
        assert rc.committee_type in ("Permanente", "Especial")
        assert "<html>" in rc.raw_html


# ---------- add_committees_to_db ----------


def test_add_committees_to_db_persists(monkeypatch):
    engine, SessionLocal = _setup_inmemory_db()

    scraper = RawCommitteeScraper()
    scraper.engine = engine
    scraper.Session = SessionLocal

    committee = RawCommittee(
        timestamp=datetime(2021, 1, 1),
        legislative_year=2021,
        committee_type="Permanente",
        raw_html="<html>data</html>",
    )
    scraper.committee_list = [committee]

    assert scraper.add_committees_to_db() is True

    with SessionLocal() as session:
        count = session.query(RawCommittee).count()
        assert count == 1
        db_obj = session.query(RawCommittee).first()
        assert db_obj.legislative_year == 2021
        assert db_obj.committee_type == "Permanente"
        assert db_obj.raw_html == "<html>data</html>"


def test_add_committees_to_db_asserts_when_empty():
    scraper = RawCommitteeScraper()
    scraper.committee_list = []

    with pytest.raises(AssertionError):
        scraper.add_committees_to_db()


def test_add_committees_to_db_handles_sqlalchemy_error(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    scraper = RawCommitteeScraper()
    scraper.committee_list = [
        RawCommittee(
            timestamp=datetime.now(),
            legislative_year=2021,
            committee_type="Permanente",
            raw_html="<html></html>",
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

    ok = scraper.add_committees_to_db()
    assert ok is False
    assert dummy_session.rolled_back is True
