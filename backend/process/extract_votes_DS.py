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

# OJO: LP/LE/LO son votos posibles en tu data
VOTE_RE = r"(?:SI|NO|ABST\.?|LE|LP|LO|AUS|SINRES|SUS|\*\*\*)"

TRIPLE_RE = re.compile(
    rf"""
    \|\s*(?P<bancada>{BANCADA_RE})\s*\|      # | BANCADA |
    \s*(?P<name>{NAME_RE})\s*\|              # NAME |
    \s*(?P<vote>{VOTE_RE})                   # VOTE
    """,
    re.VERBOSE
)

VOTE_CANON = {
    "SI":"SI","NO":"NO","LE":"LE","LP":"LP","LO":"LO",
    "AUS":"AUS","SINRES":"SINRES","SUS":"SUS","***":"***",
    "ABST":"ABST","ABST.":"ABST",
}







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
        return (day, month, year)
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
    for m in TRIPLE_RE.finditer(lines):
        vote_raw = m.group("vote").strip().upper()
        vote = VOTE_CANON.get(vote_raw, vote_raw)

        rec = {
            "bancada": m.group("bancada").strip(),
            "nombre_completo": m.group("name").strip(),
            "voto": vote,
        }

        resultados.append(rec)


    return {
        "resultados": resultados,
        "stats": {"records_out": len(resultados)}
    }