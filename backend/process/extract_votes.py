# -*- coding: utf-8 -*-

from io import BytesIO
import re
import unicodedata

import fitz
from PIL import Image
import numpy as np
import cv2
import pytesseract
from jellyfish import jaro_winkler_similarity as jws

pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

# --- Shared patterns ---
UPPER_SPANISH = r"A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1"
BANCADA_REGEX = rf"([{UPPER_SPANISH}]{{2,5}}(?:-[{UPPER_SPANISH}]{{2,5}})?)"
NOMBRE_REGEX = rf"([{UPPER_SPANISH} ,.'-]+?)"

ATTENDANCE_STATE_REGEX = rf"(?<![{UPPER_SPANISH}])\s*(AUS|PRE|LE|LO|LP)\s*(?![{UPPER_SPANISH}])"

SI_REGEX = (
    rf"(?<![{UPPER_SPANISH}])[S5][I\u00cd](?:\s+[\+\d]{{0,4}})?(?:\s+|$)(?![{UPPER_SPANISH}])"
    rf"|S\s+\+{{1,4}}(?:\s+|$)"
    rf"|S\d\s+\+{{1,4}}(?:\s+|$)"
    rf"|\"?\$1\"?(?:\s+|$)"
)


NO_REGEX = rf"(?<![{UPPER_SPANISH}])N[O\u00d3](?:\s+[-=\d]{{0,4}})?(?:\s+|$)(?![{UPPER_SPANISH}])"
AUS_REGEX = r"(?:AUS|AIS|US)"
ABST_REGEX = r"(?:ABST\.)"
ASIS_REGEX = r"(?:PRE)"
OTHER_REGEX = rf"(?<![{UPPER_SPANISH}])(?:LE|LO|LP|SINRES|SINRRES|TT|TTT)(?![{UPPER_SPANISH}])"
STAR_REGEX = r"(?:\*{1,4})"

VOTE_STATE_REGEX = rf"(?:{SI_REGEX}|{NO_REGEX}|{AUS_REGEX}|{ABST_REGEX}|{OTHER_REGEX}|{STAR_REGEX})"

# Compiled patterns for estado categorization
SI_PATTERN = re.compile(rf"^(?:{SI_REGEX})$", re.IGNORECASE)
NO_PATTERN = re.compile(rf"^(?:{NO_REGEX})$", re.IGNORECASE)
ABST_PATTERN = re.compile(rf"^(?:{ABST_REGEX})$", re.IGNORECASE)
AUS_PATTERN = re.compile(rf"^(?:{AUS_REGEX})$", re.IGNORECASE)
ASIS_PATTERN = re.compile(rf"^(?:{ASIS_REGEX})$", re.IGNORECASE)
OTHER_PATTERN = re.compile(rf"^(?:{OTHER_REGEX})$", re.IGNORECASE)
STAR_PATTERN = re.compile(rf"^(?:{STAR_REGEX})$")

