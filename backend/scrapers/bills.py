import json
import time
from datetime import datetime
from loguru import logger

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.scrapers.utils import get_url_text
from backend.database.raw_models import RawBill

BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal-service/"
RAW_DB_PATH = settings.RAW_DB_URL


class RawBillScraper:
    """
    Class to scrape and store raw bill information
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.Session = sessionmaker(bind=self.engine)

        # Mapping raw section name to RawBill attribute name
        self.section_mapping = {
            "general": "general",
            "firmantes": "congresistas",
            "comisiones": "committees",
            "seguimientos": "steps",
        }

        # List of raw bills objects
        self.raw_bills = []

    def scrape_bill(self, year: str, bill_number: str) -> None:
        """
        Scrape key sections: general, congresistas, committees, steps

        Returns tuple with result of scrape, error message if relevant
        """

        bill_url = f"{BASE_URL}/expediente/{year}/{bill_number}"
        response = get_url_text(bill_url)

        try:
            resp = json.loads(response)

            # Successfully built the raw bill!
            self.raw_bills.append(self.create_raw_bill(year, bill_number, resp["data"]))
            logger.success(f"Successfully scraped Raw Bill {year}_{bill_number}")

        except TypeError as e:
            raise e

    def create_raw_bill(self, year: str, bill_number: str, data: dict) -> RawBill:
        # Initialize raw bill with id and timestamp
        raw_bill = RawBill(id=f"{year}_{bill_number}", timestamp=datetime.now())

        # Add sections
        for raw_name, attribute_name in self.section_mapping.items():
            # Grab expected section, use English value to signal no section
            # (since sections can be empty lists themselves)
            attribute_value = data.get(raw_name, "Not Found")
            if attribute_value == "Not Found":
                logger.warning(
                    f"{raw_bill.id} - Missing Attribute: {raw_name} ({attribute_name})"
                )
            else:
                setattr(raw_bill, attribute_name, json.dumps(attribute_value))

        return raw_bill

    def add_bills_to_db(self) -> bool:
        """
        Add a single bill to the database.
        Returns True on success, False on failure.
        """
        assert len(self.raw_bills) != 0, (
            "There are no Raw Bills scraped. Nothing to load to DB."
        )

        # Create a new session
        session = self.Session()
        try:
            # Add and commit raw bill
            session.bulk_save_objects(self.raw_bills)
            session.commit()
            logger.success(f"Added {len(self.raw_bills)} Raw Bills to table.")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to add bills to Raw Bills table: {e}")
            session.rollback()
            return False

        finally:
            # Close Session
            session.close()

    def load_raw_bills(self):
        self.add_bills_to_db()
        self.raw_bills = []

def main():
    scraper = RawBillScraper()
    years = ["2021"]
    bills = [str(num) for num in range(1, 13330)]

    bill = 101
    year = 2021
    while True:
        try:
            scraper.scrape_bill(str(year), str(bill))
        except TypeError:
            break

        bill += 1

        if len(scraper.raw_bills) % 10 == 0:
            time.sleep(5)

        if len(scraper.raw_bills) % 100 == 0:
            scraper.load_raw_bills()

if __name__ == "__main__":
    main()