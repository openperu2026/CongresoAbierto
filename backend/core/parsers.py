from __future__ import annotations

import re
import unicodedata
from backend.core.constants import (
    BILL_ROLE_MAPS,
    LEG_PERIOD_ALIASES,
    LEGISLATURE_ALIASES,
)
from backend.core.enums import (
    BillStepType,
    LegPeriod,
    LegislativeYear,
    Legislature,
    MotionStepType,
    MotionType,
    Proponents,
    RoleOrganization,
    RoleTypeBill,
)


def _normalize_leg_period(value: str) -> str:
    # 1) Unicode normalize (handles odd forms)
    v = unicodedata.normalize("NFKC", value)

    # 2) Replace non-breaking spaces and other common weird spaces with normal space
    v = v.replace("\xa0", " ").replace("\u202f", " ").replace("\u2007", " ")

    v = v.strip()

    # 3) normalize different dash characters to "-"
    v = re.sub(r"[–—−]", "-", v)

    # 4) normalize spaces around dash
    v = re.sub(r"\s*-\s*", "-", v)

    # 5) collapse multiple spaces
    v = re.sub(r"\s+", " ", v)

    return v


LEG_PERIOD_RE = re.compile(r"(\d{4})-(\d{4})")


def parse_leg_period(value: str) -> LegPeriod:
    if value is None:
        raise ValueError("leg_period cannot be null")

    v = _normalize_leg_period(value)

    canon = LEG_PERIOD_ALIASES.get(v)
    if canon is None:
        m = LEG_PERIOD_RE.search(v)
        if m:
            canon = f"{m.group(1)}-{m.group(2)}"

    if canon is None:
        raise ValueError(f"Unknown leg period: {value!r} (normalized={v!r})")

    return LegPeriod(canon)


def _normalize_legislature(value: str) -> str:
    v = value.strip()
    v = re.sub(r"\s+", " ", v)  # collapse whitespace
    return v


def parse_legislature(value: str) -> Legislature:
    if value is None:
        raise ValueError("legislature cannot be null")

    v = _normalize_legislature(value)
    canon = LEGISLATURE_ALIASES.get(v)

    if canon is None:
        raise ValueError(f"Unknown legislature: {value!r}")

    return Legislature(canon)


def parse_role_bill(value: int) -> RoleTypeBill:
    if value is None:
        raise ValueError("role_bill cannot be null")

    canon = BILL_ROLE_MAPS.get(value)
    if canon is None:
        raise ValueError(f"Unknown role_bill: {value!r}")
    return RoleTypeBill(canon)


def parse_motion_type(value: str) -> MotionType:
    if value is None:
        raise ValueError("motion_type cannot be null")

    v = " ".join(value.strip().split())

    # Direct match for scalar enum values.
    for item in MotionType:
        if isinstance(item.value, str) and item.value == v:
            return item

    raise ValueError(f"Unknown motion_type: {value!r}")


def parse_proponent(value: str) -> Proponents:
    if value is None:
        raise ValueError("proponent cannot be null")

    v = " ".join(value.strip().split())

    try:
        return Proponents(v)
    except ValueError:
        pass

    # Handle suffixes like "Congreso-Actualización"
    if "-" in v:
        head = v.split("-", 1)[0].strip()
        try:
            return Proponents(head)
        except ValueError:
            pass

    raise ValueError(f"Unknown proponent: {value!r}")


