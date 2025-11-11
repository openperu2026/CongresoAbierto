import re
import asyncio
import httpx
from lxml.html import HtmlElement, fromstring
from urllib.parse import urljoin
from loguru import logger
from ..config import settings
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from ..database.raw_models import RawCongresista
from estecon.backend.scrapers.scrape_utils import (
    parse_url,
    get_url_text,
    normalize_text,
    get_url_text_async,
    with_retry
)

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
        
        self.periods = {}
        self.raw_congresistas: List[RawCongresista] = []        
    
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
    
    def _is_cargos_label(self, txt: str) -> bool:
        """
        Helper function to assert if the labels inside the webpage is related to cargos.
        We care about labels like: 'Cargos', 'Cargos del congresista', 'Cargos de la congresista', etc.
        """
        if "cargo" not in txt:
            return False
        # soft preference for congresista/parlamentario but we don't force it
        return True
    
    def _score_link_text(self, txt: str) -> int:
        """
        Higher score means that is more like what we want from the cargos url.
        """
        score = 0
        if "cargo" in txt:
            score += 2
        if "congres" in txt or "parlament" in txt:
            score += 2
        if "cargos del" in txt or "cargos de la" in txt:
            score += 1
        return score
    
    def get_best_cargos_link(self, doc: HtmlElement, base_url: str) -> Optional[str]:
        """
        Method
        """
        # collect all <a> and <button> (just in case)
        candidates = doc.xpath("//a | //button")

        best_href = None
        best_score = -1

        for node in candidates:
            raw_text = node.text_content()
            txt = normalize_text(raw_text)

            if not self._is_cargos_label(txt):
                continue

            # try common URL carriers
            href = node.get("href") or node.get("data-href") or node.get("onclick")
            if not href:
                continue

            s = self._score_link_text(txt)
            if s > best_score:
                best_score = s
                best_href = href

        if best_href:
            return urljoin(base_url, best_href)

        # fallback: None found
        return None

    @with_retry()
    async def create_raw_congresista_async(
        self,
        client: httpx.AsyncClient,
        period: str,
        cong_link: str,
    ) -> Optional[RawCongresista]:
        """
        Async version of create_raw_congresista.
        The logic is the same, but all network I/O is awaited.
        """
        # 1. profile page (relative link from the table -> build full URL)
        full_profile_url = self.url + cong_link
        profile_content = await get_url_text_async(client, full_profile_url)
        if not profile_content:
            logger.warning(f"Failed to fetch profile for {cong_link}")
            return None

        website = self.get_cong_website(profile_content)

        # Old periods (pre 2006) don't have cargos iframe
        legacy_periods = [
            "Parlamentario 2001 - 2006",
            "Parlamentario 2000 - 2001",
            "Parlamentario 1995 - 2000",
            "CCD 1992 -1995",
        ]
        if period in legacy_periods or not website:
            return RawCongresista(
                timestamp=datetime.now(),
                leg_period=period,
                url=website,
                profile_content=profile_content,
                memberships_content=None,
            )

        # 2. congresista's personal page
        try: 
            website_html_text = await get_url_text_async(client, website)
        except (httpx.HTTPError, TypeError) as e:
            logger.warning(f"Failed to fetch personal site {website}: {e}")
            return RawCongresista(
                timestamp=datetime.now(),
                leg_period=period,
                url=website,
                profile_content=profile_content,
                memberships_content=None,
            )

        website_doc = fromstring(website_html_text)
        cargos_url = self.get_best_cargos_link(website_doc, website)

        if not cargos_url:
            logger.warning(f"No cargos link for {website}")
            return RawCongresista(
                timestamp=datetime.now(),
                leg_period=period,
                url=website,
                profile_content=profile_content,
                memberships_content=None,
            )

        # 3. cargos page
        cargos_html_text = await get_url_text_async(client, cargos_url)
        if not cargos_html_text:
            logger.warning(f"Failed to fetch cargos page {cargos_url}")
            return RawCongresista(
                timestamp=datetime.now(),
                leg_period=period,
                url=website,
                profile_content=profile_content,
                memberships_content=None,
            )

        cargos_doc = fromstring(cargos_html_text)

        try:
            iframe = cargos_doc.xpath('//*[@id="objContents"]/div[2]/p/iframe')
            if not iframe:
                raise IndexError("No iframe found in cargos page")
            api_call = iframe[0].get("src")
            match = re.search(r"(listar/)(.*)", api_call)
            if not match:
                raise ValueError(f"Invalid iframe src pattern: {api_call}")
            api_id = match.group(2)
        except (IndexError, ValueError, AttributeError) as e:
            logger.warning(f"Failed to extract API ID for {cong_link}: {e}")
            logger.warning(f"Congresista partially extracted from {website}")
            return RawCongresista(
                timestamp=datetime.now(),
                leg_period=period,
                url=website,
                profile_content=profile_content,
                memberships_content=None,
            )

        # 4. cargos API
        memberships_content = await get_url_text_async(
            client,
            API_MEMBERSHIP + api_id,
        )

        return RawCongresista(
            timestamp=datetime.now(),
            leg_period=period,
            url=website,
            profile_content=profile_content,
            memberships_content=memberships_content,
        )

    @with_retry()
    async def extract_cong_from_period_async(
        self,
        period_key: str,
        period_value: str,
        concurrency_limit: int = 10,
    ) -> List[RawCongresista]:
        """
        Concurrently scrape all congresistas for a given period.
        We cap concurrency_limit so we don't nuke the Congreso server.
        """
        links = self.get_urls_from_table(period_value)

        sem = asyncio.Semaphore(concurrency_limit)

        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            async def _task_wrapper(link: str):
                async with sem:
                    await asyncio.sleep(0.5)
                    try:
                        return await self.create_raw_congresista_async(
                            client, period_key, link
                        )
                    except Exception as e:
                        logger.error(f"Exception on {link}: {e}")
                        return None

            tasks = [asyncio.create_task(_task_wrapper(link)) for link in links]
            results = await asyncio.gather(*tasks)

        # filter None (failed ones)
        return [r for r in results if r is not None]

    async def extract_and_load_all_async(self) -> List[RawCongresista]:
        assert (
            self.periods
        ), "You need to extract all the available periods before extracting the tables"

        all_raw: List[RawCongresista] = []

        # scrape each period (still sequential by period, but parallel *within* period)
        for period, value in self.periods.items():
            period_raw = await self.extract_cong_from_period_async(period, value)
            logger.info(f"{period}: scraped {len(period_raw)} congresistas")
            all_raw.extend(period_raw)

        self.raw_congresistas = all_raw

        # write once at the end
        self.add_congresistas_to_db()

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

async def main():
    scraper = RawCongresistasScraper()
    scraper.get_dict_periodos()
    await scraper.extract_and_load_all_async()

if __name__ == "__main__":
    asyncio.run(main())