import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.raw_models import RawBase

# repo root: .../OpenPeru
ROOT = Path(__file__).resolve().parents[1]

# Ensure root is on sys.path so `import backend` works
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture()
def raw_engine():
    engine = create_engine("sqlite:///:memory:")
    RawBase.metadata.create_all(engine)
    return engine

@pytest.fixture()
def raw_session(raw_engine):
    SessionLocal = sessionmaker(bind=raw_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()