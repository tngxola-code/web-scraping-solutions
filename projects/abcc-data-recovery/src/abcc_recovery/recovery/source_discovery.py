"""Historical source discovery (SR-001 .. SR-007).

Strategy order:
1. SR-001  exact client-supplied URL recovery via the CDX index;
2. SR-003  historical filename-variant discovery (domain-wide CDX queries);
3. SR-004  archived resource-page recovery + inspection of its links.

Candidate selection follows SR-002: XLSX > XLS > CSV > PDF.  A PDF is never
selected when a structured spreadsheet source was recovered.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import yaml

from .downloader import DownloadAttempt, Downloader
from .file_detector import TYPE_CSV, TYPE_PDF, TYPE_XLS, TYPE_XLSX
from .wayback import WaybackClient, WaybackError

log = logging.getLogger("abcc_recovery.source_discovery")

# SR-003: likely filename variants (the list may be extended during
# investigation without code changes elsewhere).
FILENAME_VARIANTS = [
    "abcc_agreement_clauses_spreadsheet",
    "agreement_clauses",
    "agreement-clauses",
    "abcc_agreement_clauses",
]

# SR-002: original-spreadsheet priority.
FORMAT_PRIORITY = {TYPE_XLSX: 0, TYPE_XLS: 1, TYPE_CSV: 2, TYPE_PDF: 3}

_DOC_EXTENSIONS = (".xlsx", ".xls", ".csv", ".pdf")
_MIME_PREF = {
    TYPE_XLSX: ("application/vnd.openxmlformats-officedocument", "application/zip"),
    TYPE_XLS: ("application/vnd.ms-excel", "application/x-ole-storage"),
    TYPE_CSV: ("text/csv", "text/plain"),
    TYPE_PDF: ("application/pdf",),
}

STATUS_RECOVERED = "RECOVERED"
STATUS_NOT_RECOVERED = "SOURCE_NOT_RECOVERED"


def load_sources_config(path: str) -> list[dict[str, str]]:
    """Load the externalised source list (config/sources.yaml)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    sources = data.get("sources") or []
    for src in sources:
        if "url" not in src or "type" not in src:
            raise ValueError(f"invalid source entry in {path}: {src!r}")
    return sources


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append(value)


def extract_document_links(html: str, base_url: str) -> list[str]:
    """SR-004: pull XLS/XLSX/CSV/PDF-style links out of an archived page."""
    parser = _LinkExtractor()
    parser.feed(html)
    found: list[str] = []
    for link in parser.links:
        absolute = urljoin(base_url, link)
        path = urlparse(absolute).path.lower()
        if path.endswith(_DOC_EXTENSIONS) or "agreement" in path:
            if absolute not in found:
                found.append(absolute)
    return found


@dataclass
class Candidate:
    """A recovered (or recoverable) historical file."""

    original_url: str
    archive_url: str
    archive_timestamp: str
    discovered_via: str  # exact_url | filename_variant | resource_page_link
    attempt: Optional[DownloadAttempt] = None

    @property
    def accepted(self) -> bool:
        return self.attempt is not None and self.attempt.outcome == "DOWNLOADED"

    @property
    def detected_type(self) -> Optional[str]:
        return self.attempt.detected_file_type if self.attempt else None


def select_best_candidate(candidates: list[Candidate]) -> Optional[Candidate]:
    """SR-002: pick the highest-priority accepted candidate (XLSX>XLS>CSV>PDF)."""
    accepted = [c for c in candidates if c.accepted]
    if not accepted:
        return None
    return min(
        accepted,
        key=lambda c: FORMAT_PRIORITY.get(c.detected_type, 99),
    )


@dataclass
class RecoveryResult:
    status: str
    selected: Optional[Candidate]
    candidates: list[Candidate] = field(default_factory=list)
    queries: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    retrieval_date: str = ""

    def build_report(self) -> dict[str, Any]:
        """reports/recovery_report.json content (SPEC section 16)."""
        accepted = [c for c in self.candidates if c.accepted]
        rejected = [c for c in self.candidates if c.attempt and not c.accepted]
        selected = self.selected
        return {
            "status": self.status,
            "retrieval_date": self.retrieval_date,
            "urls_searched": sorted(
                {c.original_url for c in self.candidates}
                | {q["url"] for q in self.queries}
            ),
            "archive_queries": self.queries,
            "snapshots_discovered": sum(q.get("snapshots", 0) for q in self.queries),
            "files_considered": len(self.candidates),
            "files_accepted": [
                {
                    "original_url": c.original_url,
                    "archive_url": c.archive_url,
                    "archive_timestamp": c.archive_timestamp,
                    "detected_file_type": c.detected_type,
                    "sha256": c.attempt.sha256,
                    "file_size": c.attempt.file_size,
                    "saved_path": c.attempt.saved_path,
                    "discovered_via": c.discovered_via,
                }
                for c in accepted
            ],
            "files_rejected": [
                {
                    "original_url": c.original_url,
                    "archive_url": c.archive_url,
                    "http_status": c.attempt.http_status,
                    "detected_file_type": c.attempt.detected_file_type,
                    "error": c.attempt.error,
                }
                for c in rejected
            ],
            "checksums": {c.original_url: c.attempt.sha256 for c in accepted},
            "recovery_errors": self.errors,
            "selected_source": (
                {
                    "original_url": selected.original_url,
                    "archive_url": selected.archive_url,
                    "archive_timestamp": selected.archive_timestamp,
                    "detected_file_type": selected.detected_type,
                    "sha256": selected.attempt.sha256,
                    "file_size": selected.attempt.file_size,
                    "saved_path": selected.attempt.saved_path,
                    "discovered_via": selected.discovered_via,
                }
                if selected
                else None
            ),
            "attempts": [c.attempt.to_dict() for c in self.candidates if c.attempt],
        }


