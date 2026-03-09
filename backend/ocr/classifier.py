from __future__ import annotations

import re
import unicodedata

PAGE_TYPE_VOTE = "vote"
PAGE_TYPE_ATTENDANCE = "attendance"
PAGE_TYPE_OTHER = "other"

VOTE_PATTERNS = (
    re.compile(r"\bvotaci[oó]n\s*:"),
    re.compile(r"\bresultados?\s+de\s+votaci[oó]n\b"),
    re.compile(r"\bsi\s*\+{3,}\b"),
    re.compile(r"\bno\s*-{3,}\b"),
    re.compile(r"\babst\.?\b"),
    re.compile(r"\bsinres\b"),
)

ATTENDANCE_PATTERNS = (
    re.compile(r"##\s*asistencia\s*:"),
    re.compile(r"\basistencia\b"),
    re.compile(r"\bresultados?\s+de\s+la\s+asistencia\b"),
    re.compile(r"\bpresentes\b"),
    re.compile(r"\bausentes\b"),
    re.compile(r"\bqu[oó]rum\b"),
)

def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.lower()


def classify_page(text: str) -> str:
    normalized = normalize_text(text)
    if any(pattern.search(normalized) for pattern in ATTENDANCE_PATTERNS):
        return PAGE_TYPE_ATTENDANCE

    if any(pattern.search(normalized) for pattern in VOTE_PATTERNS):
        return PAGE_TYPE_VOTE

    return PAGE_TYPE_OTHER
