from io import BytesIO
import re
import unicodedata
import fitz
from PIL import Image
import numpy as np
import cv2
import pytesseract
from jellyfish import jaro_winkler_similarity as jws
from typing import Dict, List, Any, Optional

BANCADA_START = r"\|\s*AP\s*\|"
# STEP 4 — Stable token defs
# -------------------------

BANCADA_RE = r"[A-Z]{1,5}(?:-[A-Z]{1,5}){0,3}"
NAME_RE = r"[A-Z .'\-]+,\s*[A-Z .'\-]+"

SI_RE   = r"SI"
NO_RE   = r"NO"
AUS_RE  = r"(?:AUS|AIS|US)"
ABST_RE = r"ABST\.?"          # dot optional
ASIS_RE = r"PRE"              # (not used in VOTE_RE right now)
OTHER_RE= r"(?:SINRRES|SINRES|TTT|TT|LP|LE|LO)"  # longer-first helps
STAR_RE = r"\*{1,4}"

# whole-token boundary (avoid matching inside words)
TOKEN = r"(?<![A-Z0-9])(?:{tok})(?![A-Z0-9])"

VOTE_RE = rf"(?:{TOKEN.format(tok=OTHER_RE)}|{TOKEN.format(tok=AUS_RE)}|{TOKEN.format(tok=ABST_RE)}|{TOKEN.format(tok=SI_RE)}|{TOKEN.format(tok=NO_RE)}|{TOKEN.format(tok=STAR_RE)})"

DOBLE_RE = re.compile(
    rf"""
    \s*(?P<name>{NAME_RE})\s*\|      # NAME |
    \s*(?P<vote>{VOTE_RE})           # VOTE token
    """,
    re.VERBOSE
)

#Para la parte de abajo
FAVOR_HDR = (
    r"VOTO\s+A\s+FAVOR\s+DE\s+"
    r"(?:(?:LA|EL|LOS|LAS)\s+)?"
    r"(?:CONGRESISTA|CONGRESISTAS)\s+"
)

CONTRA_HDR = (
    r"VOTO\s+EN\s+CONTRA\s+DE\s+"
    r"(?:(?:LA|EL|LOS|LAS)\s+)?"
    r"(?:CONGRESISTA|CONGRESISTAS)\s+"
)

ABST_HDR = (
    r"VOTO\s+EN\s+ABSTENCION\s+DEL?\s+"
    r"(?:(?:LA|EL|LOS|LAS)\s+)?"
    r"(?:CONGRESISTA|CONGRESISTAS)\s+"
)










def say_hello():
    print("que se cuiden los malditos")


def read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def normalize_text(
    text: str,
) -> str:
    """
    Normalize OCR text for regex parsing.
    Parameters
    ----------
    text : str

    Returns
    -------
    str Normalized text.
    """

    if not isinstance(text, str):
        raise TypeError("Input must be string")

    #Normalize unicode (important for OCR)
    text = unicodedata.normalize("NFKC", text)
    #Standardize pipes spacing
    text = re.sub(r"\s*\|\s*", " | ", text)
    # Replace multiple spaces/tabs with single space
    text = re.sub(r"[ \t]+", " ", text)
    #Remove excessive blank lines
    text = re.sub(r"\n\s*\n+", "\n", text)
    #Strip leading/trailing whitespace
    text = text.strip()
    #UPPERCASE
    text = text.upper()

    #Remove accents 
    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
        )


    #Remove ALL + - =
    text = re.sub(r"[+\-=]+", " ", text)

    # Clean spacing again
    text = re.sub(r"[ \t]+", " ", text)
    return text


def get_type(text: str) -> str | None:

    # Detect VOTACION
    if re.search(r"\bVOTACI[OÓ]N\s*:", text):
        return "VOTACION"

    # Detect ASISTENCIA
    if re.search(r"\bASISTENCIA\s*:", text):
        return "ASISTENCIA"

    return None


