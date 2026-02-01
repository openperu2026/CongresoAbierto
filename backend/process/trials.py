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
    extract_text_from_page,
    render_bill,
    extract_information,
    count_votes,
    matching_lists,
    extraction_first_second,
    format_jsn,
    no_comma_readed,
    run_exceptions,
    matching_last_name,
    name_swap,
    extract_congressmen,
    swap_names, 
    normalize_votes_in_place,
    normalize_text
)

DATA_DIR = ROOT_DIR / "data"
PDF_NAME = "Asis_y_vot_de_la_sesión_del_13-12-2024.pdf"
pdf_path=DATA_DIR / PDF_NAME

#votes_text = extract_text_from_page(votes_page)
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


#congresistas=last_name_swap(congresistas)
#matched_votes=matching_lists(congresistas,vote_list)


counter=0

for congresista in matched_votes3:
    if congresista["condicion"]=="en Ejercicio" and congresista["votacion"]!=None:
        counter+=1
#print(matched_votes)
#print(votes)
#print(type(votes))

print(counter)

list_faltan=[]
for item in matched_votes3:
    if item["votacion"]==None and item["condicion"]=="en Ejercicio":
        list_faltan.append(item["nombre_completo"])

print(list_faltan)

#congresistas_added=extract_congressmen(bill[1])

#print(count_votes(vote_list, "estado"))



final_votes=[]
for congresista in matched_votes3:
    if congresista["condicion"]=="en Ejercicio":
        final_votes.append(congresista)




print('matched3')

final_votes = normalize_votes_in_place(final_votes)

for vote in final_votes:
    vote["nombre_completo"]=normalize_text(vote["nombre_completo"])
    vote["nombre"]=normalize_text(vote["nombre"])
    vote["apellido"]=normalize_text(vote["apellido"])
    vote["bancada"]=normalize_text(vote["bancada"])

output_path = DATA_DIR / "seats.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(final_votes, f, ensure_ascii=False, indent=2)

print(f"Saved {len(final_votes)} seats to {output_path}")

#print(count_votes(final_votes, "votacion"))

#print(final_votes)

#print(matched_votes3)
#print(vote_list)
#print(congresistas_raw)
#print(congresistas_swaped)
#print(count_votes(final_votes, "votacion"))

#print(matched_votes3)
#print(count_votes(matched_votes3, "votacion"))
#print(bill[1])
#print(congresistas_added)




#############FALTA VER COMO ahcemos con los ultimos agregados al final
#############Falta ver como hacemos el match_last_name con los congresistas hermanos
#############Hacer una marca en congresistas, tiene eponimos: Si/ No
#print(matched_votes3)
#print(count_votes(votes["resultados"], "estado"))
#print(votes["resultados"])

#congresman_matched=matching_lists()