def extract_text_from_page(page):
    """
    Extract text from a single PDF page using Tesseract OCR.
    Args:
        page: PyMuPDF page object (e.g., doc[0]).
    Returns:
        str: Extracted text from the page.
    """
    pix = page.get_pixmap(dpi=300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    pil_img = Image.fromarray(thresh)
    text = pytesseract.image_to_string(pil_img, lang="spa", config="--psm 6")
    return text

# If there are more pages we have to find the page with the votes.

def render_bill(pdf_path: str, page=0):
    """
    Extract text from a PDF file of a BILL using PyMuPDF and Tesseract OCR.
    Args:
        pdf_url (str): URL of the PDF file to be processed.
        Note: Should consider using a pdf object as an argument instead of a URL. TO DISCUSS

    Returns:
        tuple: A tuple containing the attendance text and the votes text.

    Assume that in the PDF the first two pages are:
    - The first page contains the attendance information.
    - The second page contains the votes information. (third)
    If the PDF has a different structure, this function may need to be adjusted.
    """
    with open(pdf_path, "rb") as f:
        pdf_file = BytesIO(f.read())

    with fitz.open(stream=pdf_file, filetype="pdf") as pdf:
        
        content = pdf[page]
        text = extract_text_from_page(content)

    return text

def extract_information(text: str, is_attendance=True) -> dict:
    """Extracts attendance and votes from a bill voting."""
    
    hora_match = re.search(r'[Hh]ora[:\s]*([\d:\samp]+)', text)
    #titulo_match = re.search(
    #    r"(?is)\bAsunto\b\s*:?(?:\s*\r?\n)?\s*([^\r\n]+)",
    #    text
    #)
    
    fecha_match = re.search(r'[Ff]echa[:\s]*([\d/]+)', text, re.IGNORECASE)

    if not fecha_match:
        fecha_match = re.search(r'[Ee]ccha[:\s]*([\d/]+)', text, re.IGNORECASE)


    fecha = fecha_match.group(1) if fecha_match else "Not found"

    hora = hora_match.group(1) if hora_match else "No found"
    #titulo = titulo_match.group(1).strip() if titulo_match else "No found"
    if is_attendance is True:
        # Attendance
        estado_pattern = rf"({ATTENDANCE_STATE_REGEX})"
        # Regex
        fila_pattern = re.compile(
            rf"{BANCADA_REGEX}\s+{NOMBRE_REGEX}\s+{estado_pattern}",
            re.IGNORECASE
        )

    else:
        estado = rf"({VOTE_STATE_REGEX})"

        fila_pattern = re.compile(
            rf"{BANCADA_REGEX}\s+{NOMBRE_REGEX}\s+{estado}",
            re.IGNORECASE
        )
    resultados = []

    # For lines
    for line in text.splitlines():
        line = line.replace("5", "S").replace("0", "O")
        line_upper = line.upper()

        matches = fila_pattern.findall(line_upper)
    
        # For every match
        for bancada, nombre, estado in matches:
            resultados.append({
                "bancada": bancada.strip().upper(),
                "nombre": nombre.strip().title(),
                "estado": estado.upper()
            })


    titulo=get_title(text)
    # Final Result
    return {
        "fecha": fecha,
        "hora": hora,
        "titulo": titulo,
        "resultados": resultados,
    }

def extract_afavor(text: str) -> list[str]:
    """
    Extracts congressmen names from attendance/vote records,
    handling multiline text and final 'y Name' cases.
    """
    text = normalize_text(text)

    pattern = (
        #r"deja constancia de la (?:asistencia| voto a favor) de los\s+congresistas\s+"
        r"deja constancia del voto a favor de los\s+congresistas\s+"
        r"(.+?)\."
    )

    match = re.search(pattern, text, flags=re.IGNORECASE)

    if not match:
        return []

    names_block = match.group(1)
    # Stop if another vote clause appears after this block
    names_block = re.split(r"\sVOT(?:O)?\s", names_block, maxsplit=1, flags=re.IGNORECASE)[0]

    # Replace " y " with comma for consistent splitting
    names_block = re.sub(r"\s+y\s+", ", ", names_block, flags=re.IGNORECASE)

    # Split and clean
    names = [
        name.strip()
        for name in names_block.split(",")
        if name.strip()
    ]

    return names

def extract_encontra(text: str) -> list[str]:
    """
    Extracts congressmen names from 'voto en contra' records,
    handling multiline text and final 'y Name' cases.
    """
    text = normalize_text(text)

    pattern = (
        r"vot(?:o)?\s+en\s+contra\s+de\s+los\s+congresistas\s+"
        r"(.+?)\."
    )

    match = re.search(pattern, text, flags=re.IGNORECASE)

    if not match:
        return []

    names_block = match.group(1)
    # Stop if another vote clause appears after this block
    names_block = re.split(r"\sVOT(?:O)?\s", names_block, maxsplit=1, flags=re.IGNORECASE)[0]

    # Replace " y " with comma for consistent splitting
    names_block = re.sub(r"\s+y\s+", ", ", names_block, flags=re.IGNORECASE)

    # Split and clean
    names = [
        name.strip()
        for name in names_block.split(",")
        if name.strip()
    ]

    return names

def extract_enabstencion(text: str) -> list[str]:
    """
    Extracts congressmen names from 'voto en abstencion' records,
    handling multiline text and final 'y Name' cases.
    """
    text = normalize_text(text)

    pattern = (
        r"vot(?:o)?\s+en\s+abstencion\s+de\s+los\s+congresistas\s+"
        r"(.+?)\."
    )

    match = re.search(pattern, text, flags=re.IGNORECASE)

    if not match:
        return []

    names_block = match.group(1)
    # Stop if another vote clause appears after this block
    names_block = re.split(r"\sVOT(?:O)?\s", names_block, maxsplit=1, flags=re.IGNORECASE)[0]

    # Replace " y " with comma for consistent splitting
    names_block = re.sub(r"\s+y\s+", ", ", names_block, flags=re.IGNORECASE)

    # Split and clean
    names = [
        name.strip()
        for name in names_block.split(",")
        if name.strip()
    ]

    return names

def text_below_to_dict(lst: list) -> list:
    lst_final = []
    for congressman in lst:
        lst_final.append({
            "apellido": congressman,
            "nombre_completo": congressman,
            "estado": "SI"
        })

    return lst_final

def run_exceptions(lst_attendance):
    for x in lst_attendance:
        if "apellido" in x:
            if x["apellido"] == "Echaíz De Núñez Izaga":
                x["apellido"] = "Echaíz Ramos vda de Núñez"

            if x["nombre_completo"] == "HECTOR ACUNA PERALTA":
                x["nombre_completo"] = "SEGUNDO HECTOR ACUNA PERALTA"

    return lst_attendance

def swap_names(lst_congress):
    lst_2 = lst_congress.copy()
    for congresista in lst_2:
        if congresista["nombre_completo"] == congresista["nombre"] + " " + congresista["apellido"]:
            congresista["nombre_completo"] = congresista["apellido"] + " " + congresista["nombre"]
        elif congresista["nombre_completo"] == congresista["apellido"] + " " + congresista["nombre"]:
            congresista["nombre_completo"] = congresista["nombre"] + " " + congresista["apellido"]

    return lst_2

def no_comma_readed(lst_attendance):
    result = []

    for x in lst_attendance:
        x2 = x.copy()
        if "nombre" in x2 and "apellido" not in x2:
            x2["nombre_completo"] = x2["nombre"]
        result.append(x2)

    return result

def extraction_first_second(congresistas):
    result = []

    for c in congresistas:
        c_new = c.copy()  # copy each dict

        nombre = c_new.get("nombre")
        if isinstance(nombre, str) and "," in nombre:
            last_name, first_name = nombre.split(",", 1)
            first_name = first_name.strip()
            last_name = last_name.strip()

            c_new["nombre"] = first_name
            c_new["apellido"] = last_name
            c_new["nombre_completo"] = f"{first_name} {last_name}"

        result.append(c_new)

    return result

def matching_lists(lst_congres, lst_attendance, threshold=0.90):
    """
    Match congresistas to attendance/vote rows using Jaro-Winkler similarity
    on nombre_completo. Enforces one-to-one matching (no reuse) and picks the
    best match (highest score), not the first match.
    """

    # Ensure every attendance row has nombre_completo
    att = []
    for x in lst_attendance:
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
        if congresista.get("votacion") is not None:
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
            congresista["votacion"] = sorted_attendance[best_i].get("estado")
            used.add(best_i)
        else:
            congresista["votacion"] = None

    return sorted_congres

def matching_last_name(lst_congres, lst_attendance, text_below=False):
    att = []

    for x in lst_attendance:
        x2 = x.copy()
        if "apellido" not in x2:
            x2["apellido"] = "NO_NAME"
        x2["apellido"] = normalize_text(x2["apellido"])
        att.append(x2)

    sorted_congres = sorted(lst_congres, key=lambda x: x["apellido"])
    sorted_attendance = sorted(att, key=lambda x: x["apellido"])

    for congresista in sorted_congres:
        c_apellido = normalize_text(congresista.get("apellido", ""))
        if text_below is False:
            if congresista["votacion"] is None:
                # Solo para los que aun no ha hecho match
                # Que pasa si los hermanos aun no han hecho match?
                counter = 0
                while (
                    counter < len(sorted_attendance)
                    and jws(c_apellido, sorted_attendance[counter]["apellido"]) < 0.950
                ):
                    counter += 1

                if counter < len(sorted_attendance):
                    congresista["votacion"] = sorted_attendance[counter]["estado"]
                else:
                    congresista["votacion"] = None  # no match found

        if text_below is True:
            counter = 0
            while (
                counter < len(sorted_attendance)
                and jws(c_apellido, sorted_attendance[counter]["apellido"]) < 0.950
            ):
                counter += 1

            if counter < len(sorted_attendance):
                congresista["votacion"] = sorted_attendance[counter]["estado"]

    return sorted_congres

###### AUXILIAR FUNCTIONS FOR TESTING PURPOSES ######

def count_votes(lst, key):
    """
    Counts the votes from the extracted text.
    Args:
        dict (dict): The dictionary containing the attendance and votes information.
    Returns:
        dict: A dictionary with the counts of each vote option.
    """
    conteo = {}

    for fila in lst:
        estado = fila.get(key)

        estado = estado.strip() if isinstance(estado, str) else "SIN_VOTO"

        conteo[estado] = conteo.get(estado, 0) + 1

    return conteo

def format_jsn(congresistas):
    list_congreso = []
    for item in congresistas:
        dict_congresista = {}
        dict_congresista["id"] = item["id"]
        dict_congresista["nombre"] = item["nombre"]
        dict_congresista["apellido"] = item["apellido"]
        dict_congresista["nombre_completo"] = item["nombre"] + " " + item["apellido"]
        dict_congresista["partido"] = item["party_name"]
        dict_congresista["bancada"] = item["bancada"]
        dict_congresista["en_ejercicio"] = item["en_ejercicio"]
        dict_congresista["votacion"] = None
        dict_congresista["periodo"]= item["periodo"]

        list_congreso.append(dict_congresista)

    return list_congreso

#############################

def _parse_fecha(fecha: str):
    if not isinstance(fecha, str):
        return None
    try:
        day, month, year = [int(x) for x in fecha.split("/")]
        return (year, month, day)
    except Exception:
        return None


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


def define_bancada(congresistas_raw, fecha):
    """"
    congresistas_raw: producto of a json.load(f)
    fecha: a fecha in format dd/mm/year

    """
    # If fecha is between inicio and fin in "bancada.periodo",
    # set "bancada" to the bancada name for that period.
    if not fecha:
        return congresistas_raw

    target = _parse_fecha(fecha)
    if not target:
        return congresistas_raw

    for c in congresistas_raw:
        bancada = c.get("bancada")

        # Bancada can be a dict (single) or list (many)
        if isinstance(bancada, dict):
            if _period_contains(bancada.get("periodo"), target):
                c["bancada"] = bancada.get("name")
            else:
                c["bancada"] = None
            continue

        if isinstance(bancada, list):
            found = None
            for item in bancada:
                if not isinstance(item, dict):
                    continue
                if _period_contains(item.get("periodo"), target):
                    found = item.get("name")
                    break
            c["bancada"] = found
            continue

        # Unknown/empty types -> set to None
        c["bancada"] = None

    return congresistas_raw







def categorize_estado(estado: str) -> str:
    """
    Map raw OCR estado strings (e.g., 'SI +++', 'NO ---', 'ABST.', 'AUS', '*')
    into: SI, NO, ABST, AUS, OTROS
    """
    if not isinstance(estado, str):
        return "OTROS"

    e = estado.strip().upper()
    e = re.sub(r"\s+", " ", e)  # normalize spaces

    # SI / NO
    if SI_PATTERN.match(e):
        return "SI" 

    if NO_PATTERN.match(e):
        return "NO" 

    # ABST
    if ABST_PATTERN.match(e):
        return "ABST"

    # AUS (or US)
    if AUS_PATTERN.match(e):
        return "AUS"

    # Other isolated tokens or stars -> OTROS
    if OTHER_PATTERN.match(e) or STAR_PATTERN.match(e):
        return "OTROS"
    
    return "OTROS"

def normalize_votes_in_place(congresistas: list[dict], key: str = "votacion"):
    """
    Replace raw vote strings (e.g. 'SI +++', 'NO ---') with
    normalized categories: SI, NO, ABST, AUS, OTROS.

    Modifies the list IN PLACE and also returns it.
    """
    for c in congresistas:
        raw = c.get(key)

        if raw is None:
            c[key] = None
        else:
            c[key] = categorize_estado(raw)

    return congresistas

def normalize_text(s: str) -> str:
    if not s:
        return ""

    s = s.upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)

    return s.strip()

