from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from ..config import settings

# Import all models from the models.py file
from .models import Base
from .raw_models import Base as RawBase

import os

def _ensure_columns(base, engine, cols: list[str] = ['last_update', 'changed', 'processed']):
    """
    For each table in `base`, if the SQLAlchemy model defines a 'processed'
    column but the actual DB table does not have it yet, add it via ALTER TABLE.

    This is written for SQLite; adjust the ALTER TABLE statement if you move
    to Postgres/MySQL.
    """
    inspector = inspect(engine)

    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            table_name = table.name

            for col_name in cols:
                # Only act if the model defines a 'processed' column
                if col_name not in table.c:
                    continue

                existing_cols = {col["name"] for col in inspector.get_columns(table_name)}

                if col_name in existing_cols:
                    # Already present in DB
                    continue

                print(f"[MIGRATION] Adding '{col_name}' column to table '{table_name}'")

                # SQLite: BOOLEAN is fine, stored as 0/1
                conn.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN '{col_name}' BOOLEAN NOT NULL DEFAULT 0"
                    )
                )


def create_database(base, db_url: str):
    """
    Create a SQLite database (Raw or Clean) with all tables from the models,
    only if the database file does not already exist.
    """
    # Extract path from the URL (assuming format sqlite:///path/to/dbfile.db)
    if not db_url.startswith("sqlite:///"):
        raise ValueError("This function only supports SQLite databases.")

    db_path = db_url.replace("sqlite:///", "")

    engine = create_engine(db_url)

    # If DB exists, just ensure all tables are present
    if os.path.exists(db_path):
        print(f"Database already exists: {db_path}, ensuring all tables are present...")
        try:
            base.metadata.create_all(engine)
            _ensure_columns(base, engine)
        except SQLAlchemyError as e:
            print(f"Error updating existing database schema: {e}")
            return False        
        return False

    # If DB does not exist, create it and all tables
    try:
        base.metadata.create_all(engine)

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            )
            tables = [row[0] for row in result.fetchall()]

        print(f"Database created successfully at {db_path} with {len(tables)} tables.")
        return True

    except SQLAlchemyError as e:
        print(f"Error creating database: {e}")
        return False


if __name__ == "__main__":
    create_database(RawBase, settings.RAW_DB_URL)
    create_database(Base, settings.DB_URL)
