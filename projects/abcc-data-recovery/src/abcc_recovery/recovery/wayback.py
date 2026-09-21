"""Wayback Machine (web.archive.org) API clients.

All network access goes through an injectable ``session`` object so tests
never touch the network.  The session only needs a ``get(url, params=...,
timeout=...)`` method returning an object with ``status_code``, ``headers``
and ``json()``/``text`` attributes (``requests.Session`` compatible).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

import requests

log = logging.getLogger("abcc_recovery.wayback")

AVAILABILITY_API = "https://archive.org/wayback/available"
CDX_API = "https://web.archive.org/cdx/search/cdx"
REPLAY_PREFIX = "https://web.archive.org/web"

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_SECONDS = 5.0


class WaybackError(Exception):
    """Raised when a Wayback API call fails after retries."""


def parse_cdx_rows(payload: list[list[str]]) -> list[dict[str, str]]:
    """Parse CDX JSON output (header row + data rows) into dicts."""
    if not payload or not isinstance(payload, list):
        return []
    header, rows = payload[0], payload[1:]
    snapshots = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(header):
            continue
        snapshots.append(dict(zip(header, row)))
    return snapshots


class WaybackClient:
    """Client for the Wayback availability and CDX APIs.

    Parameters
    ----------
    session:
        requests-compatible session; injectable for tests.
    sleep:
        sleep callable used for 429 back-off; injectable so tests do not wait.
    """

    def __init__(
        self,
        session: Optional[Any] = None,
        sleep: Optional[Callable[[float], None]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session or requests.Session()
        self.sleep = sleep or time.sleep
        self.timeout = timeout

    # ------------------------------------------------------------------
    def _get_json(self, url: str, params: dict[str, Any]) -> Any:
        """GET expecting JSON, with polite retry on HTTP 429 (rate limited)."""
        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except Exception as exc:  # network-layer failure
                last_error = exc
                log.warning("wayback request error (attempt %d): %s", attempt, exc)
                self.sleep(BACKOFF_SECONDS * attempt)
                continue
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After") if resp.headers else None
                try:
                    wait = (
                        float(retry_after) if retry_after else BACKOFF_SECONDS * attempt
                    )
                except ValueError:
                    wait = BACKOFF_SECONDS * attempt
                log.warning("wayback rate-limited (429); backing off %.1fs", wait)
                self.sleep(wait)
                continue
            if resp.status_code != 200:
                raise WaybackError(f"Wayback API HTTP {resp.status_code} for {url}")
            try:
                return resp.json()
            except Exception as exc:
                raise WaybackError(
                    f"Wayback API returned invalid JSON for {url}: {exc}"
                )
        raise WaybackError(
            f"Wayback API failed after {MAX_RETRIES} attempts: {last_error or 'rate limited'}"
        )

    # ------------------------------------------------------------------
    def availability(self, url: str) -> Optional[dict[str, Any]]:
        """Query the availability API for the closest snapshot of *url*.

        Returns the ``archived_snapshots.closest`` dict, or None if no
        snapshot is available.
        """
        data = self._get_json(AVAILABILITY_API, {"url": url})
        snapshots = (data or {}).get("archived_snapshots") or {}
        closest = snapshots.get("closest")
        if closest and closest.get("available"):
            return closest
        return None

    # ------------------------------------------------------------------
    def cdx_search(
        self,
        url: str,
        match_type: Optional[str] = None,
        status_filter: Optional[str] = "200",
        limit: Optional[int] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """Search the CDX index; returns a list of snapshot dicts."""
        params: dict[str, Any] = {"url": url, "output": "json"}
        if match_type:
            params["matchType"] = match_type
        if status_filter:
            params["filter"] = f"statuscode:{status_filter}"
        if limit:
            params["limit"] = str(limit)
        if extra_params:
            params.update(extra_params)
        payload = self._get_json(CDX_API, params)
        return parse_cdx_rows(payload)

    # ------------------------------------------------------------------
    @staticmethod
    def replay_url(timestamp: str, original: str, raw: bool = True) -> str:
        """Build a replay URL for a snapshot (``id_`` = original content)."""
        suffix = "id_" if raw else ""
        return f"{REPLAY_PREFIX}/{timestamp}{suffix}/{original}"

    # ------------------------------------------------------------------
    @staticmethod
    def evaluate_snapshots(
        snapshots: list[dict[str, str]],
        prefer_mimetypes: Optional[tuple[str, ...]] = None,
    ) -> list[dict[str, str]]:
        """Order snapshots for evaluation (SR-005).

        The newest snapshot is NOT assumed to be the best source.  Snapshots
        are ordered so that candidates whose archived MIME type matches the
        kind of file we are looking for are tried first; within each group
        newer snapshots come first, but *every* candidate is expected to be
        validated by content inspection after download.
        """
        usable = [s for s in snapshots if s.get("statuscode") == "200"]

        def score(snap: dict[str, str]) -> tuple[int, str]:
            mime = (snap.get("mimetype") or "").lower()
            preferred = 0
            if prefer_mimetypes:
                preferred = (
                    0 if any(mime.startswith(p) for p in prefer_mimetypes) else 1
                )
            # sort key: preferred mime first, then newest timestamp first
            return (preferred, _invert_timestamp(snap.get("timestamp", "")))

        return sorted(usable, key=score)


def _invert_timestamp(ts: str) -> str:
    """Invert a numeric timestamp string so 'newest first' sorts ascending."""
    return "".join(str(9 - int(c)) if c.isdigit() else c for c in ts)
