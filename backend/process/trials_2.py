from pathlib import Path
import sys
import json

# Ensure project root is on sys.path so imports like `backend.process` work when
# running this file directly (e.g., `uv run backend/process/trials.py`).
ROOT_DIR = Path(__file__).resolve().parents[2]

#the important comment
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.process.extract_votes import (
    render_bill,
    transformation_final
)

DATA_DIR = ROOT_DIR / "data/to_test_function"
#PDF_NAME = "Asis_y_vot_de_la_sesión_del_13-12-2024.pdf"
PDF_NAME = "L31989.pdf"

pdf_path=DATA_DIR / PDF_NAME

votes=render_bill(pdf_path,1)


#print(votes)


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
json_path = DATA_DIR / "congresistas_2021_2026.json"

#print(json_path)
with json_path.open(encoding="utf-8-sig") as f:
    congresistas_raw = json.load(f)  



final_votes=transformation_final(votes, congresistas_raw )

output_path = DATA_DIR / "seats.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(final_votes, f, ensure_ascii=False, indent=2)


#print(count_votes(final_votes["resultados"], "votacion"))
#print(final_votes["resultados"])

#print(final_votes["fecha"])
#print(normalize_text(votes))
