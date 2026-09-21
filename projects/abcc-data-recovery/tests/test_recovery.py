"""Recovery tests (SPEC section 22): config loading, archive parsing,
failed recovery, candidate selection, and the guarantee that a failed
recovery never produces synthetic data."""

from __future__ import annotations

import json
import os

import pytest

from abcc_recovery import cli
from abcc_recovery.recovery.downloader import Downloader, sanitize_filename
from abcc_recovery.recovery.source_discovery import (STATUS_NOT_RECOVERED,
                                                     STATUS_RECOVERED,
                                                     Candidate,
                                                     SourceDiscovery,
                                                     extract_document_links,
                                                     load_sources_config,
                                                     select_best_candidate)
from abcc_recovery.recovery.wayback import WaybackClient, parse_cdx_rows
from tests.conftest import FakeResponse, FakeSession, cdx_payload
from tests.fixtures import make_xlsx

PDF_URL = (
    "https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.pdf"
)
PAGE_URL = "https://www.abcc.gov.au/resources/agreement-clauses"


# ----------------------------------------------------------------------
# Configuration loading
# ----------------------------------------------------------------------
def test_repo_config_loads_exact_sources(repo_config_path):
    sources = load_sources_config(repo_config_path)
    assert len(sources) == 2
    by_type = {s["type"]: s for s in sources}
    assert by_type["pdf"]["url"] == PDF_URL
    assert by_type["webpage"]["url"] == PAGE_URL