def look_for_absent_brother(lst_congress, lst_text_below):
    for brother in lst_text_below:
        for congressman in lst_congress:
            if congressman["votacion"] == "AUS":
                if brother["nombre_completo"] == congressman["nombre_completo"]:
                    congressman["votacion"] = None

    return lst_congress


def get_title(text):
    texto_normalized = normalize_text(text)
    start = texto_normalized.find("ASUNTO:")
    if start == -1:
        return ""
    start += len("ASUNTO:")
    end = texto_normalized.find("APP", start)
    if end == -1:
        end = len(texto_normalized)
    return texto_normalized[start:end].strip()

def get_type(text):
    texto_normalized = normalize_text(text)

    if re.search(r"\bVOTACI[OÓ]N:\s*(?:—|-)?\s*FECHA:?\b", texto_normalized, re.IGNORECASE):
        return "VOTACION"

    if re.search(r"\bVOTACI[OÓ]N:\s*(?:—|-)?\s*ECCHA:?\b", texto_normalized, re.IGNORECASE):
        return "VOTACION"

    elif re.search(r"\bASISTENCIA:\s*(?:—|-)?\s+[FE]CHA\b", texto_normalized):
        return "ASISTENCIA"

    return None


def define_enejercicio(congresistas_raw, fecha):
    """"
    congresistas_raw: producto of a json.load(f)  
    fecha: a fecha in format dd/mm/year

    """
    # If fecha is between inicio and fin in "periodo" for each congresista,
    # set "en_ejercicio"=True, else set it to False.
    if not fecha:
        return congresistas_raw

    try:
        day, month, year = [int(x) for x in fecha.split("/")]
        target = (year, month, day)
    except Exception:
        return congresistas_raw

    for c in congresistas_raw:
        periodo = c.get("periodo", {})
        inicio = periodo.get("inicio")
        fin = periodo.get("fin")

        if not (isinstance(inicio, str) and isinstance(fin, str)):
            # Keep existing value if we can't parse periodo
            continue

        try:
            d_i, m_i, y_i = [int(x) for x in inicio.split("/")]
            d_f, m_f, y_f = [int(x) for x in fin.split("/")]
            start = (y_i, m_i, d_i)
            end = (y_f, m_f, d_f)
        except Exception:
            continue

        c["en_ejercicio"] = start <= target <= end

    return congresistas_raw

