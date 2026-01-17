import re
import json
import base64

from backend.scrapers.motions import BASE_URL
from backend.database.raw_models import RawMotion
from backend.process.schema import Motion, MotionCongresistas, MotionStep

VOTE_PATTERN = re.compile(
    r"\bSI\s*\+{2,}.*?\bNO\s*-{2,}|\bNO\s*-{2,}.*?\bSI\s*\+{2,}",
    re.IGNORECASE | re.DOTALL,
)

def process_bill(raw_motion: RawMotion) -> tuple[Motion, list[MotionCongresistas]]:
    """
    Process a RawMotion instance into a Motion instance and a list of MotionCongresistas 
    that maps all the congresistas that have a role in the Motion process

    Args:
        raw_motion (RawMotion): RawMotion instance that contains the scraped information from a bill

    Returns:
        Motion: instance that contains general information of the bill
        list[MotionCongresistas]: list of instances that relates congresistas to a Motion
    """
    # Obtaining dictionaries from the raw_motion columns 
    general = json.loads(raw_motion.general)
    firmantes = json.loads(raw_motion.congresistas)

    # Extracting information from general dictionary
    id = raw_motion.id
    leg_period = general.get('desPerParAbrev')
    legislature = general.get('desLegis')
    presentation_date = general.get('fecPresentacion')
    motion_type = general.get('desTipoMocion')
    summary = general.get('sumilla')
    observations = general.get('observacion')
    complete_text = None # TODO: Extract Motion Full Text
    status = general.get('desEstadoMocion')
    motion_approved = general.get('desEstadoMocion') == "Publicado Diario Oficial  El Peruano"

    # Extracting information from firmantes dictionary
    cong_list = []
    if firmantes:
        
        author_info = firmantes[0]
        author_name = author_info.get('nombre')
        author_web = author_info.get('pagWeb')

        for cong in firmantes:
            cong_list.append(MotionCongresistas(
                motion_id = id,
                nombre = cong.get('nombre'),
                leg_period = leg_period,
                role_type = cong.get('tipoFirmanteId')
            ))

    # Creating Motion instance
    motion = Motion(
        id = id,
        leg_period = leg_period,
        legislature = legislature,
        presentation_date = presentation_date,
        motion_type = motion_type,
        summary = summary,
        observations = observations,
        complete_text = complete_text,
        status = status,
        author_name = author_name,
        author_web = author_web,
        motion_approved = motion_approved
    )

    return motion, cong_list

def process_motion_steps_and_comms(raw_motion: RawMotion) -> list[MotionStep] | None:
    """
    Process a RawMotion instance into a list of MotionStep 
    that maps all the steps that have happended during the bill processess

    Args:
        raw_motion (RawMotion): RawMotion instance that contains the scraped information from a bill

    Returns:
        list[MotionStep]: list of instances that contains all the steps related to a Motion
    """
    # Obtaining dictionaries from the raw_motion columns 
    steps = json.loads(raw_motion.steps)

    if steps: 
        final_steps = []
        vote_step_counter = 0 
        
        for step in steps:
            
            # Extracting information from each step
            id = step.get("seguimientoId")
            date = step.get("fecSeguimiento")
            details = step.get("detalle")
            files = step.get("adjuntos")
            vote_step = "votación" in details.lower() or "votacion" in details.lower()
            vote_id = None
            # TODO: Think how to assess if it's a proper pdf with votes/attendance.

            if files:
                for file in files:
                    file_id = file["seguimientoAdjuntoId"]
                    b64_id = base64.b64encode(str(file_id).encode()).decode()
                    url = f"{BASE_URL}/seguimiento-adjunto/{b64_id}/pdf"

                    #TODO: Mejorar el codigo para obtener todos los urls

                    if vote_step:
                        vote_step_counter += 1
                        vote_id = f"{raw_motion.id}_{vote_step_counter}"


            final_steps.append(MotionStep(
                id = id,
                motion_id = raw_motion.id,
                vote_step = vote_step,
                vote_id = vote_id,
                step_date = date,
                step_detail = details,
                step_url = url,
            ))

        return final_steps

    else:
        return None