DES_ESTADO_TO_MOTION_STEP_TYPE: dict[str, MotionStepType] = {

    # Presented
    "Presentado": MotionStepType.PRESENTADO,
    
    # Admitted / not admitted
    "Admitida la Moción": MotionStepType.PENDIENTE_DEBATE,
    "NO ADMITIDA A DEBATE": MotionStepType.NO_ADMITIDA,
    "RECHAZADA LA ADMISIÓN A DEBATE": MotionStepType.NO_ADMITIDA,
    
    # Assigned / in committee
    "En Comisión": MotionStepType.EN_COMISION,
    "Integrantes de Comisión": MotionStepType.EN_COMISION,
    "Aprobado integrantes de Comisión": MotionStepType.EN_COMISION,
    
    # Agenda / internal routing (CD = Consejo Directivo)
    "En Agenda C.D": MotionStepType.AGENDA_CONSEJO_DIRECTIVO,
    "PARA SER VISTA POR EL CONSEJO DIRECTIVO": MotionStepType.AGENDA_CONSEJO_DIRECTIVO,
    "Tramitada con conocimiento del CD": MotionStepType.TRAMITADO_POR_CONSEJO_DIRECTIVO,
    "TRAMITADA CON ACUERDO DE CD": MotionStepType.TRAMITADO_POR_CONSEJO_DIRECTIVO,
    "Por Acuerdo de CD.": MotionStepType.TRAMITADO_POR_CONSEJO_DIRECTIVO,

    "Acuerdo Junta de Portavoces": MotionStepType.ACUERDO_JUNTA_PORTAVOCES,
    
    # Pleno routing / agenda
    "Para ser vista por el Pleno": MotionStepType.EN_AGENDA,
    "En Agenda del Pleno": MotionStepType.EN_AGENDA,
    "Orden del Día": MotionStepType.EN_AGENDA,
    "Dado cuenta en el Pleno": MotionStepType.EN_AGENDA,
    "Por Acuerdo de Pleno": MotionStepType.EN_AGENDA,
    
    # Debate
    "En Debate": MotionStepType.PENDIENTE_DEBATE,
    
    # Vote-ish / outcomes
    "Leída en sesión": MotionStepType.LEIDA_PLENO,
    "Aprobada": MotionStepType.APROBADO_PLENO,
    "Aprobada la Moción": MotionStepType.APROBADO_PLENO,
    "Rechazada": MotionStepType.RECHAZADO_PLENO,
    
    # Reconsideration
    "Reconsideración": MotionStepType.RECONSIDERACION,
    "Rechazada Reconsideración": MotionStepType.RECONSIDERACION,
    
    # Text updates
    "Texto consensuado": MotionStepType.TEXTO_SUSTITUTORIO,
    "Texto Sustitutorio": MotionStepType.TEXTO_SUSTITUTORIO,
    "Retiro de Firma": MotionStepType.RETIRO_FIRMA,
    "Adhesión": MotionStepType.TEXTO_SUSTITUTORIO,
    
    # Official comms / documents
    "Oficio": MotionStepType.OFICIO,
    
    # Publication
    "Publicado Diario Oficial  El Peruano": MotionStepType.PUBLICADA,
    
    # Appearances (minister, etc.)
    "Concurre Ministro": MotionStepType.MINISTRO,
    "Asiste": MotionStepType.MINISTRO,
    "Asistió el Ministro  para contestar el pliego.": MotionStepType.MINISTRO,
    
    # Order / procedural
    "Cuestión de Orden": MotionStepType.CUESTION_ORDEN,
    
    # Requirements / blocking status
    "INCUMPLE REQUISITOS PARA CONTINUAR SU TRÁMITE": MotionStepType.INCUMPLE_REQUISITOS,
    
    # Withdrawal
    "Solicita retiro de moción": MotionStepType.RETIRO_FIRMA,
    "RETIRADA POR SU AUTOR": MotionStepType.RETIRADO,
    
    # Archive
    "Al archivo": MotionStepType.ARCHIVO,
    "En Archivo General": MotionStepType.ARCHIVO,
    
    # Resignation (if applicable in your domain)
    "Renuncia": MotionStepType.RENUNCIA,
    
    # External routing / referrals
    "En Fiscalía de la Nación": MotionStepType.FISCALIA,
}


def classify_motion_des_estado(des_estado: str | None) -> MotionStepType:
    if not des_estado:
        return MotionStepType.DESCONOCIDO

    key = " ".join(des_estado.strip().split())  # trim + collapse whitespace
    return (
        DES_ESTADO_TO_MOTION_STEP_TYPE.get(key)
        or DES_ESTADO_TO_MOTION_STEP_TYPE.get(key.upper())
        or DES_ESTADO_TO_MOTION_STEP_TYPE.get(key.title())
        or MotionStepType.DESCONOCIDO
    )

