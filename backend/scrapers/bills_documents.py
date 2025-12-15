import json
import base64
import time
from loguru import logger
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


from backend.config import settings
from backend.scrapers.utils import render_pdf
from backend.database.raw_models import RawBillDocument, RawBill

BASE_URL = "https://wb2server.congreso.gob.pe/spley-portal-service/"
RAW_DB_PATH = settings.RAW_DB_URL
PRIORITIES = set(
    [
        "Publicada en el Diario Oficial El Peruano",
        "AUT\u00d3GRAFA",
        "APROBADO",
        "EN DEBATE - PLENO",
        "APROBADO 1ERA. VOTACI\u00d3N",
    ]
)


class RawBillDocumentScraper:
    """
    Class to scrape and store raw text extracted from bill's documents
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.Session = sessionmaker(bind=self.engine)

        self.documents = []

    def filter_steps(self, extracted_steps: list[dict], bill_id: str):
        """
        Filter steps that are already loaded in the DB
        """
        session = self.Session()
        n_steps_in_db = (
            session.query(RawBillDocument)
            .filter(RawBillDocument.bill_id == bill_id)
            .all()
        )
        seguimiento_ids = set([int(step.seguimiento_id) for step in n_steps_in_db])

        filtered_steps = [
            step
            for step in extracted_steps
            if step["seguimientoPleyId"] not in seguimiento_ids
        ]

        return filtered_steps

    def get_bill_documents(
        self, bill_id: str, update: bool = False, prioritize: bool = True
    ) -> list[RawBillDocument]:
        """
        Extract the urls from a RawBill's files and extract the text from each of them
        """
        session = self.Session()
        bill = (
            session.query(RawBill)
            .filter(RawBill.id == bill_id)
            .order_by(RawBill.timestamp.desc())
            .first()
        )

        assert bill is not None, f"Bill with id {bill_id} has not been scraped yet"

        steps: list[dict] = json.loads(bill.steps)

        if not update:
            steps = self.filter_steps(steps, bill_id)

        if prioritize:
            logger.info(f"Total number of steps: {len(steps)}")
            steps = [step for step in steps if step.get("desEstado") in PRIORITIES]

        if len(steps) == 0:
            logger.info(f"No steps found for bill {bill_id}")
            return None

        logger.info(f"Extracting files from {len(steps)} steps of bill {bill_id}")

        for ix, step in enumerate(steps):
            files = step.get("archivos")
            step_date = step.get("fecha")

            if not files:
                continue

            for file in files:
                file_id = file["proyectoArchivoId"]
                seguimiento_id = file["seguimientoPleyId"]

                b64_id = base64.b64encode(str(file_id).encode()).decode()
                url = f"{BASE_URL}/archivo/{b64_id}/pdf"
                logger.info(f"Extracting document {ix + 1}/{len(steps)} at url: {url}")
                extracted_text = render_pdf(url)
                logger.success(f"Successfully extracted text from {url}")

                new_doc = RawBillDocument(
                    timestamp=datetime.now(),
                    bill_id=bill_id,
                    step_date=datetime.strptime(step_date, "%Y-%m-%dT%H:%M:%S.%f%z"),
                    seguimiento_id=seguimiento_id,
                    archivo_id=file_id,
                    url=url,
                    text=extracted_text,
                    processed=False,
                    last_update=True,
                )
                self.documents.append(self.update_tracking(new_doc))

    def update_tracking(self, document: RawBillDocument) -> RawBillDocument:
        """Update the tracking columns of a RawBillDocument object"""

        with self.Session() as session:
            last_document = (
                session.query(RawBillDocument)
                .filter(RawBillDocument.id == document.id)
                .order_by(RawBillDocument.timestamp.desc())
                .first()
            )

            # First ever version of this document
            if last_document is None:
                document.changed = True
                document.last_update = True
            else:
                # Compare last vs new
                document.changed = document != last_document
                document.last_update = True

                # Update the old version AFTER comparison
                last_document.last_update = False
                session.add(last_document)
                session.commit()

            return document

    def add_documents_to_db(self) -> bool:
        """
        Add the documents to the database.
        Returns True on success, False on failure.
        """

        assert self.documents, "Documents must be scraped before it can be saved"

        session = self.Session()

        try:
            session.bulk_save_objects(self.documents)
            session.commit()
            logger.success(
                f"Added {len(self.documents)} documents to Raw Bill Documents table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(
                f"Failed to add documents from bill {self.documents[0].bill_id}: {e}"
            )
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()

    def load_raw_documents(self):
        if self.documents:
            self.add_documents_to_db()
            self.documents = []
        else:
            return None


if __name__ == "__main__":
    logger.info("Starting Scraper")
    scraper = RawBillDocumentScraper()

    bill = 865
    year = 2021

    while True:
        try:
            scraper.get_bill_documents(
                bill_id=f"{year}_{bill}", update=False, prioritize=True
            )
            scraper.load_raw_documents()
            bill += 1
        except TypeError as e:
            print(e)
            break
        except:
            time.sleep(10)
            continue

        time.sleep(5)
