from __future__ import annotations

import re
import unicodedata

PAGE_TYPE_VOTE = "vote"
PAGE_TYPE_ATTENDANCE = "attendance"
PAGE_TYPE_OTHER = "other"

# Strong vote markers that do NOT appear in attendance tables
VOTE_PATTERNS = (
    # Header (present in many, but not all)
    re.compile(r"(?mi)^\s*#{0,6}\s*VOTACI[ÓO]N\b\s*:", re.IGNORECASE),

    # The real discriminator: +++ / --- / Abst.
    re.compile(r"\+{3,}"),                # +++
    re.compile(r"-{3,}"),                 # ---
    re.compile(r"(?i)\bABST\.?\b"),       # Abst. / ABST
)

# Attendance: header OR attendance-style status codes in a table,
# but explicitly NOT vote tables (no +++/---/Abst.)
ATTENDANCE_PATTERNS = (
    re.compile(r"(?mi)^\s*#{0,6}\s*ASISTENCIA\b\s*:", re.IGNORECASE),
    re.compile(r"(?mi)^\s*ASISTENCIA\b\s*:", re.IGNORECASE),

    # Pipe table rows containing attendance status codes like PRE/LP/LE/aus
    # This catches pages that are table-only (no header).
    re.compile(
        r"(?mi)^\s*\|.*\b(?:PRE|LP|LE|AUS|aus)\b.*\|"
        r"(?!.*(?:\+{3,}|-{3,}|\bABST\.?\b))"
    ),
)

def classify_text(text: str) -> str:
    # Votes first, because vote tables can contain "aus" too
    if any(p.search(text) for p in VOTE_PATTERNS):
        return "votes"
    if any(p.search(text) for p in ATTENDANCE_PATTERNS):
        return "attendance"
    return "other"

def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.lower()


def classify_page(text: str) -> str:
    normalized = normalize_text(text)

    for pattern in VOTE_PATTERNS:
        if pattern.search(normalized):
            return PAGE_TYPE_VOTE

    for pattern in ATTENDANCE_PATTERNS:
        if pattern.search(normalized):
            return PAGE_TYPE_ATTENDANCE

    return PAGE_TYPE_OTHER
