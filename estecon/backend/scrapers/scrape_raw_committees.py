import os
import httpx
from loguru import logger
from lxml.html import fromstring, HtmlElement
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from itertools import product
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from estecon.backend.database.models import RawCommittee
from typing import Dict, Optional, List, Literal
from .scrape_utils import parse_url
from ..config import settings

BASE_URL = "https://www.congreso.gob.pe/CuadrodeComisiones" 
DB_PATH = settings.DB_URL


class RawCommitteeScraper:
    '''
    Class to scrape committee raw data from the congress web page
    '''
    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(DB_PATH)
        self.url = BASE_URL
        self.Session = sessionmaker(bind=self.engine)

    def get_options(self, 
                    url: str, 
                    select_name: Literal['idRegistroPadre', 'fld_78_Comision'] = 'idRegistroPadre') -> Dict[str,str]:
        """
        Functions that fetchs all the possible options that are in the dropdown list in the html file

        Args:
            - url (str): link to the html
            - select_name (str): the name of the dropdown element
        """
        parse = parse_url(url)
        years = parse.xpath(f'//*[@name="{select_name}"]/option')
        return {elem.text : elem.get('value') for elem in years if elem.text is not None}
    
    def get_html_with_selections(self, url: str, year_value: str, committee_value: str) -> Optional[HtmlElement]:
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        service = Service(log_path=os.devnull)

        driver = webdriver.Chrome(service = service, options = options)
        driver.get(url)

        try:
            select_year = Select(driver.find_element(By.NAME, "idRegistroPadre"))
            select_year.select_by_value(year_value)

            select_committee = Select(driver.find_element(By.NAME, "fld_78_Comision"))
            select_committee.select_by_value(committee_value)    

            html = driver.page_source
            driver.quit()
            return html
        except NoSuchElementException as e:
            logger.error(f"Error found: {e}")
            driver.quit()
            return None
    
    def get_raw_committees(self) -> HtmlElement:

        dict_years = self.get_options(url = self.url, select_name = 'idRegistroPadre')
        dict_types = self.get_options(url = self.url, select_name = 'fld_78_Comision')   

        final_lst = []
        for year_key, type_key in product(dict_years.keys(), dict_types.keys()):
            
            logger.info(f"Scraping committee for year {year_key} and committee_type {type_key}")

            year = dict_years.get(year_key)
            types = dict_types.get(type_key)

            html = self.get_html_with_selections(self.url, year, types)

            if html is not None:
                final_lst.append(RawCommittee(
                    timestamp = datetime.now(),
                    legislative_year = int(year_key),
                    committee_type = type_key,
                    raw_html = html
                ))

        self.committee_list = final_lst 
        logger.success(f"Successfully extracted {len(self.committee_list)} raw html committees")
    
    def add_committees_to_db(self) -> bool:
        """
        Add the committees to the database.
        Returns True on success, False on failure.
        """
        assert self.committee_list, "Committees must be scraped before it can be saved"

        session = self.Session()

        try:
            session.bulk_save_objects(self.committee_list)
            session.commit()
            logger.success(f'Added {len(self.committee_list)} documents to Raw Bill Documents table')
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add committees: {e}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()

if __name__ == "__main__":
    scraper = RawCommitteeScraper()
    scraper.get_raw_committees()
    scraper.add_committees_to_db()

