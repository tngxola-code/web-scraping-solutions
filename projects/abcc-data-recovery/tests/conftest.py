"""Shared pytest fixtures and fake (offline) HTTP plumbing.

No test ever performs real network access: every HTTP interaction goes
through FakeSession, which serves canned responses matched by URL
substring.
"""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tests.fixtures import make_csv, make_pdf, make_xlsx  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class FakeResponse:
    def __init__(
        self, status_code=200, json_data=None, text="", content=b"", headers=None
    ):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.content = content
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]

    def close(self):
        pass


class FakeSession:
    """URL-substring routed fake of requests.Session."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.requests = []

    def get(self, url, params=None, timeout=None, stream=False):
        self.requests.append({"url": url, "params": params or {}, "stream": stream})
        full = url + ("?" + urlencode(self.requests[-1]["params"]) if params else "")
        for key, handler in self.routes.items():
            if key == "*" or key in full or key in url:
                if callable(handler):
                    return handler(url, params)
                if isinstance(handler, list):
                    if not handler:
                        return FakeResponse(500, text="exhausted")
                    return handler.pop(0)
                return handler
        return FakeResponse(404, text="not found", content=b"not found")


@pytest.fixture()
def config_path(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - name: agreement_clauses_pdf\n"
        "    type: pdf\n"
        "    url: https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.pdf\n"
        "  - name: agreement_clauses_page\n"
        "    type: webpage\n"
        "    url: https://www.abcc.gov.au/resources/agreement-clauses\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture()
def repo_config_path():
    return os.path.join(REPO_ROOT, "config", "sources.yaml")


@pytest.fixture()
def xlsx_fixture(tmp_path):
    return make_xlsx(str(tmp_path / "fixture.xlsx"))


@pytest.fixture()
def csv_fixture(tmp_path):
    return make_csv(str(tmp_path / "fixture.csv"))


@pytest.fixture()
def pdf_fixture(tmp_path):
    return make_pdf(str(tmp_path / "fixture.pdf"))


def cdx_payload(rows):
    header = [
        "urlkey",
        "timestamp",
        "original",
        "mimetype",
        "statuscode",
        "digest",
        "length",
    ]
    return [header] + rows
