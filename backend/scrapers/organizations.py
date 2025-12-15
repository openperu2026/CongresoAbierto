import os
from loguru import logger
from typing import Literal
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database.raw_models import RawOrganization
from backend.scrapers.utils import parse_url


BASE_URLS = {
    "Junta de Portavoces": "https://www.congreso.gob.pe/integrantesjuntadeportavoces",
    "Consejo Directivo": "https://www.congreso.gob.pe/integrantesconsejodirectivo/",
    "Mesa Directiva": "https://www.congreso.gob.pe/integrantesmesadirectiva",
    "Comisión Permanente": "https://www.congreso.gob.pe/integrantescomisionespermanentes",
}

RAW_DB_PATH = settings.RAW_DB_URL


class RawOrganizationScraper:
    """
    Class to scrape Grupos Parlamentarios' raw data from the congress web page
    """

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.urls = BASE_URLS
        self.Session = sessionmaker(bind=self.engine)

    def get_options(
        self,
        url: str,
        select_name: Literal["idRegistroPadre"] = "idRegistroPadre",
    ) -> dict[str, str]:
        """
        Functions that fetchs all the possible options that are in the dropdown list in the html file

        Args:
            - url (str): link to the html
            - select_name (str): the name of the dropdown element
        """
        parse = parse_url(url)
        options = parse.xpath(f'//*[@name="{select_name}"]/option')
        return {
            elem.text: elem.get("value") for elem in options if elem.text is not None
        }

    def get_html_with_selections(self, url: str, period_value: str) -> str | None:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        service = Service(log_path=os.devnull)

        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)

        try:
            select_year = Select(driver.find_element(By.NAME, "idRegistroPadre"))
            select_year.select_by_value(period_value)

            html = driver.page_source
            driver.quit()
            return html
        except NoSuchElementException as e:
            logger.error(f"Error found: {e}")
            driver.quit()
            return None

    def get_raw_organizations(self, only_current: bool = True) -> None:
        final_lst = []
        for type_org, url in self.urls.items():
            dict_periods = self.get_options(url=url, select_name="idRegistroPadre")

            if only_current:
                # Only scrape current period
                key, val = list(dict_periods.items())[0]
                dict_periods = {key: val}

            for year, value in dict_periods.items():
                logger.info(
                    f"Scraping organization for year {year} and type {type_org}"
                )

                html = self.get_html_with_selections(url, value)

                if html is not None:
                    new_org = RawOrganization(
                        timestamp=datetime.now(),
                        legislative_year=year,
                        type_org=type_org,
                        raw_html=html,
                        processed=False,
                        last_update=True,
                    )

                    final_lst.append(self.update_tracking(new_org))

        self.organizations_list = final_lst
        logger.success(
            f"Successfully extracted {len(self.organizations_list)} raw html organization"
        )

    def update_tracking(self, org: RawOrganization) -> RawOrganization:
        """Update the tracking columns of a RawOrganization object"""

        with self.Session() as session:
            last_org = (
                session.query(RawOrganization)
                .filter(RawOrganization.id == org.id)
                .order_by(RawOrganization.timestamp.desc())
                .first()
            )

            # First ever version of this org
            if last_org is None:
                org.changed = True
                org.last_update = True
            else:
                # Compare last vs new
                org.changed = org != last_org
                org.last_update = True

                # Update the old version AFTER comparison
                last_org.last_update = False
                session.add(last_org)
                session.commit()

            return org

    def add_organizations_to_db(self) -> bool:
        """
        Add the organizations to the database.
        Returns True on success, False on failure.
        """
        assert self.organizations_list, (
            "Organizations must be scraped before it can be saved"
        )

        session = self.Session()

        try:
            session.bulk_save_objects(self.organizations_list)
            session.commit()
            logger.success(
                f"Added {len(self.organizations_list)} organizations to Raw Organizations table"
            )
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add organizations: {e}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()


if __name__ == "__main__":
    scraper = RawOrganizationScraper()
    scraper.get_raw_organizations()
    scraper.add_organizations_to_db()
