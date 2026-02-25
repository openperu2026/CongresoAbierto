from pathlib import Path
import sys
import fitz
import json
from pathlib import Path

# Ensure project root is on sys.path so imports like `backend.process` work when
# running this file directly (e.g., `uv run backend/process/trials.py`).
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR=ROOT_DIR /"data/extracted_text"

#the important comment
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.process.extract_votes_DS import (
    say_hello,
    read_txt,
    normalize_text,
    get_type,
    locate_blocks,
    get_fecha,
    get_title,
    parse_vote_table,
    find_below_block,
    clean_vote_block,
    _split_nombres,
    extract_constancias,
    extraction_first_second,
    format_jsn,
    define_enejercicio,
    define_bancada,
    matching_lists
)

say_hello()
####################################################################
#Parsing the OCR
texto_path=DATA_DIR/"L31751_page_2.txt"
texto=read_txt(texto_path)
texto_normalized=normalize_text(texto)
type_text=get_type(texto_normalized)
blocks=locate_blocks(texto_normalized, type_text)
fecha=get_fecha(blocks["header_block"])
titulo=get_title(blocks["header_block"])
table=parse_vote_table(blocks["table_block"])

####RESULTADOS PARA COMAPRAR
results_formated=extraction_first_second(table["resultados"])

#print(results_formated)
#####LISTA DE EXCEPCIONES DEBAJO
below_block=clean_vote_block(find_below_block(blocks["table_block"]))
list_below=extract_constancias(below_block)

####################################################################
# Formatting the base of congresistas
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
json_path = DATA_DIR / "congresistas_2021_2026.json"
#print(json_path)
with json_path.open(encoding="utf-8-sig") as f:
    congresistas_raw = json.load(f)  
    
congresistas = format_jsn(congresistas_raw)
congresistas=define_enejercicio(congresistas, fecha)
congresistas=define_bancada(congresistas, fecha)

####################################################################
#MAKING THE MATCHES

first_match=matching_lists(congresistas, results_formated)





####For couting

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


print(count_votes(first_match, "voto"))