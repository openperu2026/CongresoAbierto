#uv run pytest -W ignore::UserWarning  .\tests\test_transformation_final.py -vv

import re
import unicodedata
from pathlib import Path

import json
import pandas as pd
import pytest



def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    if not s:
        return ""
    s = s.upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def normalize_vote(value: str) -> str:
    v = normalize_text(value)
    if v in {"SI", "NO"}:
        return v
    return "OTROS"

def jaro_winkler_similarity(s1: str, s2: str, prefix_scale: float = 0.1, max_prefix: int = 4) -> float:
    # Pure Python implementation to avoid external deps in tests.
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] == s2[j]:
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    # Count transpositions.
    t = 0
    j = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[j]:
            j += 1
        if s1[i] != s2[j]:
            t += 1
        j += 1
    transpositions = t / 2

    jaro = (
        (matches / len1) +
        (matches / len2) +
        ((matches - transpositions) / matches)
    ) / 3

    # Winkler adjustment.
    prefix = 0
    for i in range(min(max_prefix, len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    return jaro + prefix * prefix_scale * (1 - jaro)

def assert_title_similar(actual_title: str, expected_title: str, threshold: float = 0.6) -> None:
    a = normalize_text(actual_title)
    e = normalize_text(expected_title)
    score = jaro_winkler_similarity(a, e)
    assert score >= threshold, f"Title similarity below threshold: {score:.3f} < {threshold}"

def to_str(val) -> str:
    if pd.isna(val):
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


def parse_input_test_excel(path: Path, sheetname) -> dict:
    df = pd.read_excel(path, sheet_name= sheetname, header=None)

    raw_title = df.iloc[0, 1]
    raw_fecha = df.iloc[1, 1]
    raw_evento = df.iloc[2, 1]

    if isinstance(raw_fecha, pd.Timestamp):
        fecha = raw_fecha.strftime("%d/%m/%Y")
    else:
        fecha = to_str(raw_fecha)

    titulo = normalize_text(raw_title)
    evento = normalize_text(raw_evento)

    header = df.iloc[3].tolist()
    data_df = df.iloc[4:].copy()
    data_df.columns = header
    data_df = data_df.dropna(subset=["id"])

    resultados = []
    for _, row in data_df.iterrows():
        resultados.append(
            {
                "id": to_str(row.get("id")),
                "nombre": normalize_text(row.get("nombre")),
                "apellido": normalize_text(row.get("apellido")),
                "nombre_completo": normalize_text(row.get("nombre_completo")),
                "bancada": normalize_text(row.get("bancada")),
                "voto": normalize_text(row.get("voto")),
            }
        )

    return {
        "titulo": titulo,
        "evento": evento,
        "fecha": fecha,
        "resultados": resultados,
    }

def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compare_results(actual_results: list[dict], expected_results: list[dict], report: bool = False) -> None:
    # Only compare rows where en_ejercicio is True in actual results.
    actual_filtered = [r for r in actual_results if r.get("en_ejercicio") is True]
    actual_ids = {str(r.get("id", "")).strip() for r in actual_filtered}
    expected_filtered = [
        r for r in expected_results if str(r.get("id", "")).strip() in actual_ids
    ]

    def row_key(r: dict) -> tuple:
        return (
            str(r.get("id", "")).strip(),
            normalize_text(r.get("nombre")),
            normalize_text(r.get("apellido")),
            normalize_text(r.get("nombre_completo")),
            normalize_text(r.get("bancada")),
            normalize_vote(r.get("voto")),
        )

    actual_keyed = [(row_key(r), r) for r in actual_filtered]
    expected_keyed = [(row_key(r), r) for r in expected_filtered]

    actual_sorted = sorted((k for k, _ in actual_keyed))
    expected_sorted = sorted((k for k, _ in expected_keyed))

    if actual_sorted != expected_sorted:
        actual_set = set(actual_sorted)
        expected_set = set(expected_sorted)
        only_in_actual = sorted(actual_set - expected_set)
        only_in_expected = sorted(expected_set - actual_set)
        matched = len(actual_set & expected_set)
        actual_lookup = {k: r for k, r in actual_keyed}
        expected_lookup = {k: r for k, r in expected_keyed}
        only_in_actual_dicts = [actual_lookup[k] for k in only_in_actual[:20]]
        only_in_expected_dicts = [expected_lookup[k] for k in only_in_expected[:20]]
        if not report:
            raise AssertionError("Result mismatch.")
        raise AssertionError(
            "Result mismatch.\n"
            f"Matched results: {matched}\n"
            f"Unmatched in actual: {len(only_in_actual)}\n"
            f"Unmatched in expected: {len(only_in_expected)}\n"
            f"Only in actual results (first 2 dicts): {only_in_actual_dicts}\n"
            f"Only in expected results (first 2 dicts): {only_in_expected_dicts}"
        )

def with_voto_key(expected_results: list[dict]) -> list[dict]:
    out = []
    for r in expected_results:
        if "voto" in r:
            out.append(r)
            continue
        rr = dict(r)
        rr["voto"] = r.get("voto")
        out.append(rr)
    return out


#def test_seats_json_matches_input_test_xlsx():
#    expected = parse_input_test_excel(Path("data/input_test.xlsx"), "Sheet1")

#    actual = load_json(Path("data/seats.json"))
#    assert_title_similar(actual.get("titulo"), expected.get("titulo"))
#    assert normalize_text(actual.get("evento")) == expected.get("evento")
#    assert str(actual.get("fecha", "")).strip() == expected.get("fecha")
#
 #   compare_results(actual.get("resultados", []), expected.get("resultados", []))
#

def test_transformation_final_L31751():
    try:
        from backend.process import extract_votes_DS as ev
    except Exception as exc:
        pytest.skip(f"extract_votes_DS import failed: {exc}")

    expected = parse_input_test_excel(Path("data/to_test_function/input_test.xlsx"), "L31751")

    txt_path = Path("data/extracted_text/L31751.txt")
    if not txt_path.exists():
        pytest.skip("Sample text not found.")
    votes_text = txt_path.read_text(encoding="utf-8", errors="ignore")
    congresistas_jsn = load_json(Path("data/congresistas_2021_2026.json"))
    
    actual = ev.transformation_final(votes_text, congresistas_jsn)

    compare_results(actual, with_voto_key(expected.get("resultados", [])), report=True)








def test_transformation_final_L31989():

    try:
        from backend.process import extract_votes_DS as ev
    except Exception as exc:
        pytest.skip(f"extract_votes_DS import failed: {exc}")

    expected = parse_input_test_excel(Path("data/to_test_function/input_test.xlsx"), "L31989")

    txt_path = Path("data/extracted_text/L31989.txt")
    if not txt_path.exists():
        pytest.skip("Sample text not found.")
    votes_text = txt_path.read_text(encoding="utf-8", errors="ignore")
    congresistas_jsn = load_json(Path("data/congresistas_2021_2026.json"))
    
    actual = ev.transformation_final(votes_text, congresistas_jsn)

    compare_results(actual, with_voto_key(expected.get("resultados", [])), report=True)