# Name hint without accents (since you removed them)
#ROW_NAME_HINT = re.compile(r"[A-Z .'\-]+,\s*[A-Z .'\-]+")


def locate_blocks(
    text_clean: str,
    doc_type: str
    ) -> Dict[str, object]:
    """
    Locate boundaries and extract a best-guess title block for VOTACION docs.
    Assumes text is already cleaned (UPPERCASE, no accents, clean spaces).
    """

    if doc_type not in {"VOTACION", "ASISTENCIA"}:
        return {
            "header_block": None,
            "table_block": None,
        }
    anchor_pat = r"\bVOTACION\s*:" if doc_type == "VOTACION" else r"\bASISTENCIA\s*:"

    warnings: List[str] = []

    # 1) Find anchor line
    head_match = re.search(anchor_pat, text_clean)
    if head_match is None:
        return {
            "header_block": None,
            "table_block": None,
            "additional block": None,
            "warnings": ["Anchor (VOTACION/ASISTENCIA) not found."],
        }

    # 2) Find table start
    table_match = re.search(BANCADA_START, text_clean)
    if table_match is None:
        return {
            "header_block": text_clean[head_match.start():].strip(),
            "table_block": None,
            "warnings": ["Table start not found using BANCADA_START."],
        }

    if table_match.start() < head_match.start():
        warnings.append("Table start found before anchor; check OCR normalization.")

    header_block = text_clean[head_match.start():table_match.start()].strip()
    table_block = text_clean[table_match.start():].strip()

    return {
            "header_block": header_block,
            "table_block": table_block,
            "warnings": warnings,
        }


def _parse_fecha(fecha: str):
    if not isinstance(fecha, str):
        return None
    try:
        day, month, year = [int(x) for x in fecha.split("/")]
        return (year, month, day)
    except Exception:
        return None

def get_fecha(text):

    fecha_match = re.search(r'[Ff]echa[:\s]*([\d/]+)', text, re.IGNORECASE)
    if not fecha_match:
        fecha_match = re.search(r'[Ee]ccha[:\s]*([\d/]+)', text, re.IGNORECASE)

    fecha = fecha_match.group(1) if fecha_match else "Not found"

    return _parse_fecha(fecha)




def get_title(text):
    start = text.find("ASUNTO:")
    if start == -1:
        return ""
    
    start += len("ASUNTO:")
    remaining = text[start:]

    # Find first letter or number
    match = re.search(r"[A-Z0-9]", remaining)
    if not match:
        return ""

    return remaining[match.start():].strip()


def parse_vote_table(table_text: str) -> Dict[str, Any]:
    """
    Parse table block where the repeated structure is:
      | BANCADA | NAME | VOTE

    Works even if OCR returns everything as one long line (no \\n).
    Does NOT rely on row splitting, so it won't treat LP/SI as bancada.
    """
    if not isinstance(table_text, str):
        raise TypeError("table_text must be a string")

    lines = table_text.strip()

    resultados: List[Dict[str, Any]] = []
    for m in DOBLE_RE.finditer(lines):
        vote = m.group("vote").strip().upper()

        rec = {
            #"bancada": m.group("bancada").strip(),
            "nombre_completo": m.group("name").strip(),
            "voto": vote,
        }

        resultados.append(rec)


    return {
        "resultados": resultados,
        "stats": {"records_out": len(resultados)}
    }


def extraction_first_second(resultados):
    result = []

    for c in resultados:
        c_new = c.copy()  # copy each dict

        nombre = c_new.get("nombre_completo")
        if isinstance(nombre, str) and "," in nombre:
            last_name, first_name = nombre.split(",", 1)
            first_name = first_name.strip()
            last_name = last_name.strip()

            c_new["nombre"] = first_name
            c_new["apellido"] = last_name
            c_new["nombre_completo"] = f"{last_name} {first_name}"

        result.append(c_new)

    return result








