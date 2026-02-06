# -*- coding: utf-8 -*-

from .schema import Vote
from .schema import VoteEvent
import pytesseract
import os
import fitz
from io import BytesIO
import httpx
from PIL import Image
import numpy as np
import cv2
from jellyfish import jaro_winkler_similarity as jws
from .. import PARTIES #VOTE_RESULTS VOTE RESULTS IS NOT IN THE MAIN
import re
import pytesseract
from pathlib import Path
import json

from datetime import datetime
import unicodedata
import re


pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"



def extract_text_from_page(page):
    '''
    Extract text from a single PDF page using Tesseract OCR.
    Args:
        page: page of aA PyMuPDF page object. For example if PyMuPDF is doc. The page will be doc[0]
    Returns:
        str: Extracted text from the page.
     '''
    pix = page.get_pixmap(dpi = 300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    pil_img = Image.fromarray(thresh)
    text = pytesseract.image_to_string(pil_img, lang = 'spa', config='--psm 6')
    print('hello there')
    return text

#If there is more pages we have to find the page with the votes.


def render_bill(pdf_path: str):
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
        attendance_page = pdf[0]
        votes_page = pdf[2]
        attendance_text = extract_text_from_page(attendance_page)
        votes_text = extract_text_from_page(votes_page)

    return attendance_text, votes_text

def extract_information(text: str, type=True) -> dict:
    """Extracts attendance and botes from a bill voting."""


    fecha_match = re.search(r'[Ff]echa[:\s]*([\d/]+)', text)
    hora_match = re.search(r'[Hh]ora[:\s]*([\d:\samp]+)', text)

    fecha = fecha_match.group(1) if fecha_match else "No found"
    hora = hora_match.group(1) if hora_match else "No found"

    if type==True:
        #Attendance
        estado_pattern = r"(?<![A-ZÁÉÍÓÚÑ])\s*(AUS|PRE|LE|LO|LP)\s*(?![A-ZÁÉÍÓÚÑ])"
         # Regex
        fila_pattern = re.compile(
            rf"([A-ZÁÉÍÓÚÑ]{{2,5}})\s+([A-ZÁÉÍÓÚÑ ,.'-]+?)\s+{estado_pattern}",
            re.IGNORECASE
        )

    else:
        bancada = r"([A-ZÁÉÍÓÚÑ]{2,5})"
        nombre  = r"([A-ZÁÉÍÓÚÑ ,.'-]+?)"
        si_no_pattern = r"(?:S[IÍ]\s*[\+\d]{1,4}|N[OÓ]\s*[-=\d]{1,4})"
        isolated =  r"(?<![A-ZÁÉÍÓÚÑ])(?:AUS|US|PRE|LE|LO|LP|ABST\.|SINRES|SINRRES|TT|TTT)(?![A-ZÁÉÍÓÚÑ])"
        star_pattern = r"(?:\*{1,4})"
        estado = rf"({si_no_pattern}|{isolated}|{star_pattern})"

        fila_pattern = re.compile(
            rf"{bancada}\s+{nombre}\s+{estado}",
            re.IGNORECASE
        )

    resultados = []

    # For Lines
    for line in text.splitlines():
        line = line.replace("5", "S").replace("0", "O")
        line_upper = line.upper()

        matches = fila_pattern.findall(line_upper)
    
        # For everymatch
        for bancada, nombre, estado in matches:
            resultados.append({
                "bancada": bancada.strip().upper(),
                "nombre": nombre.strip().title(),
                "estado": estado.upper()
            })

    #Final Result
    return {
        "fecha": fecha,
        "hora": hora,
        "resultados": resultados

 
    }



def extract_congressmen(text: str) -> list[str]:
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

    # Replace " y " with comma for consistent splitting
    names_block = re.sub(r"\s+y\s+", ", ", names_block, flags=re.IGNORECASE)

    # Split and clean
    names = [
        name.strip()
        for name in names_block.split(",")
        if name.strip()
    ]

    return names


def text_below_to_dict(lst:list)->list:
    lst_final=[]
    for congressman in lst:
        dict_congress={}
        dict_congress["apellido"]=congressman
        dict_congress["nombre_completo"]=congressman
        dict_congress["estado"]="SI"
        lst_final.append(dict_congress) 

    return lst_final



def run_exceptions(lst_attendance):
    for x in lst_attendance:
        if "apellido" in x:
            if x["apellido"]=="Echaíz De Núñez Izaga":
                print("there is exceptions")
                x["apellido"]="Echaíz Ramos vda de Núñez"

            if x["nombre_completo"]=="HECTOR ACUNA PERALTA":
                print("there is exceptions")
                x["nombre_completo"]="SEGUNDO HECTOR ACUNA PERALTA"

    return lst_attendance


def swap_names(lst_congress):
    
    lst_2=lst_congress.copy()
    for congresista in lst_2:
        if congresista["nombre_completo"]==congresista["nombre"]+ " "+ congresista["apellido"]:   
            #print("from first-last to last-first")
            congresista["nombre_completo"]=congresista["apellido"]+ " "+ congresista["nombre"]
        elif congresista["nombre_completo"]==congresista["apellido"]+ " "+ congresista["nombre"]:
            #print("from last-dirst to first-last")
            congresista["nombre_completo"]=congresista["nombre"]+ " "+ congresista["apellido"]
        else:
            print("no swap to perform")
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
            att.append(x2)
        else:
            att.append(x2)
    
    
    
    sorted_congres = sorted(lst_congres, key=lambda x: x["apellido"])
    sorted_attendance = sorted(att, key=lambda x: x["apellido"])
    
      

    for congresista in sorted_congres:
        if text_below==False:
            if congresista["votacion"] == None:
                ###Solo para los que aun no ha hecho match
                ###Que pasa si los hermanos aun no han hecho match?
                
                counter = 0
                while (
                    counter < len(sorted_attendance)
                    and jws(congresista["apellido"], sorted_attendance[counter]["apellido"]) < 0.950
                ):
                    counter += 1

                if counter < len(sorted_attendance):
                    congresista["votacion"] = sorted_attendance[counter]["estado"]
                else:
                    congresista["votacion"] = None  # no match found

        if text_below==True:
                counter = 0
                while (
                    counter < len(sorted_attendance)
                    and jws(congresista["apellido"], sorted_attendance[counter]["apellido"]) < 0.950
                ):
                    counter += 1

                if counter < len(sorted_attendance):
                    congresista["votacion"] = sorted_attendance[counter]["estado"]

    return sorted_congres


######AUXILIAR FUNCTIONS FOR TESTING PURPOSES#####

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
    #base = Path(base_dir) if base_dir else (Path(__file__).parent if "__file__" in globals() else Path.cwd())
    #data_path = base / "data" / "congresistas.json"

    #with data_path.open(encoding="utf-8") as f:
    #   congresistas = json.load(f)
    #print(f"Loaded {len(congresistas)} congresistas")

    list_congreso=[]
    #for dict in congresistas["Parlamentario 2021 - 2026"]:
    for dict in congresistas:
        dict_congresista={}
        dict_congresista["id"]=dict["id"]
        dict_congresista["nombre"]=dict["nombre"]
        dict_congresista["apellido"]=dict["apellido"]
        dict_congresista["nombre_completo"]=dict["nombre"] + " " + dict["apellido"]
        dict_congresista["partido"] = dict["party_name"]
        dict_congresista["bancada"]= dict["bancada_name"]
        dict_congresista["condicion"]= dict["condicion"]
        dict_congresista["votacion"]= None

        list_congreso.append(dict_congresista)
    
    return list_congreso



#############################

import re
from collections import Counter

# --- Patterns (based on yours) ---
SI_NO_PATTERN = re.compile(r"^(?:S[IÍ]\s*[\+\d]{0,4}|N[OÓ]\s*[-=\d]{0,4})$", re.IGNORECASE)

ABST_PATTERN = re.compile(r"^ABST\.?$", re.IGNORECASE)

AUS_PATTERN = re.compile(r"^(?:AUS|US)$", re.IGNORECASE)

# Everything else you listed as "isolated" that isn't SI/NO/ABST/AUS.
OTHER_ISOLATED_PATTERN = re.compile(
    r"^(?:PRE|LE|LO|LP|SINRES|SINRRES|TT|TTT)$",
    re.IGNORECASE
)

STAR_PATTERN = re.compile(r"^\*{1,4}$")


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
    if SI_NO_PATTERN.match(e):
        return "SI" if e.startswith("SI") or e.startswith("SÍ") else "NO"

    # ABST
    if ABST_PATTERN.match(e):
        return "ABST"

    # AUS (or US)
    if AUS_PATTERN.match(e):
        return "AUS"

    # Other isolated tokens or stars -> OTROS
    if OTHER_ISOLATED_PATTERN.match(e) or STAR_PATTERN.match(e):
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
            if congressman["votacion"]=="AUS" :
                if brother["nombre_completo"]==congressman["nombre_completo"]:
                    congressman["votacion"]=None
    
    return lst_congress


def transformation_final(votacion, congresistas_jsn):
    # Formating the votation
    a=extract_information(votacion, False)["resultados"]
    b=extraction_first_second(a)
    c=no_comma_readed(b)
    d=run_exceptions(c)

    #Formating the base of congresistas
    congresistas=format_jsn(congresistas_jsn)

    #First matching between lists
    e=matching_lists(congresistas,d)
    f=matching_last_name(e,d)

    #match when there is no comma
    g=swap_names(f)
    h=matching_lists(g, d)
    i=swap_names(h)


    #Adding the congressmen at the base
    below=text_below_to_dict(extract_congressmen(votacion))
    below_brothers=run_exceptions(below)

    #Formating the matchin (normalize)
    j=[]
    for congresista in i:
        if congresista["condicion"]=="en Ejercicio":
            j.append(congresista)

    j= normalize_votes_in_place(j)

    for vote in j:
        vote["nombre_completo"]=normalize_text(vote["nombre_completo"])
        vote["nombre"]=normalize_text(vote["nombre"])
        vote["apellido"]=normalize_text(vote["apellido"])
        vote["bancada"]=normalize_text(vote["bancada"])
    
    #second round of match (with the one below):
    k=matching_last_name(j,below, True)

    # we eliminate the absense for the brother in the below
    l=look_for_absent_brother(k, below_brothers)


    final_votes=matching_lists(l, below_brothers)

    return final_votes

