import json
import time
from datetime import datetime
from loguru import logger

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawMotion
from backend.scrapers.scrape_utils import get_url_text

BASE_URL = "https://wb2server.congreso.gob.pe/smociones-portal-service"
RAW_DB_PATH = settings.RAW_DB_URL


class RawMotionScraper:
    """
    Class to scrape and store raw bill information
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.Session = sessionmaker(bind=self.engine)

        # Mapping raw section name to RawMotion attribute name
        self.section_mapping = {
            "firmantes": "congresistas",
            "seguimientos": "steps",
        }

        # List of raw bills objects
        self.raw_motions = []

    def scrape_motion(self, year: str, motion_number: str) -> None:
        """
        Scrape key sections: general, congresistas, steps

        Returns tuple with result of scrape, error message if relevant
        """

        motion_url = f"{BASE_URL}/mocion/{year}/{motion_number}"
        response = get_url_text(motion_url)

        try:
            resp = json.loads(response)

            # Successfully built the raw bill!
            self.raw_motions.append(self.create_raw_motion(year, motion_number, resp["data"]))
            logger.success(f"Successfully scraped Raw Motion {year}_{motion_number}")

        except TypeError as e:
            raise e

    def create_raw_motion(self, year: str, motion_number: str, data: dict) -> RawMotion:
        # Initialize raw bill with id and timestamp
        raw_motion = RawMotion(id=f"{year}_{motion_number}", timestamp=datetime.now())

        # Add sections
        for raw_name, attribute_name in self.section_mapping.items():
            # Grab expected section, use English value to signal no section
            # (since sections can be empty lists themselves)
            attribute_value = data.pop(raw_name, "Not Found")
            if attribute_value == "Not Found":
                logger.warning(
                    f"{raw_motion.id} - Missing Attribute: {raw_name} ({attribute_name})"
                )
            else:
                setattr(raw_motion, attribute_name, json.dumps(attribute_value))
        
        raw_motion.general = json.dumps(data)

        return raw_motion

    def add_motions_to_db(self) -> bool:
        """
        Add a single motion to the database.
        Returns True on success, False on failure.
        """
        assert len(self.raw_motions) != 0, (
            "There are no Raw Motions scraped. Nothing to load to DB."
        )

        # Create a new session
        session = self.Session()
        try:
            # Add and commit raw motion
            session.bulk_save_objects(self.raw_motions)
            session.commit()
            logger.success(f"Added {len(self.raw_motions)} Raw Motions to table.")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to add motions to Raw Motions table: {e}")
            session.rollback()
            return False

        finally:
            # Close Session
            session.close()

    def load_raw_motions(self):
        self.add_motions_to_db()
        self.raw_motions = []


if __name__ == "__main__":
    scraper = RawMotionScraper()
    years = ["2021"]

    motion = 1
    year = 2021
    while True:
        try:
            scraper.scrape_motion(str(year), str(motion))
            motion += 1
        except TypeError:
            break


        if len(scraper.raw_motions) % 10 == 0:
            time.sleep(5)

        if len(scraper.raw_motions) % 10 == 0:
            scraper.load_raw_motions()