DES_ESTADO_TO_STEP_TYPE: dict[str, BillStepType] = {
    "------": BillStepType.DESCONOCIDO,
    # Presented
    "PRESENTADO": BillStepType.PRESENTADO,

    # Assigned / committee routing
    "EN COMISIÓN": BillStepType.EN_COMISION,
    "PASA A COMISIÓN": BillStepType.EN_COMISION,
    "RETORNA A COMISIÓN": BillStepType.EN_COMISION,
    "Acumulado en Sala": BillStepType.EN_COMISION,

    # Committee stage artifacts / decisions
    "DICTAMEN": BillStepType.DICTAMEN,
    "ACUERDO DE COMISIÓN": BillStepType.DICTAMEN,

    # Exemptions / procedural shortcuts
    "Dispensado de Dictamen": BillStepType.EXCEPCION,
    "EXONERADO DE DICTAMEN": BillStepType.EXCEPCION,
    "EXONERADO DE PLAZO DE PUBLICACIÓN": BillStepType.EXCEPCION,
    "Dispensado de Publicación en el Portal": BillStepType.EXCEPCION,

    # Agenda
    "Orden del Día": BillStepType.EN_AGENDA,
    "EN AGENDA DEL PLENO": BillStepType.EN_AGENDA,
    "EN AGENDA DE LA COMISIÓN PERMANENTE": BillStepType.EN_AGENDA,

    # Debate
    "EN DEBATE - PLENO": BillStepType.PENDIENTE_DEBATE,
    "EN DEBATE - COMISIÓN PERMANENTE": BillStepType.PENDIENTE_DEBATE,
    "EN DEBATE DE LA COMISIÓN PERMANENTE": BillStepType.PENDIENTE_DEBATE,
    "EN CUARTO INTERMEDIO": BillStepType.PENDIENTE_DEBATE,
    "PARA CONSEJO DIRECTIVO": BillStepType.PENDIENTE_DEBATE,

    # Vote events
    "APROBADO 1ERA. VOTACIÓN": BillStepType.APROB_1_VOTACION,
    "Pendiente 2da. votación": BillStepType.PENDIENTE_2_VOTACION,
    "No alcanzó Nº de votos": BillStepType.NO_APROBADO,
    "NO APROBADO": BillStepType.NO_APROBADO,
    "APROBADO": BillStepType.APROB_2_VOTACION,
    "Aprobado Com.Permanente ": BillStepType.APROB_COM_PERMANENTE,
    "ACUERDO DEL PLENO": BillStepType.ACUERDO_PLENO,

    # Text / autographs (post-approval drafting)
    "TEXTO SUSTITUTORIO": BillStepType.TEXTO_SUSTITUTORIO,
    "AUTÓGRAFA": BillStepType.AUTÓGRAFA,
    "AUTÓGRAFA OBSERVADA": BillStepType.AUTÓGRAFA,
    "Retiro de Firma": BillStepType.RETIRO_FIRMA,  
    "ACLARACIÓN": BillStepType.ACLARACION,

    # Withdrawal
    "Retirado por su Autor": BillStepType.RETIRADO,
    "Solicita Retiro": BillStepType.RETIRADO,

    # Reconsideration
    "EN RECONSIDERACIÓN": BillStepType.RECONSIDERACION,

    # Rejection
    "RECHAZADO": BillStepType.NO_APROBADO,

    # Archive
    "Al Archivo": BillStepType.ARCHIVO,
    "DECRETO DE ARCHIVO": BillStepType.ARCHIVO,

    # Promulgation / publication
    "Promulgado/Presidente de la República": BillStepType.PUBLICADA,
    "Promulgado/Presidente del Congreso": BillStepType.PUBLICADA,
    "Publicada en el Diario Oficial El Peruano": BillStepType.PUBLICADA,
}


