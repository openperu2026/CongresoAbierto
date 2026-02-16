from lxml.html import fromstring

from backend.database.raw_models import RawLey
from backend.process.schema import Ley


def process_leyes(raw_ley: RawLey) -> Ley | None:

    html = fromstring(raw_ley.data)

    ley, _, recursos = html.xpath('./data/*')

    try:
        num_ley = ley.xpath('./numley')[0].text_content()
        title = ley.xpath('./tituloley')[0].text_content()
        
        for recurso in recursos.getchildren():
            if recurso.xpath('tiporecursoleyitemmenu')[0].text == '6':
                bill_id = recurso.xpath('enlace')[0].text
                break

        return Ley(
            id = num_ley,
            title = title,
            bill_id = bill_id,
        )
    except AttributeError:
        return None