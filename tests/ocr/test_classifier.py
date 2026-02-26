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