def classify_des_estado(des_estado: str | None) -> BillStepType:
    if not des_estado:
        return BillStepType.DESCONOCIDO

    key = " ".join(des_estado.strip().split())  # trim + collapse whitespace
    # keep original casing keys in mapping, but also try upper
    return DES_ESTADO_TO_STEP_TYPE.get(key) or DES_ESTADO_TO_STEP_TYPE.get(
        key.upper(), BillStepType.DESCONOCIDO
    )


def find_leg_period(leg_year: LegislativeYear):
    int_year = int(leg_year)

    if int_year in range(2026, 2031):
        return parse_leg_period("Parlamentario 2026 - 2031")
    if int_year in range(2021, 2026):
        return parse_leg_period("Parlamentario 2021 - 2026")
    if int_year in range(2016, 2021):
        return parse_leg_period("Parlamentario 2016 - 2021")
    if int_year in range(2011, 2016):
        return parse_leg_period("Parlamentario 2011 - 2016")
    if int_year in range(2006, 2011):
        return parse_leg_period("Parlamentario 2006 - 2011")
    if int_year in range(2001, 2006):
        return parse_leg_period("Parlamentario 2001 - 2006")
    if int_year in range(2000, 2001):
        return parse_leg_period("Parlamentario 2000 - 2001")
    if int_year in range(1995, 2000):
        return parse_leg_period("Parlamentario 1995 - 2000")
    return parse_leg_period("CCD 1992 -1995")


def normalize_membership_role(raw: str) -> str:
    if not raw:
        raise ValueError("Empty membership role")

    role = raw.strip().lower()

    role_map = {
        "presidenta": "presidente",
        "presidente": "presidente",
        "vicepresidenta": "vicepresidente",
        "vicepresidente": "vicepresidente",
        "secretaria": "secretario",
        "secretario": "secretario",
        "vocera": "vocero",
        "vocero": "vocero",
        "miembro": "miembro",
        "titular": "titular",
        "suplente": "suplente",
        "accesitaria": "accesitario",
        "accesitario": "accesitario",
    }

    canon = role_map.get(role)

    if canon is None:
        raise ValueError(f"Unknown role: {role!r}")

    return RoleOrganization(canon)


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\xa0", " ").replace("\u202f", " ").replace("\u2007", " ")
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


# Canonical outputs must exactly match your enum values
_COMM_TYPE_RULES: list[tuple[re.Pattern[str], str]] = [
    # Most specific first
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+acusaciones\s+constitucionales", re.I),
        "Subcomisión de Acusaciones Constitucionales",
    ),
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+control\s+pol[ií]tico", re.I),
        "Subcomisión de Control Político",
    ),
    (
        re.compile(
            r"^comisi[oó]n\s+de\s+levantamiento\s+de\s+inmunidad\s+parlamentaria", re.I
        ),
        "Comisión de Levantamiento de Inmunidad Parlamentaria",
    ),
    (
        re.compile(r"^comisi[oó]n\s+de\s+[eé]tica\s+parlamentaria", re.I),
        "Comisión de Ética Parlamentaria",
    ),
    (
        re.compile(r"^sub\s*comisi[oó]n\s+de\s+seguimiento\s+del\s+tlc", re.I),
        "Sub Comisión de Seguimiento del TLC",
    ),
    # Common noisy cases
    (re.compile(r"^comisi[oó]n\s+ordinaria\b", re.I), "Comisión Ordinaria"),
    (
        re.compile(r"^comisiones?\s+investigadoras?\b", re.I),
        "Comisiones Investigadoras",
    ),
    (re.compile(r"^comisiones?\s+especiales?\b", re.I), "Comisiones Especiales"),
    (re.compile(r"^grupo\s+de\s+trabajo\b", re.I), "Grupo de Trabajo"),
]


def parse_comm_type(value: str) -> str:
    raw = value
    v = _norm_text(value)

    # normalize dash variants (optional, but consistent with your style)
    v = re.sub(r"[–—−]", "-", v)

    for pat, canon in _COMM_TYPE_RULES:
        if pat.search(v):
            return canon

    raise ValueError(f"Unknown comm_type: {raw!r} (normalized={v!r})")
