from __future__ import annotations

import io
import json
import urllib.error
from typing import Dict, List
from urllib.request import Request

import pytest

from pyproject_doctor.checks import run_checks
from pyproject_doctor.cli import run
from pyproject_doctor.sources import GitHubSource, SourceError, parse_github_spec
from tests.helpers import complete_tree


class FakeResponse:
    def __init__(self, payload) -> None:
        if isinstance(payload, bytes):
            self._data = payload
        elif isinstance(payload, str):
            self._data = payload.encode("utf-8")
        else:
            self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


class FakeGitHub:
    def __init__(self, files: Dict[str, str], default_branch: str = "main") -> None:
        self.files = files
        self.default_branch = default_branch
        self.calls: List[str] = []

    def __call__(self, request, timeout=30):
        url = request.full_url if isinstance(request, Request) else str(request)
        self.calls.append(url)
        if url.endswith("/repos/owner/demo") or url.endswith("/repos/owner/demo/"):
            return FakeResponse({"default_branch": self.default_branch})
        if "/git/trees/" in url:
            tree = [{"path": path, "type": "blob", "sha": "abc"} for path in self.files]
            return FakeResponse({"tree": tree, "truncated": False})
        if "/contents/" in url:
            path = url.split("/contents/", 1)[1].split("?", 1)[0]
            # URL-decoded path may still be encoded; try both.
            from urllib.parse import unquote

            path = unquote(path)
            if path not in self.files:
                raise urllib.error.HTTPError(url, 404, "not found", hdrs=None, fp=io.BytesIO(b"{}"))
            return FakeResponse(self.files[path])
        raise AssertionError("unexpected URL: %s" % url)


def test_parse_github_spec_variants():
    assert parse_github_spec("owner/name") == ("owner", "name")
    assert parse_github_spec("https://github.com/owner/name.git") == ("owner", "name")
    assert parse_github_spec("https://github.com/owner/name/") == ("owner", "name")
    assert parse_github_spec("https://github.com/owner/name/tree/main") == ("owner", "name")
    assert parse_github_spec("https://www.github.com/owner/name") == ("owner", "name")
    assert parse_github_spec("https://github.com/owner/name?tab=readme-ov-file") == ("owner", "name")
    assert parse_github_spec("https://github.com/owner/name#readme") == ("owner", "name")
    assert parse_github_spec("git@github.com:owner/name.git") == ("owner", "name")
    assert parse_github_spec("ssh://git@github.com/owner/name.git") == ("owner", "name")
    assert parse_github_spec("ssh://git@github.com:owner/name.git") == ("owner", "name")
    assert parse_github_spec("https://github.com/owner/name.git?tab=readme") == ("owner", "name")
    with pytest.raises(SourceError):
        parse_github_spec("only-owner")
    with pytest.raises(SourceError):
        parse_github_spec("https://gitlab.com/owner/name")


def test_github_source_runs_checks_with_mocked_api():
    opener = FakeGitHub(complete_tree())
    source = GitHubSource("owner", "demo", opener=opener, token="test-token")
    report = run_checks(source)
    assert report.ok
    assert "owner/demo@main" in report.target
    assert any("git/trees/main" in url for url in opener.calls)
    assert any("/contents/" in url for url in opener.calls)
    assert any(".github/workflows/ci.yml" in url for url in opener.calls)
    assert not any("%2F" in url.split("/contents/", 1)[-1] for url in opener.calls if "/contents/" in url)


def test_cli_github_mode_uses_mock(monkeypatch):
    original = GitHubSource.__init__

    def wrapped(self, owner, repo, token=None, api_base="https://api.github.com", opener=None):
        original(
            self,
            owner,
            repo,
            token=token,
            api_base=api_base,
            opener=opener or FakeGitHub(complete_tree()),
        )

    monkeypatch.setattr(GitHubSource, "__init__", wrapped)
    stdout = io.StringIO()
    code = run(["--github", "owner/demo", "--json"], stdout=stdout, stderr=io.StringIO())
    assert code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["target"].startswith("owner/demo")


def test_github_http_404_is_source_error():
    def opener(request, timeout=30):
        raise urllib.error.HTTPError(
            "https://api.github.com/repos/owner/missing",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"Not Found"}'),
        )

    with pytest.raises(SourceError) as exc:
        GitHubSource("owner", "missing", opener=opener)
    assert "not found" in str(exc.value)


def test_github_branch_with_slash_is_fully_encoded():
    opener = FakeGitHub(complete_tree(), default_branch="release/1.0")
    source = GitHubSource("owner", "demo", opener=opener)
    assert source.default_branch == "release/1.0"
    assert source.label().endswith("@release/1.0")
    assert any("/git/trees/release%2F1.0" in url for url in opener.calls)
    source.read_text("README.md")
    contents = [url for url in opener.calls if "/contents/" in url]
    assert contents
    assert all("ref=release%2F1.0" in url for url in contents)
    assert all("%2F" not in url.split("/contents/", 1)[1].split("?", 1)[0] for url in contents)


def test_github_truncated_tree_is_an_error():
    def opener(request, timeout=30):
        url = request.full_url if isinstance(request, Request) else str(request)
        if url.endswith("/repos/owner/demo"):
            return FakeResponse({"default_branch": "main"})
        if "/git/trees/" in url:
            return FakeResponse({"tree": [{"path": "README.md", "type": "blob", "sha": "abc"}], "truncated": True})
        raise AssertionError(url)

    with pytest.raises(SourceError) as exc:
        GitHubSource("owner", "demo", opener=opener)
    assert "truncated" in str(exc.value)


def test_github_rate_limit_mentions_token():
    def opener(request, timeout=30):
        raise urllib.error.HTTPError(
            "https://api.github.com/repos/owner/demo",
            403,
            "Forbidden",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"API rate limit exceeded"}'),
        )

    with pytest.raises(SourceError) as exc:
        GitHubSource("owner", "demo", opener=opener)
    assert "GITHUB_TOKEN" in str(exc.value)
