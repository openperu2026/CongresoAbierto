from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from backend.config import settings
from backend.documents.downloader import build_filename
from backend.ocr.types import OCRSourceDocument
from backend.scrapers.utils import get_url


_S3_URI_RE = re.compile(r"^s3://(?P<bucket>[^/]+)/(?P<key>.+)$")


@dataclass(slots=True)
class PDFStorageConfig:
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    prefer_s3: bool = True
    http_fallback: bool = True


class PDFSourceResolver:
    def __init__(self, config: PDFStorageConfig):
        self.config = config
        self._s3_client = None

    def _client(self):
        if self._s3_client is not None:
            return self._s3_client

        try:
            import boto3  # type: ignore
        except Exception as exc:
            raise RuntimeError("boto3 is required for S3-backed OCR input") from exc

        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            session = boto3.session.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            self._s3_client = session.client("s3")
        else:
            self._s3_client = boto3.client("s3", region_name=settings.AWS_REGION)

        return self._s3_client

    @staticmethod
    def _build_key(prefix: str | None, kind: str, filename: str) -> str:
        parts: list[str] = []
        if prefix:
            parts.append(prefix.strip("/"))
        parts.extend(["documents", kind, filename])
        return "/".join(parts)

    @staticmethod
    def _candidate_filenames(source: OCRSourceDocument) -> list[str]:
        # Preferred canonical filename (used by downloader/upload path).
        with_ext = build_filename(
            source.parent_natural_id,
            source.seguimiento_id,
            source.archivo_id,
        )
        # Compatibility with buckets that store objects without ".pdf".
        no_ext = with_ext[:-4] if with_ext.lower().endswith(".pdf") else with_ext
        # Uppercase extension compatibility in legacy uploads.
        upper_ext = f"{no_ext}.PDF"
        return [with_ext, no_ext, upper_ext]

    def _download_s3(self, bucket: str, key: str) -> bytes | None:
        try:
            obj = self._client().get_object(Bucket=bucket, Key=key)
            return obj["Body"].read()
        except Exception as exc:
            logger.warning(f"S3 fetch failed s3://{bucket}/{key}: {exc}")
            return None

    def resolve_pdf_bytes(self, source: OCRSourceDocument) -> bytes | None:
        # Case 1: URL is already an s3:// URI
        s3_match = _S3_URI_RE.match(source.url)
        if s3_match:
            return self._download_s3(
                bucket=s3_match.group("bucket"),
                key=s3_match.group("key"),
            )

        # Case 2: deterministic key lookup based on existing downloader naming
        if self.config.prefer_s3:
            bucket = self.config.s3_bucket or settings.AWS_S3_BUCKET_NAME
            prefix = self.config.s3_prefix or settings.AWS_S3_PREFIX
            if bucket:
                kind = "bills" if source.parent_type == "bill" else "motions"
                for filename in self._candidate_filenames(source):
                    key = self._build_key(prefix, kind, filename)
                    data = self._download_s3(bucket, key)
                    if data:
                        return data

        # Case 3: fallback to HTTP source URL
        if self.config.http_fallback:
            response = get_url(source.url)
            if response is None:
                return None
            try:
                response.raise_for_status()
            except Exception as exc:
                logger.warning(f"HTTP fetch failed {source.url}: {exc}")
                return None
            return response.content

        return None
