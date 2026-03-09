from __future__ import annotations

from io import BytesIO

try:
    import pymupdf as fitz  # preferred modern import
except Exception:  # pragma: no cover
    import fitz  # fallback for environments exposing only fitz
from PIL import Image


def _open_pdf(pdf_bytes: bytes):
    if hasattr(fitz, "open"):
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    if hasattr(fitz, "Document"):
        return fitz.Document(stream=pdf_bytes, filetype="pdf")
    raise RuntimeError(
        "PyMuPDF is not available with a compatible API. "
        "Install with: pip install -U PyMuPDF"
    )


def iter_pdf_pages_as_png_bytes(pdf_bytes: bytes, dpi: int = 220):
    """Yield (page_number, PNG bytes) one page at a time."""
    with _open_pdf(pdf_bytes) as doc:
        for page_number, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = BytesIO()
            image.save(buf, format="PNG")
            yield page_number, buf.getvalue()