#### FOR THE EXCEPTION PART
def find_below_block(text):
    start = text.find("EL PRESIDENTE DEL CONGRESO DEJA CONSTANCIA")
    return text[start:].strip()



def clean_vote_block(text: str) -> str:
    if not isinstance(text, str):
        return ""

    #Eliminar saltos de línea
    text = text.replace("\n", " ")

    #Eliminar todo lo entre ** ... **
    text = re.sub(r"\*\*.*?\*\*", "", text)
    #Eliminar símbolos &, |
    text = re.sub(r"[&|]", "", text)

    #Eliminar todos los numeros
    text = re.sub(r"\d+", "", text)
    # Eliminar espacios múltiples
    text = re.sub(r"\s{2,}", " ", text)

     #Eliminar "FALLECIDOS (F)"
    # Tiene que ser al ultimo luego de limpiar todos
    text = re.sub(r"FALLECIDOS\s*\(F\)", "", text)

    # Eliminar espacios múltiples, uevamente
    text = re.sub(r"\s{2,}", " ", text)


    return text.strip()


def _split_nombres(raw: str) -> List[str]:
    raw = raw.strip()

    # Remove leading/trailing connector junk if OCR leaves it
    raw = re.sub(r"^(?:LA|EL|LOS|LAS|DEL|DE)\s+", "", raw)
    raw = re.sub(r"\s+(?:DEL|DE)$", "", raw)

    # Split by ; or , (names lists)
    parts = re.split(r"\s*[;,]\s*", raw)

    cleaned = []
    for p in parts:
        p = p.strip(" .;:-")
        # Remove residual words inside the captured chunk
        p = re.sub(r"\b(?:LA|EL|LOS|LAS|DEL|DE)\b", "", p).strip()
        p = re.sub(r"\bCONGRESISTA(S)?\b", "", p).strip()
        if p:
            cleaned.append(p)
    return cleaned

def extract_constancias(text: str) -> List[Dict[str, str]]:
    t = text.upper()

    favor_pat  = re.compile(rf"{FAVOR_HDR}(?P<nombres>.+?)(?=(?:{CONTRA_HDR}|{ABST_HDR})|$)", re.DOTALL)
    contra_pat = re.compile(rf"{CONTRA_HDR}(?P<nombres>.+?)(?=(?:{ABST_HDR})|$)", re.DOTALL)
    abst_pat   = re.compile(rf"{ABST_HDR}(?P<nombres>.+?)(?=$)", re.DOTALL)

    out: List[Dict[str, str]] = []

    # Helper to append results
    def add_results(match, voto):
        if not match:
            return
        nombres = _split_nombres(match.group("nombres"))
        for nombre in nombres:
            congressman = {
                "nombre_completo": nombre.strip(),
                "apellido": nombre.strip(),  # si luego quieres separar, lo hacemos
                "voto": voto
            }
            out.append(congressman)

    add_results(favor_pat.search(t), "SI")
    add_results(contra_pat.search(t), "NO")
    add_results(abst_pat.search(t), "ABST")

    return out


###### FUNCTION FOR FORMATING THE INCOMING JSON BASE


def format_jsn(congresistas):
    list_congreso = []
    for item in congresistas:
        dict_congresista = {}
        dict_congresista["id"] = item["id"]
        dict_congresista["nombre"] = normalize_text(item["nombre"])
        dict_congresista["apellido"] = normalize_text(item["apellido"])
        dict_congresista["nombre_completo"] = dict_congresista["apellido"] + " " + dict_congresista["nombre"]
        dict_congresista["partido"] = item["party_name"]
        dict_congresista["bancada"] = item["bancada"]
        dict_congresista["en_ejercicio"] = item["en_ejercicio"]
        dict_congresista["voto"] = None
        dict_congresista["periodo"]= item["periodo"]

        list_congreso.append(dict_congresista)

    return list_congreso



