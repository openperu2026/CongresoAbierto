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

def to_str(val) -> str:
    if pd.isna(val):
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


def parse_input_test_excel(path: Path) -> dict:
    df = pd.read_excel(path, header=None)

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
                "votacion": normalize_text(row.get("votacion")),
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


def compare_results(actual_results: list[dict], expected_results: list[dict]) -> None:
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
            normalize_vote(r.get("votacion")),
        )

    actual_sorted = sorted((row_key(r) for r in actual_filtered))
    expected_sorted = sorted((row_key(r) for r in expected_filtered))

    if actual_sorted != expected_sorted:
        actual_set = set(actual_sorted)
        expected_set = set(expected_sorted)
        only_in_actual = sorted(actual_set - expected_set)
        only_in_expected = sorted(expected_set - actual_set)
        raise AssertionError(
            "Result mismatch.\n"
            f"Only in actual (first 20): {only_in_actual[:20]}\n"
            f"Only in expected (first 20): {only_in_expected[:20]}"
        )


def test_seats_json_matches_input_test_xlsx():
    expected = parse_input_test_excel(Path("data/input_test.xlsx"))
    actual = load_json(Path("data/seats.json"))

    assert normalize_text(actual.get("titulo")) == expected.get("titulo")
    assert normalize_text(actual.get("evento")) == expected.get("evento")
    assert str(actual.get("fecha", "")).strip() == expected.get("fecha")

    compare_results(actual.get("resultados", []), expected.get("resultados", []))


def test_transformation_final_matches_input_test_xlsx():
    tesseract_path = Path(r"C:/Program Files/Tesseract-OCR/tesseract.exe")
    if not tesseract_path.exists():
        pytest.skip("Tesseract not installed on this machine.")

    try:
        from backend.process import extract_votes as ev
    except Exception as exc:
        pytest.skip(f"extract_votes import failed: {exc}")

    expected = parse_input_test_excel(Path("data/input_test.xlsx"))

    pdf_candidates = list(Path("data").glob("Asis_y_vot_de_la_*_13-12-2024.pdf"))
    if not pdf_candidates:
        pytest.skip("Sample PDF not found.")
    pdf_path = pdf_candidates[0]

    attendance_text, votes_text = ev.render_bill(str(pdf_path))
    congresistas_jsn = load_json(Path("data/congresistas.json"))
    actual = ev.transformation_final(votes_text, congresistas_jsn)

    assert normalize_text(actual.get("titulo")) == expected.get("titulo")
    assert normalize_text(actual.get("evento")) == expected.get("evento")
    assert str(actual.get("fecha", "")).strip() == expected.get("fecha")

    compare_results(actual.get("resultados", []), expected.get("resultados", []))
