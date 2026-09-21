"""Untrusted-file downloader with safety limits and full attempt logging.

Security (SPEC section 23):
* URLs must be HTTPS where available (plain HTTP is upgraded/rejected);
* downloaded bytes are treated as untrusted input and validated by content
  (see file_detector) before any processing;
* remote filenames never control arbitrary filesystem paths — the basename
  is sanitised to a strict character set;
* downloads are size-capped and time-limited.

Every attempt produces a log record with all SR-006 fields.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from . import file_detector

log = logging.getLogger("abcc_recovery.downloader")

MAX_BYTES = 50 * 1024 * 1024  # 50 MB cap
DEFAULT_TIMEOUT = 60
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class DownloadAttempt:
    """SR-006 recovery-attempt log record."""

    requested_url: str
    archive_url: Optional[str] = None
    archive_timestamp: Optional[str] = None
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    detected_file_type: Optional[str] = None
    file_size: Optional[int] = None
    sha256: Optional[str] = None
    outcome: str = "FAILED"
    error: Optional[str] = None
    saved_path: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sanitize_filename(name: str, default: str = "recovered_file") -> str:
    """Reduce a remote filename to a safe basename (SPEC section 23)."""
    base = os.path.basename(name.replace("\\", "/").split("?")[0])
    base = SAFE_NAME_RE.sub("_", base).strip("._")
    if not base:
        base = default
    return base[:120]


def ensure_https(url: str) -> str:
    """Upgrade plain HTTP URLs to HTTPS where available."""
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


class Downloader:
    """Downloads candidate files with limits and per-attempt logging."""

    def __init__(
        self,
        session: Optional[Any] = None,
        max_bytes: int = MAX_BYTES,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session or requests.Session()
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.attempts: list[DownloadAttempt] = []

    # ------------------------------------------------------------------
    def _fetch(self, url: str) -> tuple[int, Optional[str], bytes]:
        resp = self.session.get(url, timeout=self.timeout, stream=True)
        status = resp.status_code
        ctype = resp.headers.get("Content-Type") if resp.headers else None
        chunks: list[bytes] = []
        total = 0
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.max_bytes:
                    raise ValueError(
                        f"download exceeded size cap of {self.max_bytes} bytes"
                    )
                chunks.append(chunk)
        finally:
            close = getattr(resp, "close", None)
            if callable(close):
                close()
        return status, ctype, b"".join(chunks)

    # ------------------------------------------------------------------
    def download(
        self,
        url: str,
        dest_dir: str,
        filename: Optional[str] = None,
        archive_timestamp: Optional[str] = None,
        archive_url: Optional[str] = None,
    ) -> DownloadAttempt:
        """Download *url* into *dest_dir*; always returns an attempt record.

        The returned attempt has ``outcome == "DOWNLOADED"`` only when the
        bytes were fetched and content-validated as a real document.
        """
        url = ensure_https(url)
        attempt = DownloadAttempt(
            requested_url=url,
            archive_url=archive_url,
            archive_timestamp=archive_timestamp,
        )
        self.attempts.append(attempt)
        try:
            status, ctype, data = self._fetch(url)
            attempt.http_status = status
            attempt.content_type = ctype
            if status != 200:
                attempt.error = f"HTTP {status}"
                log.warning("[recovery] Download failed: %s (HTTP %s)", url, status)
                return attempt
            attempt.file_size = len(data)
            attempt.sha256 = file_detector.sha256_hex(data)
            detected = file_detector.detect_file_type(data)
            attempt.detected_file_type = detected
            if detected in (file_detector.TYPE_HTML, file_detector.TYPE_UNKNOWN):
                # FD-004: replay/error pages must not be processed as documents
                attempt.error = f"content rejected: detected type '{detected}'"
                log.warning("[file] Rejected %s: detected %s", url, detected)
                return attempt
            safe = sanitize_filename(filename or os.path.basename(urlparse(url).path))
            os.makedirs(dest_dir, exist_ok=True)
            path = os.path.join(dest_dir, safe)
            with open(path, "wb") as fh:
                fh.write(data)
            attempt.saved_path = path
            attempt.outcome = "DOWNLOADED"
            log.info(
                "[recovery] Candidate downloaded: %s (%d bytes, %s)",
                safe,
                len(data),
                detected,
            )
            return attempt
        except Exception as exc:  # noqa: BLE001 - record and continue (SR-006)
            attempt.error = str(exc)
            log.warning("[recovery] Download error for %s: %s", url, exc)
            return attempt
