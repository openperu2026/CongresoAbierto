from backend.database.raw_models import RawCongresista
from backend.database.models import Congresista, Membership 

import json
from lxml.html import fromstring

def xpath2(xpath_query, parse):
    result = parse.xpath(xpath_query)
    return result[0].text if result else None

def process_profile_content(raw_cong: RawCongresista) -> Congresista:

    html = fromstring(raw_cong.profile_content)

    return Congresista(
        id=id,
        nombre=xpath2('//*[@class="nombres"]/span[2]', html),
        votation=xpath2('//*[@class="votacion"]/span[2]', html),
        leg_period=raw_cong.leg_period,
        party_name=xpath2('//*[@class="grupo"]/span[2]', html),
        bancada_name=xpath2('//*[@class="bancada"]/span[2]', html),
        dist_electoral=xpath2('//*[@class="representa"]/span[2]', html),
        condicion=xpath2('//*[@class="condicion"]/span[2]', html),
        website=raw_cong.url
    )

def process_memberships(raw_cong: RawCongresista) -> tuple[list[Membership], dict]:

    lst_membership = json.loads(raw_cong.memberships_content).get('data', None)

    for membership in lst_membership:

        period = membership.get('period')
        year = membership.get('anio')
        type_org = membership.get('desOrgano')
        name_org = membership.get('desOrganoCongresista')
        cargo = membership.get('desCargo')
        start_date = membership.get('fechaInicio')
        end_date = membership.get('fechaFin')