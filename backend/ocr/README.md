# OCR Module

This module runs asynchronous page-level OCR over bill/motion document PDFs.

## Flow

1. Load pending URLs from Raw DB (`raw_bill_documents`, `raw_motion_documents`)
2. Download each PDF
3. Stream pages one-by-one
4. OCR each page with a provider (DeepSeekOCR)
5. Classify page (`vote`, `attendance`, `other`)
6. Upsert results into `raw_document_pages`
7. Aggregate page text back into the parent raw document row

## Programmatic usage

```python
from backend.config import settings
from backend.ocr import (
    DeepSeekOCRProvider,
    OCRPipelineConfig,
    OCRRepository,
    run_ocr_pipeline,
)

repo = OCRRepository(settings.RAW_DB_URL)
provider = DeepSeekOCRProvider(model_name="deepseek-ai/DeepSeek-OCR")
config = OCRPipelineConfig(
    documents_limit=100,
    workers=1,
    # S3-first resolution (recommended for Colab to avoid source-site WAF blocks)
    s3_bucket="your-bucket",
    s3_prefix="openperu",
    prefer_s3=True,
    http_fallback=True,
    # DeepSeek-only JSON backup
    deepseek_json_backup_dir="data/raw/ocr_json_backup",
)
stats = run_ocr_pipeline(repository=repo, provider=provider, config=config)
print(stats)
```

## Notes

- Colab is suitable for backfills and ad-hoc jobs.
- For reliable always-on processing, use a persistent GPU worker runtime.
- When running in Colab, prefer S3 input instead of source URLs to avoid 403/WAF issues.