def _period_contains(periodo: dict, target):
    if not isinstance(periodo, dict):
        return False
    inicio = periodo.get("inicio")
    fin = periodo.get("fin")
    if not (isinstance(inicio, str) and isinstance(fin, str)):
        return False
    try:
        d_i, m_i, y_i = [int(x) for x in inicio.split("/")]
        d_f, m_f, y_f = [int(x) for x in fin.split("/")]
        start = (y_i, m_i, d_i)
        end = (y_f, m_f, d_f)
    except Exception:
        return False
    return start <= target <= end



def define_enejercicio(congresistas_raw, fecha):
    """"
    congresistas_raw: producto of a json.load(f)  
    fecha: a fecha in format dd/mm/year

    """
    # If fecha is between inicio and fin in "periodo" for each congresista,
    # set "en_ejercicio"=True, else set it to False.
    if not fecha:
        return congresistas_raw

    # Accept either "dd/mm/yyyy" string or (year, month, day) tuple.
    if isinstance(fecha, tuple) and len(fecha) == 3:
        target = fecha
    else:
        target = _parse_fecha(fecha)
    if not target:
        return congresistas_raw

    for c in congresistas_raw:
        periodo = c.get("periodo") 
        found=None
        if _period_contains(periodo, target):
            found = True
            c["en_ejercicio"] = found

    return congresistas_raw
        


def define_bancada(congresistas_raw, fecha):
    """"
    congresistas_raw: producto of a json.load(f)
    fecha: a fecha in format dd/mm/year

    """
    # If fecha is between inicio and fin in "bancada.periodo",
    # set "bancada" to the bancada name for that period.
    if not fecha:
        return congresistas_raw

    # Accept either "dd/mm/yyyy" string or (year, month, day) tuple.
    if isinstance(fecha, tuple) and len(fecha) == 3:
        target = fecha
    else:
        target = _parse_fecha(fecha)
    if not target:
        return congresistas_raw

    for c in congresistas_raw:
        bancada = c.get("bancada")
        found = None
        for item in bancada:
            if not isinstance(item, dict):
                continue
            if _period_contains(item.get("periodo"), target):
                found = item.get("name")
                c["bancada"] = found

    return congresistas_raw


#######MATCHING FUNCTIONS

def matching_lists(lst_congres, lst_results, threshold=0.90):
    """
    Match congresistas to attendance/vote rows using Jaro-Winkler similarity
    on nombre_completo. Enforces one-to-one matching (no reuse) and picks the
    best match (highest score), not the first match.
    """

    # Ensure every attendance row has nombre_completo
    att = []
    for x in lst_results:
        x2 = x.copy()
        if "nombre_completo" not in x2 or not isinstance(x2["nombre_completo"], str):
            x2["nombre_completo"] = "NO_NAME"
        att.append(x2)

    # Sort (optional, mostly for reproducibility)
    sorted_congres = sorted(lst_congres, key=lambda x: x.get("nombre_completo", ""))
    sorted_attendance = sorted(att, key=lambda x: x.get("nombre_completo", ""))

    used = set()  # indices in sorted_attendance already matched

    for congresista in sorted_congres:
        # Only fill if still missing
        if congresista.get("voto") is not None:
            continue

        best_i = None
        best_score = -1.0

        c_name = congresista.get("nombre_completo") or ""
        if not isinstance(c_name, str) or not c_name.strip():
            continue

        # Find best unused match
        for i, row in enumerate(sorted_attendance):
            if i in used:
                continue
            r_name = row.get("nombre_completo") or ""
            if not isinstance(r_name, str) or not r_name.strip():
                continue

            score = jws(c_name, r_name)
            if score > best_score:
                best_score = score
                best_i = i

        # Assign if above threshold
        if best_i is not None and best_score >= threshold:
            congresista["voto"] = sorted_attendance[best_i].get("voto")
            used.add(best_i)
        else:
            congresista["voto"] = None

    return sorted_congres