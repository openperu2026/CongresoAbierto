import pytest
from datetime import datetime, UTC

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from backend.database.raw_models import RawLey

from backend.scrapers.leyes import RawLeyesScraper


@pytest.fixture()
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture()
def db_session(engine):
    # Create tables
    RawLey.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def scraper(db_session):
    # Pass an existing session so the scraper does not create/close its own
    return RawLeyesScraper(session=db_session)


def test_create_raw_ley_sets_core_fields(scraper):
    ley_number = "32558"
    data = "<xml>hello</xml>"

    raw = scraper.create_raw_ley(ley_number, data)

    assert isinstance(raw, RawLey)
    assert raw.id == ley_number
    assert raw.data == data
    assert raw.processed is False
    assert isinstance(raw.timestamp, datetime)


def test_update_tracking_first_time_marks_changed_and_last_update(scraper, db_session):
    ley_number = "32558"
    data = "<xml>v1</xml>"

    ley = scraper.create_raw_ley(ley_number, data)
    tracked = scraper.update_tracking(ley)

    assert tracked is not None
    assert tracked.changed is True
    assert tracked.last_update is True

    # Nothing should exist in DB yet because update_tracking only flips old rows
    # New row will be inserted by add_leyes_to_db()
    assert db_session.query(RawLey).count() == 0


def test_update_tracking_second_time_flips_previous_last_update(scraper, db_session):
    ley_number = "32558"

    # Insert first version
    first = RawLey(
        id=ley_number,
        timestamp=datetime.now(UTC),
        data="<xml>v1</xml>",
        processed=False,
        last_update=True,
        changed=True,
    )
    db_session.add(first)
    db_session.commit()

    # Track second version
    second = scraper.create_raw_ley(ley_number, "<xml>v2</xml>")
    tracked = scraper.update_tracking(second)

    assert tracked.changed is True
    assert tracked.last_update is True

    # Previous row should now be last_update False
    prev = (
        db_session.query(RawLey)
        .filter(RawLey.id == ley_number)
        .order_by(RawLey.timestamp.desc())
        .all()
    )
    assert len(prev) == 1
    assert prev[0].last_update is False


def test_update_tracking_second_time_same_data_sets_changed_false(scraper, db_session):
    ley_number = "32558"

    # Insert first version with some data
    first = RawLey(
        id=ley_number,
        timestamp=datetime.now(UTC),
        data="<xml>same</xml>",
        processed=False,
        last_update=True,
        changed=True,
    )
    db_session.add(first)
    db_session.commit()

    second = scraper.create_raw_ley(ley_number, "<xml>same</xml>")
    tracked = scraper.update_tracking(second)

    assert tracked.changed is False
    assert tracked.last_update is True


def test_add_leyes_to_db_inserts_and_clears_tracking(scraper, db_session):
    ley_number = "32558"
    ley = scraper.create_raw_ley(ley_number, "<xml>v1</xml>")
    tracked = scraper.update_tracking(ley)

    scraper.raw_leyes.append(tracked)
    ok = scraper.add_leyes_to_db()

    assert ok is True
    rows = db_session.query(RawLey).filter(RawLey.id == ley_number).all()
    assert len(rows) == 1
    assert rows[0].last_update is True


def test_add_leyes_to_db_failure_restores_last_update(scraper, db_session, monkeypatch):
    ley_number = "32558"

    # Existing last row in DB
    existing = RawLey(
        id=ley_number,
        timestamp=datetime.now(UTC),
        data="<xml>v1</xml>",
        processed=False,
        last_update=True,
        changed=True,
    )
    db_session.add(existing)
    db_session.commit()

    # Track a new version which will flip existing.last_update to False
    new = scraper.create_raw_ley(ley_number, "<xml>v2</xml>")
    tracked = scraper.update_tracking(new)
    assert db_session.query(RawLey).first().last_update is False

    scraper.raw_leyes.append(tracked)

    # Force bulk_save_objects to fail so add_leyes_to_db triggers restore
    def boom(*args, **kwargs):
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(db_session, "bulk_save_objects", boom)

    ok = scraper.add_leyes_to_db()
    assert ok is False

    # Restore should have set last_update True back on the previous row
    restored = db_session.query(RawLey).filter(RawLey.id == ley_number).first()
    assert restored.last_update is True