class SourceDiscovery:
    """Coordinates Wayback lookups and downloads to recover the source."""

    def __init__(self, wayback: WaybackClient, downloader: Downloader) -> None:
        self.wayback = wayback
        self.downloader = downloader
        self.queries: list[dict[str, Any]] = []
        self.errors: list[str] = []

    # ------------------------------------------------------------------
    def _cdx(self, url: str, **kwargs: Any) -> list[dict[str, str]]:
        try:
            snaps = self.wayback.cdx_search(url, **kwargs)
        except WaybackError as exc:
            self.errors.append(f"CDX query failed for {url}: {exc}")
            log.warning("[recovery] CDX query failed for %s: %s", url, exc)
            snaps = []
        self.queries.append({"url": url, "params": kwargs, "snapshots": len(snaps)})
        log.info("[recovery] Found %d archive snapshots for %s", len(snaps), url)
        return snaps

    def _try_snapshots(
        self,
        snapshots: list[dict[str, str]],
        dest_dir: str,
        discovered_via: str,
        prefer: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[Candidate]:
        """Evaluate snapshots (SR-005) and attempt downloads until one sticks."""
        ordered = self.wayback.evaluate_snapshots(snapshots, prefer_mimetypes=prefer)
        candidates: list[Candidate] = []
        for snap in ordered[:limit]:
            original = snap.get("original", "")
            ts = snap.get("timestamp", "")
            replay = self.wayback.replay_url(ts, original, raw=True)
            filename = os.path.basename(urlparse(original).path) or None
            attempt = self.downloader.download(
                replay,
                dest_dir,
                filename=filename,
                archive_timestamp=ts,
                archive_url=replay,
            )
            candidates.append(
                Candidate(
                    original_url=original,
                    archive_url=replay,
                    archive_timestamp=ts,
                    discovered_via=discovered_via,
                    attempt=attempt,
                )
            )
            if attempt.outcome == "DOWNLOADED":
                break  # first content-valid snapshot wins within this strategy
        return candidates

    # ------------------------------------------------------------------
    def recover(self, sources: list[dict[str, str]], dest_dir: str) -> RecoveryResult:
        candidates: list[Candidate] = []

        # --- SR-001: exact URL recovery first ---------------------------
        exact_doc_sources = [s for s in sources if s.get("type") != "webpage"]
        page_sources = [s for s in sources if s.get("type") == "webpage"]
        for src in exact_doc_sources:
            url = src["url"]
            log.info(
                "[recovery] Searching exact ABCC %s: %s", src.get("type", "file"), url
            )
            snapshots = self._cdx(url)
            prefer = _MIME_PREF.get(TYPE_PDF, ()) if src.get("type") == "pdf" else ()
            candidates.extend(
                self._try_snapshots(snapshots, dest_dir, "exact_url", prefer)
            )

        # --- SR-003: filename-variant discovery -------------------------
        if not any(c.accepted for c in candidates):
            for variant in FILENAME_VARIANTS:
                pattern = f"*.abcc.gov.au/*{variant}*"
                log.info("[recovery] Searching filename variant: %s", variant)
                snapshots = self._cdx(pattern, match_type="domain", limit=50)
                doc_snaps = [
                    s
                    for s in snapshots
                    if urlparse(s.get("original", ""))
                    .path.lower()
                    .endswith(_DOC_EXTENSIONS)
                ]
                candidates.extend(
                    self._try_snapshots(
                        doc_snaps, dest_dir, "filename_variant", limit=3
                    )
                )

        # --- SR-004: archived resource-page link inspection -------------
        if not any(c.accepted for c in candidates):
            for src in page_sources:
                url = src["url"]
                log.info("[recovery] Searching archived resource page: %s", url)
                snapshots = self._cdx(url)
                candidates.extend(
                    self._recover_via_resource_page(url, snapshots, dest_dir)
                )

        selected = select_best_candidate(candidates)
        status = STATUS_RECOVERED if selected else STATUS_NOT_RECOVERED
        if not selected:
            log.warning(
                "[recovery] SOURCE_NOT_RECOVERED: no authoritative source found"
            )
        return RecoveryResult(
            status=status,
            selected=selected,
            candidates=candidates,
            queries=self.queries,
            errors=self.errors,
            retrieval_date=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    # ------------------------------------------------------------------
    def _recover_via_resource_page(
        self, page_url: str, snapshots: list[dict[str, str]], dest_dir: str
    ) -> list[Candidate]:
        """Fetch an archived copy of the resource page and follow its links."""
        ordered = self.wayback.evaluate_snapshots(
            snapshots, prefer_mimetypes=("text/html",)
        )
        html: Optional[str] = None
        for snap in ordered[:5]:
            replay = self.wayback.replay_url(
                snap["timestamp"], snap["original"], raw=True
            )
            try:
                resp = self.wayback.session.get(replay, timeout=self.wayback.timeout)
                if resp.status_code == 200 and resp.text:
                    html = resp.text
                    break
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"resource page fetch failed: {exc}")
        if html is None:
            self.errors.append(f"no usable archived resource page for {page_url}")
            return []
        links = extract_document_links(html, page_url)
        log.info("[recovery] Resource page yielded %d candidate links", len(links))
        candidates: list[Candidate] = []
        for link in links[:10]:
            ext = os.path.splitext(urlparse(link).path)[1].lstrip(".").lower()
            prefer = _MIME_PREF.get(ext, ())
            snapshots = self._cdx(link)
            candidates.extend(
                self._try_snapshots(
                    snapshots, dest_dir, "resource_page_link", prefer, limit=3
                )
            )
        return candidates
