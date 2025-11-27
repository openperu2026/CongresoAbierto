import json
import base64
import time
from loguru import logger
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


from backend.config import settings
from backend.scrapers.scrape_utils import render_pdf
from backend.database.raw_models import RawMotionDocument, RawMotion

BASE_URL = "https://wb2server.congreso.gob.pe/smociones-portal-service"
RAW_DB_PATH = settings.RAW_DB_URL
PRIORITIES = set(["Aprobada", "Aprobada la Moción", "Aprobado Proyecto de Resolución", "Publicado Diario Oficial El Peruano", "Rechazada"])

class RawMotionDocumentScraper:
    """
    Class to scrape and store raw text extracted from motion's documents
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.Session = sessionmaker(bind=self.engine)

        self.urls = []

    def filter_steps(self, extracted_steps: list[dict], motion_id: str):
        """
        Filter steps that are already loaded in the DB
        """
        session = self.Session()
        n_steps_in_db = (
            session.query(RawMotionDocument)
            .filter(RawMotionDocument.motion_id == motion_id)
            .all()
        )
        seguimiento_ids = set([int(step.seguimiento_id) for step in n_steps_in_db])

        filtered_steps = [
            step
            for step in extracted_steps
            if step["seguimientoPleyId"] not in seguimiento_ids
        ]

        return filtered_steps

    def get_motion_urls(
        self, motion_id: str, update: bool = False, prioritize: bool = True
    ) -> list[RawMotionDocument]:
        """
        Extract the urls from a RawMotion's files and extract the text from each of them
        """
        session = self.Session()
        motion = (
            session.query(RawMotion)
            .filter(RawMotion.id == motion_id)
            .order_by(RawMotion.timestamp.desc())
            .first()
        )

        assert motion is not None, f"Motion with id {motion_id} has not been scraped yet"

        steps: list[dict] = json.loads(motion.steps)

        if not update:
            steps = self.filter_steps(steps, motion_id)

        if prioritize:
            steps = [step for step in steps if step.get("desEstadoMocion") in PRIORITIES]

        if len(steps) == 0:
            logger.info(f"No steps found for motion {motion_id}")
            return None
        
        logger.info(f"Extracting files from {len(steps)} steps of motion {motion_id}")

        for ix, step in enumerate(steps):
            files = step.get("adjuntos")
            step_date = step.get("fecSeguimiento")

            if not files:
                continue

            for file in files:
                file_id = file["seguimientoAdjuntoId"]
                seguimiento_id = file["seguimientoId"]
                b64_id = base64.b64encode(str(file_id).encode()).decode()
                url = f"{BASE_URL}/seguimiento-adjunto/{b64_id}/pdf"

                logger.info(f"Extracting document {ix + 1}/{len(steps)} at url: {url}")
                extracted_text = render_pdf(url)
                logger.success(f"Successfully extracted text from {url}")

                self.urls.append(
                    RawMotionDocument(
                        timestamp=datetime.now(),
                        motion_id=motion_id,
                        step_date=datetime.strptime(
                            step_date, "%Y-%m-%dT%H:%M:%S.%f%z"
                        ),
                        seguimiento_id=seguimiento_id,
                        archivo_id=file_id,
                        url=url,
                        text=extracted_text,
                    )
                )

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
            logger.success(
                f"Added {len(self.urls)} documents to Raw Motion Documents table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(
                
                f"Failed to add documents from motion {self.urls[0].motion_id}: {e}"
            )
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()

    def load_raw_documents(self):
        self.add_documents_to_db()
        self.urls = []

if __name__ == "__main__":
    logger.info("Starting Scraper")
    scraper = RawMotionDocumentScraper()

    motion = 209
    year = 2021

    while True:
        try:
            scraper.get_motion_urls(motion_id=f"{year}_{motion}")
            motion += 1
        except TypeError as e:
            print(e)
            break
        except:
            time.sleep(10)
            continue

        try:
            scraper.load_raw_documents()
        except AssertionError:
            logger.warning(f"No steps neither documents found for motion {year}_{motion-1}")

        time.sleep(5)
