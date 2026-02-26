from __future__ import annotations

from io import BytesIO

import fitz
from PIL import Image


def iter_pdf_pages_as_png_bytes(pdf_bytes: bytes, dpi: int = 220):
    """Yield (page_number, PNG bytes) one page at a time."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_number, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = BytesIO()
            image.save(buf, format="PNG")
            yield page_number, buf.getvalue()
