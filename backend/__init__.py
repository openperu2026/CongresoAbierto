from enum import Enum
import re

URL = {
    "congresistas": "https://www.congreso.gob.pe/pleno/congresistas/",
    "proyectos_ley": "https://wb2server.congreso.gob.pe/spley-portal/#/expediente/search",
    "dictamenes": "https://wb2server.congreso.gob.pe/spley-portal/#/dictamenes/periodos",
    "leyes": "https://www.leyes.congreso.gob.pe/",
    "asistencia_pleno": "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-votacion-pleno",
    "asistencia_comision_permanente": "https://www.congreso.gob.pe/AsistenciasVotacionesPleno/asistencia-comisionpermanente",
    "actas_comisiones": "https://www.congreso.gob.pe/actascomisiones/",
    "conformacion_comisiones": "https://www.congreso.gob.pe/CuadrodeComisiones/",
}

# Might need to review and make sure everyone is here
PARTIES = [
    " AP ",
    " AP-PIS ",
    " APP ",
    " BM ",
    " BDP ",
    " BOP ",
    " BS ",
    " BSS ",
    " E ",
    " FP ",
    " HYD ",
    " JP ",
    " IJPP-VP ",
    " JPP-VP ",
    " NA ",
    " NP ",
    " PL ",
    " PLG ",
    " PM ",
    " PP ",
    " SP ",
    " sP ",
    " RP ",
    " 8S ",
    " 8M ",
]

# Dictionary to avoid creation of duplicate parties objects
PARTY_ALIASES = {
    "Alianza para el Progreso": "Alianza para el Progreso del Perú",
    "Somos Perú": "Partido Democrático Somos Perú",
    "Frente Amplio": "Frente Amplio por Justicia, Vida y Libertad",
    "Frente Popular Agrícola del Perú": "Frente Popular Agrícola FIA del Perú",
    "No Agrupado": "Ninguno",
    "No ha acreditado": "Ninguno",
    "No registrado": "Ninguno",
    "Alianza Solidaridad Nacional": "Solidaridad Nacional",
    "Unión por el Perú": "Unión por el Perú - Social Democracia",
}

class MajorityType(str, Enum):
    SIMPLE = "simple"
    ABSOLUTE = "absolute"
    QUALIFIED = "qualified"    