def transformation_final(text, congresistas_jsn):

    #Create the dictionary for the json
    dictionary_final={}


    # Formatting the votation
    evento=get_type(text)
    if evento=="VOTACION":
        bill= extract_information(text, False)
    elif evento=="ASISTENCIA":
        bill= extract_information(text, True)

    else:
         raise ValueError("No se identifica asistencia o votación")

    step_a=bill["resultados"]
    step_b = extraction_first_second(step_a)
    step_c = no_comma_readed(step_b)
    step_d = run_exceptions(step_c)

    # Formatting the base of congresistas
    fecha=bill["fecha"]
    congresistas = format_jsn(congresistas_jsn)
    congresistas=define_enejercicio(congresistas, fecha)
    congresistas=define_bancada(congresistas, fecha)

    
    # First matching between lists
    step_e = matching_lists(congresistas, step_d)
    

    step_f = matching_last_name(step_e, step_d)

    # match when there is no comma
    step_g = swap_names(step_f)
    step_h = matching_lists(step_g, step_d)
    step_i = swap_names(step_h)

    # Adding the congressmen at the base (favor + contra + abstencion)
    below_names = (
        extract_afavor(text)
        + extract_encontra(text)
        + extract_enabstencion(text)
    )
    below = text_below_to_dict(below_names)
    below_brothers = run_exceptions(below)


    # Formatting the matching (normalize)
    step_j = []
    for congresista in step_i:
        if congresista["en_ejercicio"] == True:
            step_j.append(congresista)
    
    step_j = normalize_votes_in_place(step_j)

    for vote in step_j:
        vote["nombre_completo"] = normalize_text(vote["nombre_completo"])
        vote["nombre"] = normalize_text(vote["nombre"])
        vote["apellido"] = normalize_text(vote["apellido"])

    # second round of match (with the one below):
    step_k = matching_last_name(step_j, below, True)

    # we eliminate the absence for the brother in the below
    step_l = look_for_absent_brother(step_k, below_brothers)

    
    final_votes = matching_lists(step_l, below_brothers)
    titulo=bill["titulo"]
    
    #breakpoint()
    

    dictionary_final["titulo"]=titulo
    dictionary_final["evento"]=evento
    dictionary_final["fecha"]=fecha
    dictionary_final["resultados"]=final_votes
    
    
    return dictionary_final



