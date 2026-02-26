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
    matching_lists,
    transformation_final
)

say_hello()
####################################################################
#Parsing the OCR
texto_path=DATA_DIR/"L31989.txt"

texto=read_txt(texto_path)
# Formatting the base of congresistas
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
json_path = DATA_DIR / "congresistas_2021_2026.json"
#print(json_path)
with json_path.open(encoding="utf-8-sig") as f:
    congresistas_raw = json.load(f)  

final_results=transformation_final(texto, congresistas_raw)

print(final_results)