class VoteResult(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIED = "tied"
    NO_QUORUM = "no_quorum"
    SUSPENDED = "suspended"          # cuarto intermedio
    RETURNED_TO_COMMITTEE = "returned_to_committee"
    FILED = "filed"
    WITHDRAWN = "withdrawn"

class VoteOption(str, Enum):
    SI = "si"
    NO = "no"
    ABSTENCION = "abstencion"
    SIN_RESPUESTA = "sin respuesta"


class AttendanceStatus(str, Enum):
    PRESENTE = "presente"
    AUSENTE = "ausente"
    LICENCIA = "con licencia"
    SUSPENDIDO = "suspendido"


class BillStepType(str, Enum):
    UNKNOWN = "unknown"
    PRESENTED = "presented"
    ASSIGNED = "assigned to committee"
    COMMITTEE_STAGE = "committee stage"
    AGENDA = "agenda"
    DEBATE = "debate"
    VOTE = "vote"
    RECONSIDERATION = "reconsideration"
    APPROVED = "approved"
    REJECTED = "rejected"
    TEXT_UPDATE = "text update"
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"
    PROMULGATED = "promulgated"
    PUBLISHED = "published"
    CLARIFICATION = "clarification"
    INTERNAL_ROUTE = "internal routing"
    EXEMPTION = "exemption"

DES_ESTADO_TO_STEP_TYPE: dict[str, BillStepType] = {
    "------": BillStepType.UNKNOWN,

    # Presented
    "PRESENTADO": BillStepType.PRESENTED,

    # Assigned / committee routing
    "EN COMISIÓN": BillStepType.ASSIGNED,
    "PASA A COMISIÓN": BillStepType.ASSIGNED,
    "RETORNA A COMISIÓN": BillStepType.ASSIGNED,
    "Acumulado en Sala": BillStepType.INTERNAL_ROUTE,

    # Committee stage artifacts / decisions
    "DICTAMEN": BillStepType.COMMITTEE_STAGE,
    "ACUERDO DE COMISIÓN": BillStepType.COMMITTEE_STAGE,

    # Exemptions / procedural shortcuts
    "Dispensado de Dictamen": BillStepType.EXEMPTION,
    "EXONERADO DE DICTAMEN": BillStepType.EXEMPTION,
    "EXONERADO DE PLAZO DE PUBLICACIÓN": BillStepType.EXEMPTION,
    "Dispensado de Publicación en el Portal": BillStepType.EXEMPTION,

    # Agenda
    "Orden del Día": BillStepType.AGENDA,
    "EN AGENDA DEL PLENO": BillStepType.AGENDA,
    "EN AGENDA DE LA COMISIÓN PERMANENTE": BillStepType.AGENDA,

    # Debate
    "EN DEBATE - PLENO": BillStepType.DEBATE,
    "EN DEBATE - COMISIÓN PERMANENTE": BillStepType.DEBATE,
    "EN DEBATE DE LA COMISIÓN PERMANENTE": BillStepType.DEBATE,

    # Vote events
    "APROBADO 1ERA. VOTACIÓN": BillStepType.VOTE,
    "Pendiente 2da. votación": BillStepType.VOTE,
    "No alcanzó Nº de votos": BillStepType.VOTE,
    "NO APROBADO": BillStepType.VOTE,

    # Approval outcomes
    "APROBADO": BillStepType.APPROVED,
    "Aprobado Com.Permanente ": BillStepType.APPROVED,
    "ACUERDO DEL PLENO": BillStepType.APPROVED,

    # Text / autographs (post-approval drafting)
    "TEXTO SUSTITUTORIO": BillStepType.TEXT_UPDATE,
    "AUTÓGRAFA": BillStepType.TEXT_UPDATE,
    "AUTÓGRAFA OBSERVADA": BillStepType.TEXT_UPDATE,
    "Retiro de Firma": BillStepType.TEXT_UPDATE,  # could also be WITHDRAWN depending on how you interpret it

    # Reconsideration
    "EN RECONSIDERACIÓN": BillStepType.RECONSIDERATION,

    # Rejection
    "RECHAZADO": BillStepType.REJECTED,

    # Withdrawal
    "Retirado por su Autor": BillStepType.WITHDRAWN,
    "Solicita Retiro": BillStepType.WITHDRAWN,

    # Archive
    "Al Archivo": BillStepType.ARCHIVED,
    "DECRETO DE ARCHIVO": BillStepType.ARCHIVED,

    # Promulgation / publication
    "Promulgado/Presidente de la República": BillStepType.PROMULGATED,
    "Promulgado/Presidente del Congreso": BillStepType.PROMULGATED,
    "Publicada en el Diario Oficial El Peruano": BillStepType.PUBLISHED,

    # Clarification / internal routing
    "ACLARACIÓN": BillStepType.CLARIFICATION,
    "EN CUARTO INTERMEDIO": BillStepType.INTERNAL_ROUTE,
    "PARA CONSEJO DIRECTIVO": BillStepType.INTERNAL_ROUTE,
}

def classify_des_estado(des_estado: str | None) -> BillStepType:
    if not des_estado:
        return BillStepType.UNKNOWN

    key = " ".join(des_estado.strip().split())  # trim + collapse whitespace
    # keep original casing keys in mapping, but also try upper
    return DES_ESTADO_TO_STEP_TYPE.get(key) or DES_ESTADO_TO_STEP_TYPE.get(key.upper(), BillStepType.UNKNOWN)


class RoleTypeBill(str, Enum):
    AUTHOR = "author"
    COAUTHOR = "coauthor"
    ADHERENTE = "adherente"

BILL_ROLE_MAPS =  {
    1 : 'author',
    2 : 'coauthor',
    3 : 'adherente'
}

def parse_role_bill(value: int) -> RoleTypeBill:
    if value is None:
        raise ValueError("role_bill cannot be null")

    canon = BILL_ROLE_MAPS.get(value)
    if canon is None:
        raise ValueError(f"Unknown role_bill: {value!r}")
    return RoleTypeBill(canon)

class Proponents(str, Enum):
    CONGRESO = "Congreso"
    PODER_EJECUTIVO = "Poder Ejecutivo"
    MINISTERIO_PUBLICO = "Ministerio Público"
    DEFENSORIA = "Defensoría del Pueblo"
    JNE = "Jurado Nacional de Elecciones"
    CONTRALORIA = "Contraloría General de la República"
    TRIBUNAL_CONSTITUCIONAL = "Tribunal Constitucional"
    BANCO_CENTRAL = "Banco Central de Reserva"
    SBS = "Superintendencia de Banca y Seguros"
    COLEGIOS_PROF = "Colegios Profesionales"
    INI_CIUDADANA = "Iniciativas Ciudadanas"
    PODER_JUDICIAL = "Poder Judicial"
    GORES = "Gobiernos Regionales"
    GOLOS = "Gobiernos Locales"


class LegPeriod(str, Enum):
    PERIODO_2021_2026 = "2021-2026"
    PERIODO_2016_2021 = "2016-2021"
    PERIODO_2011_2016 = "2011-2016"
    PERIODO_2006_2011 = "2006-2011"
    PERIODO_2001_2006 = "2001-2006"
    PERIODO_2000_2001 = "2000-2001"
    PERIODO_1995_2000 = "1995-2000"
    PERIODO_1992_1995 = "1992-1995"

LEG_PERIOD_ALIASES = {
    "Parlamentario 2021 - 2026": "2021-2026",
    "2021 - 2026": "2021-2026",
    "2021–2026": "2021-2026",
    "2021-2026": "2021-2026",

    "Parlamentario 2016 - 2021": "2016-2021",
    "2016 - 2021": "2016-2021",
    "2016–2021": "2016-2021",
    "2016-2021": "2016-2021",

    "Parlamentario 2011 - 2016": "2011-2016",
    "2011 - 2016": "2011-2016",
    "2011–2016": "2011-2016",
    "2011-2016": "2011-2016",

    "Parlamentario 2006 - 2011": "2006-2011",
    "2006 - 2011": "2006-2011",
    "2006–2011": "2006-2011",
    "2006-2011": "2006-2011",

    "Parlamentario 2001 - 2006": "2001-2006",
    "2001 - 2006": "2001-2006",
    "2001–2006": "2001-2006",
    "2001-2006": "2001-2006",

    "Parlamentario 2000 - 2001": "2000-2001",
    "2000 - 2001": "2000-2001",
    "2000–2001": "2000-2001",
    "2000-2001": "2000-2001",

    "Parlamentario 1995 - 2000": "1995-2000",
    "1995 - 2000": "1995-2000",
    "1995–2000": "1995-2000",
    "1995-2000": "1995-2000",

    "CCD 1992 -1995": "1992-1995",
    "CCD 1992 - 1995": "1992-1995",
    "1992-1995": "1992-1995",
}

def _normalize_leg_period(value: str) -> str:
    v = value.strip()
    # normalize different dash characters to "-"
    v = re.sub(r"[–—−]", "-", v)
    # normalize spaces around dash
    v = re.sub(r"\s*-\s*", "-", v)
    # collapse multiple spaces
    v = re.sub(r"\s+", " ", v)
    return v

def parse_leg_period(value: str) -> LegPeriod:
    if value is None:
        raise ValueError("leg_period cannot be null")

    v = _normalize_leg_period(value)
    canon = LEG_PERIOD_ALIASES.get(v)
    if canon is None:
        raise ValueError(f"Unknown leg period: {value!r}")
    return LegPeriod(canon)


class Legislature(str, Enum):
    LEGISLATURA_2026_1 = "2026-I"
    LEGISLATURA_2025_2 = "2025-II"
    LEGISLATURA_2025_1 = "2025-I"
    LEGISLATURA_2024_2 = "2024-II"
    LEGISLATURA_2024_1 = "2024-I"
    LEGISLATURA_2023_2 = "2023-II"
    LEGISLATURA_2023_1 = "2023-I"
    LEGISLATURA_2022_2 = "2022-II"
    LEGISLATURA_2022_1 = "2022-I"
    LEGISLATURA_2021_2 = "2021-II"
    LEGISLATURA_2021_1 = "2021-I"
    LEGISLATURA_2020_2 = "2020-II"
    LEGISLATURA_2020_1 = "2020-I"
    LEGISLATURA_2019_2 = "2019-II"
    LEGISLATURA_2019_1 = "2019-I"
    LEGISLATURA_2018_2 = "2018-II"
    LEGISLATURA_2018_1 = "2018-I"
    LEGISLATURA_2017_2 = "2017-II"
    LEGISLATURA_2017_1 = "2017-I"
    LEGISLATURA_2016_2 = "2016-II"

LEGISLATURE_ALIASES = {
    # Congress wording → canonical legislature code

    # 2025
    "Primera Legislatura Ordinaria 2025": "2025-II",
    "Segunda Legislatura Ordinaria 2025": "2026-I",

    # 2024
    "Primera Legislatura Ordinaria 2024": "2024-II",
    "Segunda Legislatura Ordinaria 2024": "2025-I",

    # 2023
    "Primera Legislatura Ordinaria 2023": "2023-II",
    "Segunda Legislatura Ordinaria 2023": "2024-I",

    # 2022
    "Primera Legislatura Ordinaria 2022": "2022-II",
    "Segunda Legislatura Ordinaria 2022": "2023-I",

    # 2021
    "Primera Legislatura Ordinaria 2021": "2021-II",
    "Segunda Legislatura Ordinaria 2021": "2022-I",

    # 2020
    "Primera Legislatura Ordinaria 2020": "2020-II",
    "Segunda Legislatura Ordinaria 2020": "2021-I",

    # 2019
    "Primera Legislatura Ordinaria 2019": "2019-II",
    "Segunda Legislatura Ordinaria 2019": "2020-I",

    # 2018
    "Primera Legislatura Ordinaria 2018": "2018-II",
    "Segunda Legislatura Ordinaria 2018": "2019-I",

    # 2017
    "Primera Legislatura Ordinaria 2017": "2017-II",
    "Segunda Legislatura Ordinaria 2017": "2018-I",
}

def _normalize_legislature(value: str) -> str:
    v = value.strip()
    v = re.sub(r"\s+", " ", v)   # collapse whitespace
    return v

def parse_legislature(value: str) -> Legislature:
    if value is None:
        raise ValueError("legislature cannot be null")

    v = _normalize_legislature(value)
    canon = LEGISLATURE_ALIASES.get(v)

    if canon is None:
        raise ValueError(f"Unknown legislature: {value!r}")

    return Legislature(canon)


class LegislativeYear(str, Enum):
    YEAR_2025_2026 = "2025"
    YEAR_2024_2025 = "2024"
    YEAR_2023_2024 = "2023"
    YEAR_2022_2023 = "2022"
    YEAR_2021_2022 = "2021"
    YEAR_2020_2021 = "2020"
    YEAR_2019_2020 = "2019"
    YEAR_2018_2019 = "2018"
    YEAR_2017_2018 = "2017"
    YEAR_2016_2017 = "2016"

def find_leg_period(leg_year: LegislativeYear):

    int_year = int(leg_year)

    if int_year in range(2021,2026):
        return LegPeriod("Parlamentario 2021 - 2026")
    elif int_year in range(2016,2021):
        return LegPeriod("Parlamentario 2016 - 2021")
    elif int_year in range(2011,2016):
        return LegPeriod("Parlamentario 2011 - 2016")
    elif int_year in range(2006,2011):
        return LegPeriod("Parlamentario 2006 - 2011")
    elif int_year in range(2001,2006):
        return LegPeriod("Parlamentario 2001 - 2006")
    elif int_year in range(2000,2001):
        return LegPeriod("Parlamentario 2000 - 2001")
    elif int_year in range(1995,2000):
        return LegPeriod("Parlamentario 1995 - 2000")
    else:
        return LegPeriod("CCD 1992 -1995")

class RoleOrganization(str, Enum):
    # For Bancadas | Partidos
    VOCERO = "vocero"
    MIEMBRO = "miembro"

    # For Comisiones, Mesa Directiva, Junta de Portavoces
    PRESIDENTE = "presidente"
    PRESIDENTA = "presidenta"
    VICEPRESIDENTE = "vicepresidente"
    VICEPRESIDENTA = "vicepresidenta"
    SECRETARIO = "secretario"
    SECRETARIA = "secretaria"
    TITULAR = "titular"
    SUPLENTE = "suplente"
    ACCESITARIO = "accesitario"


class TypeOrganization(str, Enum):
    COMISON = "Comisión"
    JUNTA_DE_PORTAVOCES = "Junta de Portavoces"
    MESA_DIRECTIVA = "Mesa Directiva"
    COMISION_PERMANENTE = "Comisión Permanente"
    CONSEJO_DIRECTIVO = "Consejo Directivo"

class TypeCommittee(str, Enum):
    # For Committees
    COM_INVESTIGADORA = "Comisiones Investigadoras"
    GRUPO_TRABAJO = "Grupo de Trabajo"
    SUBCOM_AC = "Subcomisión de Acusaciones Constitucionales"
    SUBCOM_CP = "Subcomisión de Control Político"
    COM_LEV_INMUN = "Comisión de Levantamiento de Inmunidad Parlamentaria"
    COM_ORD = "Comisión Ordinaria"
    SUBCOM_TLC = "Sub Comisión de Seguimiento del TLC"
    COM_ESP = "Comisiones Especiales"
    COM_ETICA = "Comisión de Ética Parlamentaria"