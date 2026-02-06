from pathlib import Path
import sys
import fitz
import json
from pathlib import Path

# Ensure project root is on sys.path so imports like `backend.process` work when
# running this file directly (e.g., `uv run backend/process/trials.py`).
ROOT_DIR = Path(__file__).resolve().parents[2]

#the important comment
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.process.extract_votes import (
    render_bill,
    extract_information,
    count_votes,
    matching_lists,
    extraction_first_second,
    format_jsn,
    no_comma_readed,
    run_exceptions,
    matching_last_name,
    extract_congressmen,
    swap_names, 
    normalize_votes_in_place,
    normalize_text,
    text_below_to_dict,
    look_for_absent_brother
)

DATA_DIR = ROOT_DIR / "data"
PDF_NAME = "Asis_y_vot_de_la_sesión_del_13-12-2024.pdf"
pdf_path=DATA_DIR / PDF_NAME

bill=render_bill(pdf_path)
votes=extract_information(bill[1], False)["resultados"]

#Reading congresistas_2016_2021.json:



DATA_DIR = Path(__file__).resolve().parents[2] / "data"
json_path = DATA_DIR / "congresistas_2016_2021.json"

#print(json_path)
with json_path.open(encoding="utf-8-sig") as f:
    congresistas_raw = json.load(f)  


#print(congresistas)

vote_dic=extraction_first_second(votes)

congresistas=format_jsn(congresistas_raw)

#for congresista in congresistas:
#    congresista["nombre_completo"]=congresista["nombre"]+ " "+ congresista["apellido"]

vote_list=no_comma_readed(vote_dic)
vote_list=run_exceptions(vote_list)

#print(vote_list)



matched_votes=matching_lists(congresistas, vote_list)
matched_votes2=matching_last_name(matched_votes, vote_list)


congresistas_swaped=swap_names(matched_votes2)

matched_votes3=matching_lists(congresistas_swaped, vote_list)

matched_votes3=swap_names(matched_votes3)
#congresistas=last_name_swap(congresistas)
#matched_votes=matching_lists(congresistas,vote_list)


#congresistas_added=extract_congressmen(bill[1])

#print(count_votes(vote_list, "estado"))

lst_below=text_below_to_dict(extract_congressmen(bill[1]))

exception_lst_below=run_exceptions(lst_below)

normalized_votes=[]
for congresista in matched_votes3:
    if congresista["condicion"]=="en Ejercicio":
        normalized_votes.append(congresista)



normalized_votes= normalize_votes_in_place(normalized_votes)

for vote in normalized_votes:
    vote["nombre_completo"]=normalize_text(vote["nombre_completo"])
    vote["nombre"]=normalize_text(vote["nombre"])
    vote["apellido"]=normalize_text(vote["apellido"])
    vote["bancada"]=normalize_text(vote["bancada"])






output_path = DATA_DIR / "seats.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(final_votes, f, ensure_ascii=False, indent=2)


print(count_votes(final_votes, "votacion"))