def test_config_loading_requires_url(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("sources:\n  - name: broken\n    type: pdf\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_sources_config(str(bad))


# ----------------------------------------------------------------------
# Archive result parsing
# ----------------------------------------------------------------------
def test_cdx_result_parsing():
    payload = cdx_payload(
        [
            [
                "au,gov,abcc)/x.pdf",
                "20150101120000",
                PDF_URL,
                "application/pdf",
                "200",
                "ABC",
                "1234",
            ],
            [
                "au,gov,abcc)/x.pdf",
                "20160101120000",
                PDF_URL,
                "text/html",
                "404",
                "DEF",
                "999",
            ],
        ]
    )
    snaps = parse_cdx_rows(payload)
    assert len(snaps) == 2
    assert snaps[0]["timestamp"] == "20150101120000"
    assert snaps[0]["mimetype"] == "application/pdf"
    assert parse_cdx_rows([]) == []
    assert parse_cdx_rows(None) == []


def test_availability_parsing():
    session = FakeSession(
        {
            "archive.org/wayback/available": FakeResponse(
                json_data={
                    "archived_snapshots": {
                        "closest": {
                            "available": True,
                            "url": "http://web.archive.org/web/2015/x",
                            "timestamp": "20150101",
                            "status": "200",
                        }
                    }
                }
            )
        }
    )
    client = WaybackClient(session=session)
    closest = client.availability(PDF_URL)
    assert closest["timestamp"] == "20150101"

    empty = WaybackClient(
        session=FakeSession(
            {
                "archive.org/wayback/available": FakeResponse(
                    json_data={"archived_snapshots": {}}
                )
            }
        )
    )
    assert empty.availability(PDF_URL) is None


def test_polite_retry_on_429():
    session = FakeSession(
        {
            "cdx": [
                FakeResponse(429, headers={"Retry-After": "1"}),
                FakeResponse(json_data=cdx_payload([])),
            ]
        }
    )
    waits = []
    client = WaybackClient(session=session, sleep=waits.append)
    assert client.cdx_search(PDF_URL) == []
    assert waits, "client must back off politely after HTTP 429"


# ----------------------------------------------------------------------
# Candidate selection (SR-002 priority)
# ----------------------------------------------------------------------
def _candidate(fmt, outcome="DOWNLOADED"):
    from abcc_recovery.recovery.downloader import DownloadAttempt

    attempt = DownloadAttempt(requested_url="https://example.test/file")
    attempt.outcome = outcome
    attempt.detected_file_type = fmt
    attempt.sha256 = "x"
    return Candidate(
        original_url="https://example.test/file",
        archive_url="https://web.archive.org/web/1/file",
        archive_timestamp="1",
        discovered_via="test",
        attempt=attempt,
    )


def test_candidate_selection_priority():
    assert (
        select_best_candidate([_candidate("pdf"), _candidate("xlsx")]).detected_type
        == "xlsx"
    )
    assert (
        select_best_candidate([_candidate("pdf"), _candidate("csv")]).detected_type
        == "csv"
    )
    assert select_best_candidate([_candidate("pdf")]).detected_type == "pdf"
    assert (
        select_best_candidate([_candidate("xls"), _candidate("csv")]).detected_type
        == "xls"
    )


def test_candidate_selection_none_accepted():
    assert select_best_candidate([]) is None
    assert select_best_candidate([_candidate("pdf", outcome="FAILED")]) is None


# ----------------------------------------------------------------------
# Failed recovery / no synthetic data
# ----------------------------------------------------------------------
def _empty_discovery():
    wayback = WaybackClient(session=FakeSession({}), sleep=lambda s: None)
    downloader = Downloader(session=FakeSession({}))
    return SourceDiscovery(wayback, downloader)


def test_failed_recovery_status(config_path, tmp_path):
    discovery = _empty_discovery()
    sources = load_sources_config(config_path)
    result = discovery.recover(sources, str(tmp_path / "source"))
    assert result.status == STATUS_NOT_RECOVERED
    assert result.selected is None
    report = result.build_report()
    assert report["status"] == STATUS_NOT_RECOVERED
    assert report["files_accepted"] == []


def test_run_pipeline_creates_no_synthetic_data(config_path, tmp_path):
    """Failed recovery: SOURCE_NOT_RECOVERED report, no dataset, non-zero exit."""
    ctx = cli.PipelineContext(str(tmp_path), config_path)
    code = cli.stage_run(ctx, discovery=_empty_discovery())
    assert code == cli.EXIT_RECOVERY_FAILED

    report = json.loads((tmp_path / "reports" / "recovery_report.json").read_text())
    assert report["status"] == STATUS_NOT_RECOVERED
    assert report["selected_source"] is None

    # no synthetic dataset or output workbook may exist
    assert not (tmp_path / "data" / "raw" / cli.RAW_RECORDS).exists()
    assert not (tmp_path / "data" / "clean" / cli.CLEAN_RECORDS).exists()
    output = tmp_path / "data" / "output"
    produced = (
        [p for p in output.glob("*") if p.name != ".gitkeep"] if output.exists() else []
    )
    assert produced == []


# ----------------------------------------------------------------------
# Successful recovery through fake archive (offline)
# ----------------------------------------------------------------------
def test_successful_recovery_downloads_and_detects(config_path, tmp_path):
    xlsx_bytes = open(make_xlsx(str(tmp_path / "fixture_src.xlsx")), "rb").read()
    download_session = FakeSession(
        {
            "web.archive.org/web": FakeResponse(200, content=xlsx_bytes),
        }
    )
    wayback_session = FakeSession(
        {
            "cdx": FakeResponse(
                json_data=cdx_payload(
                    [
                        [
                            "au,gov,abcc)/pdf",
                            "20160101000000",
                            PDF_URL,
                            "application/pdf",
                            "200",
                            "D1",
                            "10",
                        ],
                    ]
                )
            ),
        }
    )
    discovery = SourceDiscovery(
        WaybackClient(session=wayback_session, sleep=lambda s: None),
        Downloader(session=download_session),
    )
    result = discovery.recover(
        load_sources_config(config_path), str(tmp_path / "source")
    )
    assert result.status == STATUS_RECOVERED
    # FD-001: content bytes say XLSX even though the archived URL ends in .pdf
    assert result.selected.detected_type == "xlsx"
    assert result.selected.attempt.sha256
    assert os.path.exists(result.selected.attempt.saved_path)


def test_downloader_rejects_html_replay_page(tmp_path):
    html = (
        b"<!DOCTYPE html><html><head><title>Wayback</title></head><body></body></html>"
    )
    downloader = Downloader(session=FakeSession({"*": FakeResponse(200, content=html)}))
    attempt = downloader.download("https://web.archive.org/web/1/x.pdf", str(tmp_path))
    assert attempt.outcome == "FAILED"
    assert attempt.detected_file_type == "html"
    assert not (tmp_path / "x.pdf").exists()


def test_safe_filename_blocks_path_traversal():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\evil.pdf") == "evil.pdf"
    assert sanitize_filename("normal_file.xlsx") == "normal_file.xlsx"
    assert sanitize_filename("") == "recovered_file"


def test_resource_page_link_extraction():
    html = """
    <html><body>
      <a href="/sites/default/files/agreement_clauses.xlsx">Download</a>
      <a href="https://www.abcc.gov.au/other/page">About us</a>
      <a href="/files/abcc_agreement_clauses.pdf">PDF</a>
    </body></html>
    """
    links = extract_document_links(html, PAGE_URL)
    assert "https://www.abcc.gov.au/sites/default/files/agreement_clauses.xlsx" in links
    assert "https://www.abcc.gov.au/files/abcc_agreement_clauses.pdf" in links
    assert not any(l.endswith("/other/page") for l in links)
