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
    parse_vote_table
)

say_hello()

texto_path=DATA_DIR/"L31751_page_2.txt"
texto=read_txt(texto_path)

texto_normalized=normalize_text(texto)

type_text=get_type(texto_normalized)

blocks=locate_blocks(texto_normalized, type_text)

fecha=get_fecha(blocks["header_block"])

titulo=get_title(blocks["header_block"])

table=parse_vote_table(blocks["table_block"])

print(table)
print(len(table["resultados"]))