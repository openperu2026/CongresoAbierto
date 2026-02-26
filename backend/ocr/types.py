from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class OCRSourceDocument:
    parent_type: str  # bill | motion
    parent_doc_id: int
    parent_natural_id: str
    seguimiento_id: str
    archivo_id: str
    url: str


@dataclass(slots=True)
class OCRPageTask:
    source: OCRSourceDocument
    page_number: int
    image_bytes: bytes


@dataclass(slots=True)
class OCRPageResult:
    source: OCRSourceDocument
    page_number: int
    text: str
    page_type: str
    ocr_provider: str
    ocr_model: str
    prompt: str
    processed: bool
    timestamp: datetime
    error: str | None = None
