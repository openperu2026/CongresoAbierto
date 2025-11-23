import json
import base64
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from loguru import logger

from .scrape_utils import render_pdf
from estecon.backend.database.raw_models import RawBillDocuments, RawBill
from ..config import settings
BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal-service/" 
RAW_DB_PATH = settings.RAW_DB_URL

class RawBillDocumentScraper:
    '''
    Class to scrape and store raw text extracted from bill's documents
    '''
    def __init__(self):
        
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.Session = sessionmaker(bind=self.engine)

    def filter_steps(self, extracted_steps: list[dict], bill_id: str):
        """
        Filter steps that are already loaded in the DB
        """
        session = self.Session()
        n_steps_in_db = session.query(RawBillDocuments).filter(RawBillDocuments.bill_id == bill_id).all()
        seguimiento_ids = set([int(step.seguimiento_id) for step in n_steps_in_db])

        filtered_steps = [step for step in extracted_steps if step['seguimientoPleyId'] not in seguimiento_ids]
        
        return filtered_steps


    def get_bill_urls(self, bill_id: str, update: bool = False) -> list[RawBillDocuments]:
        """
        Extract the urls from a RawBill's files and extract the text from each of them
        """
        session = self.Session()
        bill = session.query(RawBill).filter(RawBill.id == bill_id).first()

        assert bill is not None, f"Bill with id {bill_id} has not been scraped yet"

        steps: list[dict] = json.loads(bill.steps)

        if not update:
            steps = self.filter_steps(steps, bill_id)

        urls = []
        logger.info(f"Extracting files from {len(steps)} steps of bill {bill_id}")
        for ix, step in enumerate(steps):
            files = step.get("archivos")
            step_date = step.get("fecha")

            for file in files:
                file_id = file["proyectoArchivoId"]
                seguimiento_id = file['seguimientoPleyId']
                b64_id = base64.b64encode(str(file_id).encode()).decode()
                url = (f"{BASE_URL}/archivo/{b64_id}/pdf")

                logger.info(f"Extracting document {ix}/{len(steps)} at url: {url}")
                extracted_text = render_pdf(url)
                logger.success(f"Successfully extracted text from {url}")

                urls.append(RawBillDocuments(
                    timestamp = datetime.now(),
                    bill_id = bill_id,
                    step_date = datetime.strptime(step_date, "%Y-%m-%dT%H:%M:%S.%f%z"),
                    seguimiento_id = seguimiento_id,
                    archivo_id = file_id,
                    url = url,
                    text = extracted_text
                ))
        
        self.urls = urls
    
    def add_documents_to_db(self) -> bool:
        """
        Add the documents to the database.
        Returns True on success, False on failure.
        """

        assert self.urls, "Documents must be scraped before it can be saved"

        session = self.Session()

        try:
            session.bulk_save_objects(self.urls)
            session.commit()
            logger.success(f'Added {len(self.urls)} documents to Raw Bill Documents table')
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add documents from bill {self.urls[0].bill_id}: {e}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()

if __name__ == "__main__":
    logger.info("Starting Scraper")
    scraper = RawBillDocumentScraper()
    scraper.get_bill_urls(bill_id = "2021_103")
    scraper.add_documents_to_db()