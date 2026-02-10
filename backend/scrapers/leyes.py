import json
import time
from datetime import datetime
from loguru import logger

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.scrapers.utils import get_url_text
from backend.database.raw_models import RawLey

BASE_URL = "https://api.congreso.gob.pe/adlp-visor-service/expediente/ley?numley="
RAW_DB_PATH = settings.RAW_DB_URL

class RawLeyesScraper:
    """
    Class to scrape and store raw ley information
    """

    def __init__(self, session = None, engine = None):
        # Engine and session maker for DB
        if session is not None:
            self.session = session
            self.engine = session.get_bind()
            self.Session = sessionmaker(bind=self.engine)  # safe default
        else:
            self.engine = engine or create_engine(RAW_DB_PATH)
            self.Session = sessionmaker(bind=self.engine)
            self.session = None

        # List of raw leyes objects
        self.raw_leyes = []

    def scrape_ley(self, ley_number: str) -> None:
        """
        Scrape data from ley api request
        """

        ley_url = f"{BASE_URL}{ley_number}"
        response = get_url_text(ley_url)

        if response:
            # Successfully built the raw ley!
            ley = self.create_raw_ley(ley_number, response)
            self.raw_leyes.append(self.update_tracking(ley))
            logger.success(f"Successfully scraped Raw Ley {ley_number}")

        else:
            return None

    def create_raw_ley(self, ley_number: str, data: str) -> RawLey:
        # Initialize raw ley with id and timestamp
        raw_ley = RawLey(
            id=ley_number, timestamp=datetime.now(), data = data, processed=False
        )

        return raw_ley

    def update_tracking(self, ley: RawLey) -> RawLey:
        """Update the tracking columns of a RawLey object"""

        # Create a new session
        session = self.session or self.Session()
        try:
            last_ley = (
                session.query(RawLey)
                .filter(RawLey.id == ley.id)
                .order_by(RawLey.timestamp.desc())
                .first()
            )

            # First ever version of this ley
            if last_ley is None:
                ley.changed = True
                ley.last_update = True
            else:
                # Compare last vs new
                ley.changed = ley != last_ley
                ley.last_update = True

                # Update the old version AFTER comparison
                last_ley.last_update = False
                session.add(last_ley)
                session.commit()

            return ley
        except SQLAlchemyError as e:
            logger.error(f"Failed to add update tracking to Raw Leyes table: {e}")
            session.rollback()
            return False

        finally:
            # Close Session
            if self.session is None:
                session.close()

    def add_leyes_to_db(self) -> bool:
        """
        Add a single ley to the database.
        Returns True on success, False on failure.
        """
        assert len(self.raw_leyes) != 0, (
            "There are no Raw Leyes scraped. Nothing to load to DB."
        )

        # Create a new session
        session = self.session or self.Session()
        try:
            # Add and commit raw ley
            session.bulk_save_objects(self.raw_leyes)
            session.commit()
            logger.success(f"Added {len(self.raw_leyes)} Raw Leyes to table.")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to add leyes to Raw Leyes table: {e}")
            session.rollback()
            return False

        finally:
            # Close Session
            if self.session is None:
                session.close()

    def load_raw_leyes(self):
        self.add_leyes_to_db()
        self.raw_leyes = []


def main():
    scraper = RawLeyesScraper()

    #Pending: 16243, 10548, 9918, 9865, 9866, 9867, 9868, 9870

    num_ley = 17011
    while True:
        try:
            scraper.scrape_ley(str(num_ley))
        except TypeError:
            break

        num_ley += 1

        if len(scraper.raw_leyes) % 10 == 0:
            time.sleep(5)

        if len(scraper.raw_leyes) % 100 == 0:
            scraper.load_raw_leyes()


if __name__ == "__main__":
    main()