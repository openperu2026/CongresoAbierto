import re
import json
import base64

from backend.scrapers.bills import BASE_URL
from backend.database.raw_models import RawBill
from backend.process.schema import Bill, BillCommittees, BillCongresistas, BillStep

VOTE_PATTERN = re.compile(
    r"\bSI\s*\+{2,}.*?\bNO\s*-{2,}|\bNO\s*-{2,}.*?\bSI\s*\+{2,}",
    re.IGNORECASE | re.DOTALL,
)

def process_bill(raw_bill: RawBill) -> Bill:

    general = json.loads(raw_bill.general)
    firmantes = json.loads(raw_bill.congresistas)

    cong_list = []
    id = raw_bill.id
    leg_period = general.get('desPerParAbrev')
    legislature = general.get('desLegis')
    presentation_date = general.get('fecPresentacion')
    title = general.get('titulo')
    summary = general.get('sumilla')
    observations = general.get('observaciones')
    complete_text = None # TODO: Extract Bill Full Text
    status = general.get('desEstado')
    proponent = general.get('desProponente')

    if firmantes:
        
        author_info = firmantes[0]
        author_name = author_info.get('nombre')
        author_web = author_info.get('pagWeb')

        for cong in firmantes:
            cong_list.append(BillCongresistas(
                bill_id = id,
                nombre = cong.get('nombre'),
                leg_period = leg_period,
                role_type = cong.get('tipoFirmanteId')
            ))

    bill_approved = general.get('desEstado') == "Publicada en el Diario Oficial El Peruano"

    bill = Bill(
        id = id,
        leg_period = leg_period,
        legislature = legislature,
        presentation_date = presentation_date,
        title = title,
        summary = summary,
        observations = observations,
        complete_text = complete_text,
        status = status,
        proponent = proponent,
        author_name = author_name,
        author_web = author_web,
        bill_approved = bill_approved
    )

    return bill, cong_list

def process_bill_steps_and_comms(raw_bill: RawBill) -> list[BillStep] | None:
    
    steps = json.loads(raw_bill.steps)

    if steps: 
        final_steps = []

        vote_step_counter = 0 
        for step in steps:
            
            id = step.get("seguimientoPleyId")
            date = step.get("fecha")
            details = step.get("detalle")
            vote_step = "votación" in details.lower() or "votacion" in details.lower()
            vote_id = None

            # Loop through each file in the step
            files = step.get("archivos")
            if files:
                for file in files:
                    file_id = file["proyectoArchivoId"]
                    b64_id = base64.b64encode(str(file_id).encode()).decode()
                    url = f"{BASE_URL}/archivo/{b64_id}/pdf"

                    # If vote file within vote step, record as such
                    if vote_step:
                        vote_step_counter += 1
                        vote_id = f"{raw_bill.id}_{vote_step_counter}"


            final_steps.append(BillStep(
                id = id,
                bill_id = raw_bill.id,
                vote_step = vote_step,
                vote_id = vote_id,
                step_date = date,
                step_detail = details,
                step_url = url,
            ))

        return final_steps

    else:
        return None

def get_committees(raw_bill: RawBill) -> list[BillCommittees] | None:

    data = json.loads(raw_bill.committees)
    
    if data: 
        committees = []

        for committee in data:
            committees.append(
                BillCommittees(
                    bill_id = raw_bill.id,
                    committee_name = committee.get('nombre')
                )
            )
        return committees
    else:
        return None
