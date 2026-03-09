from backend.ocr.classifier import (
    PAGE_TYPE_ATTENDANCE,
    PAGE_TYPE_OTHER,
    PAGE_TYPE_VOTE,
    classify_page,
)


def test_classify_page_vote():
    text = "Resultados de Votación: SI+++ 80 NO--- 10 Abst. 2"
    assert classify_page(text) == PAGE_TYPE_VOTE


def test_classify_page_attendance():
    text = "ASISTENCIA para Quórum. Presentes 90, Ausentes 20"
    assert classify_page(text) == PAGE_TYPE_ATTENDANCE


def test_classify_page_other():
    text = "Proyecto de ley presentado ante la comisión de justicia"
    assert classify_page(text) == PAGE_TYPE_OTHER


def test_attendance_reference_pattern():
    text = (
        "## ASISTENCIA: Fecha: 20/10/2022 Hora: 10:07 am\n"
        "Resultados de la ASISTENCIA\n"
        "Presentes (Pre) 111"
    )
    assert classify_page(text) == PAGE_TYPE_ATTENDANCE


def test_vote_reference_pattern():
    text = (
        "VOTACIÓN: Fecha: 20/10/2022 Hora: 10:10 am\n"
        "SI +++ NO --- Abst.\n"
        "Resultados de VOTACIÓN"
    )
    assert classify_page(text) == PAGE_TYPE_VOTE


def test_attendance_not_misclassified_by_markdown_separators():
    text = (
        "## ASISTENCIA\\n"
        "| Presentes | Ausentes |\\n"
        "|---|---|\\n"
        "Resultados de la ASISTENCIA"
    )
    assert classify_page(text) == PAGE_TYPE_ATTENDANCE
