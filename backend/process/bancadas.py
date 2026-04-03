from lxml.html import fromstring

from backend import LegislativeYear, find_leg_period
from backend.database.raw_models import RawBancada
from backend.process.schema import Bancada, BancadaMembership

from backend.process.utils import get_current_leg_year
from backend.scrapers.utils import get_url_text, get_cong_website


def process_bancada(
    raw_bancada: RawBancada,
) -> tuple[list[Bancada], list[BancadaMembership]]:
    """
    Process a RawBancada instance into a Bancada instance and a list of BancadaMemberships
    that maps all the congresistas who belongs to the Bancada at a specific legislative year

    Args:
        raw_bancada (RawBancada): RawBancada instance that contains all the bancadas and membership for a specific period

    Returns:
        tuple[Bancada, list[BancadaMembership]]: Bancada instance and the list of BancadaMemberships
    """

    html = fromstring(raw_bancada.raw_html)

    rows = html.xpath('//*[@class="table-cng"]/tbody/tr')

    membership_list = []
    bancadas_lst = []
    for row in rows:
        childs = row.getchildren()
        if len(childs) == 1:
            # Bancada
            bancada = childs[0].xpath(".//h2")[0].text_content().title()
            leg_year = get_current_leg_year(str(raw_bancada.timestamp))
            current_leg_period = find_leg_period(leg_year)

            if raw_bancada.legislative_period != current_leg_period:
                # On past periods -> Use the last year from LegPeriod
                leg_year = LegislativeYear(
                    str(int(raw_bancada.legislative_period[-4:]) - 1)
                )

            bancadas_lst.append(Bancada(leg_year=leg_year, bancada_name=bancada))

        else:
            # Congresista
            name = row.xpath('.//*[@class="conginfo"]')[0].text
            web_profile = row.xpath('.//*[@class="conginfo"]/@href')[0]
            
            query = web_profile.split('?', 1)[1]
            parsed_website = get_url_text("https://www3.congreso.gob.pe/pagina/?" + query)
            website = get_cong_website(parsed_website)

            membership_list.append(
                BancadaMembership(
                    leg_year=leg_year,
                    cong_name=name,
                    website=website,
                    bancada_name=bancada,
                )
            )

    return bancadas_lst, membership_list
