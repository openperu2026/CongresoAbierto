from datetime import datetime

from backend.ocr.pipeline import _write_deepseek_json_backups
from backend.ocr.storage import PDFSourceResolver, PDFStorageConfig
from backend.ocr.types import OCRPageResult, OCRSourceDocument


def _source(url: str) -> OCRSourceDocument:
    return OCRSourceDocument(
        parent_type="bill",
        parent_doc_id=1,
        parent_natural_id="2021_10",
        seguimiento_id="10",
        archivo_id="100",
        url=url,
    )


def test_resolver_uses_s3_uri_first(monkeypatch):
    resolver = PDFSourceResolver(PDFStorageConfig(prefer_s3=False, http_fallback=False))

    monkeypatch.setattr(
        resolver,
        "_download_s3",
        lambda bucket, key: b"PDF_BYTES" if bucket == "x" and key == "k.pdf" else None,
    )

    data = resolver.resolve_pdf_bytes(_source("s3://x/k.pdf"))
    assert data == b"PDF_BYTES"


def test_write_deepseek_json_backup(tmp_path):
    source = _source("https://example.com/doc.pdf")
    row = OCRPageResult(
        source=source,
        page_number=1,
        text="Resultados de Votacion",
        page_type="vote",
        ocr_provider="deepseek",
        ocr_model="deepseek-ai/DeepSeek-OCR",
        prompt="<image>\\nFree OCR.",
        processed=True,
        timestamp=datetime.now(),
        error=None,
    )

    _write_deepseek_json_backups(
        tmp_path,
        by_doc={source.parent_doc_id: [row]},
        pretty=True,
    )

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "Resultados de Votacion" in body
    assert "\"page_type\": \"vote\"" in body


def test_resolver_accepts_s3_key_without_pdf_extension(monkeypatch):
    resolver = PDFSourceResolver(
        PDFStorageConfig(
            s3_bucket="bucket",
            s3_prefix="openperu",
            prefer_s3=True,
            http_fallback=False,
        )
    )
    source = _source("https://example.com/ignored.pdf")

    # Stored object name uses "<bill_id>-<seguimiento_id>-<archivo_id>" (no .pdf)
    expected_key = "openperu/documents/bills/2021_10-10-100"

    def fake_download_s3(bucket, key):
        if bucket == "bucket" and key == expected_key:
            return b"PDF_NO_EXT"
        return None

    monkeypatch.setattr(resolver, "_download_s3", fake_download_s3)
    assert resolver.resolve_pdf_bytes(source) == b"PDF_NO_EXT"
