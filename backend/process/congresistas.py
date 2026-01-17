from backend import normalize_membership_role
from backend.database.raw_models import RawCongresista
from backend.process.schema import Congresista, Membership

import json
from lxml.html import fromstring

def xpath2(xpath_query, parse):
    result = parse.xpath(xpath_query)
    return result[0].text if result else None

def process_profile_content(raw_cong: RawCongresista) -> Congresista:

    html = fromstring(raw_cong.profile_content)

    return Congresista(
        nombre=xpath2('//*[@class="nombres"]/span[2]', html),
        leg_period=raw_cong.leg_period,
        party_name=xpath2('//*[@class="grupo"]/span[2]', html),
        votes_in_election=int(xpath2('//*[@class="votacion"]/span[2]', html).replace(',','')),
        dist_electoral=xpath2('//*[@class="representa"]/span[2]', html),
        condicion=xpath2('//*[@class="condicion"]/span[2]', html),
        website=raw_cong.url,
        photo_url = 'https://www.congreso.gob.pe' + html.xpath('//*[@class="foto"]/img/@src')[0]
    )

def process_memberships(raw_cong: RawCongresista, cong: Congresista) -> list[Membership]:

    lst_membership = json.loads(raw_cong.memberships_content).get('data', None)

    final_lst = []

    for membership in lst_membership:

        period = membership.get('period')
        year = membership.get('anio')
        type_org = membership.get('desOrgano')
        org_name = membership.get('desOrganoCongresista')
        cargo = normalize_membership_role(membership.get('desCargo'))
        start_date = membership.get('fechaInicio')
        end_date = membership.get('fechaFin')

        if org_name == 'Subcomisión de Acusaciones Constitucionales':
            final_lst.append(Membership(
                role = cargo,
                nombre = cong.nombre,
                leg_period=cong.leg_period,
                org_name = org_name,
                org_type = "Comisión",
                comm_type = org_name,
                start_date = start_date,
                end_date = end_date
                ))
        elif type_org != '':
            final_lst.append(Membership(
                role = cargo,
                nombre = cong.nombre,
                leg_period=cong.leg_period,
                org_name = org_name,
                org_type = "Comisión",
                comm_type = type_org,
                start_date = start_date,
                end_date = end_date
                ))
        else:
            final_lst.append(Membership(
                role = cargo,
                nombre = cong.nombre,
                leg_period=cong.leg_period,
                org_name = org_name,
                org_type = org_name,
                comm_type = None,
                start_date = start_date,
                end_date = end_date
                ))

    return final_lst