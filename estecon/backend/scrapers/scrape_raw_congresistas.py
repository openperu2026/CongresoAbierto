import re
from lxml.html import HtmlElement, fromstring
from loguru import logger
from ..config import settings
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from ..database.raw_models import RawCongresista
from estecon.backend.scrapers.scrape_utils import parse_url, get_url_text

BASE_URL = "https://www.congreso.gob.pe/pleno/congresistas/"
API_MEMBERSHIP = "https://wb2server.congreso.gob.pe/vll/cargos/api/"
RAW_DB_PATH = settings.RAW_DB_URL

class RawCongresistasScraper:
    '''
    Class to scrape congresistas raw data from the congress web page
    '''

    def __init__(self):
        # Engine and session maker for DB
        self.engine = create_engine(RAW_DB_PATH)
        self.url = BASE_URL
        self.Session = sessionmaker(bind=self.engine)
    
    def get_dict_periodos(self):
        parse = parse_url(self.url)
        periodos = parse.xpath('//*[@name="idRegistroPadre"]/option')
        self.periods = {elem.text: elem.get('value') for elem in periodos}

    def extract_table(self, period) -> HtmlElement:
        parse = parse_url(self.url, {'idRegistroPadre': period})
        table = parse.xpath('//*[@class="congresistas"]')
        return table[0]
    
    def get_urls_from_table(self, period) -> List[str]:
        html = self.extract_table(period)
        cong_links = html.xpath('//*[@class="congresistas"]//tr//td//*[@class="conginfo"]/@href')
        return cong_links

    def get_profile_content(self, cong_link: str) -> str:
        full_url = self.url + cong_link
        return get_url_text(full_url)
    
    def get_cong_website(self, profile_content: str) -> Optional[str]:
        parse = fromstring(profile_content)
        website = parse.xpath('//*[@class="web"]/span[2]/a/@href')
        return website[0] if website else None

    def create_raw_congresista(self, period: str, cong_link: str) -> Optional[RawCongresista]:
        
        profile_content = self.get_profile_content(cong_link)
        website = self.get_cong_website(profile_content)

        if period in ['Parlamentario 2001 - 2006', 'Parlamentario 2000 - 2001', 'Parlamentario 1995 - 2000', 'CCD 1992 -1995']:
            return RawCongresista(
                timestamp = datetime.now(),
                leg_period = period,
                url = website,
                profile_content = profile_content,
                memberships_content = None
            )
        elif period == "Parlamentario 2021 - 2026":
            cargos = parse_url(website + "sobrecongresista/cargos/")
        elif period == "Parlamentario 2016 - 2021":
            cargos = parse_url(website + "Cargoscongresista/")
        elif period == "Parlamentario 2011 - 2016":
            cargos = parse_url(website + "sobre_congresista/cargos/")
        elif period == "Parlamentario 2006 - 2011":
            cargos = parse_url(website + "CargosCongresista/")
            # also sobrecongresista/cargos/
            # sobreCongresista/Cargos/
            # Cargos/
            # cargos/
        
        try:
            iframe = cargos.xpath('//*[@id="objContents"]/div[2]/p/iframe')
            if not iframe:
                raise IndexError("No iframe found in cargos page")
            api_call = iframe[0].get('src')
            match = re.search(r"(listar/)(.*)", api_call)
            if not match:
                raise ValueError(f"Invalid iframe src pattern: {api_call}")
            api_id = match.group(2)
        except (IndexError, ValueError, AttributeError) as e:
            logger.warning(f"Failed to extract API ID for {cong_link}: {e}")
            logger.warning(f"Congresista partially extracted from {website}")
            return RawCongresista(
                timestamp = datetime.now(),
                leg_period = period,
                url = website,
                profile_content = profile_content,
                memberships_content = None
            )
        
        memberships_content = get_url_text(API_MEMBERSHIP + api_id) 

        raw_congresista = RawCongresista(
            timestamp = datetime.now(),
            leg_period = period,
            url = website,
            profile_content = profile_content,
            memberships_content = memberships_content
        )
        logger.info(f"Congresista successfully extracted from {website}")
        return raw_congresista

    def extract_all(self) -> List[RawCongresista]:
        assert self.periods, "You need to extract all the available periods before extracting the tables"
        
        self.raw_congresistas = []

        for period, value in self.periods.items():
            links = self.get_urls_from_table(value)
            for cong_link in links:
                self.raw_congresistas.append(self.create_raw_congresista(period, cong_link))

        return self.raw_congresistas

    def add_congresistas_to_db(self) -> bool:
        """
        Add the raw congresistas to the database.
        Returns True on success, False on failure
        """

        assert self.raw_congresistas, "Congresistas must be scraped before it can be saved"

        session = self.Session()

        try:
            session.bulk_save_objects(self.raw_congresistas)
            session.commit()
            logger.success(f"Added {len(self.raw_congresistas)} congresistas to Raw Congresistas table")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to add committees: {str(e)}")
            session.rollback()
            return False
        finally:
            # Close Session
            session.close()

if __name__ == "__main__":
    scraper = RawCongresistasScraper()
    scraper.get_dict_periodos()
    scraper.extract_all()
    scraper.add_congresistas_to_db()
    