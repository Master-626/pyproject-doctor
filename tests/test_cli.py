from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from pyproject_doctor.cli import run
from tests.helpers import complete_tree


def test_cli_json_success_exit_zero(write_tree, tmp_path: Path):
    root = write_tree(complete_tree())
    stdout, stderr = StringIO(), StringIO()
    code = run([str(root), "--json"], stdout=stdout, stderr=stderr)
    assert code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["passed"] == 6
    assert payload["failed"] == 0
    assert stderr.getvalue() == ""


def test_cli_text_failure_exit_one(write_tree, tmp_path: Path):
    root = write_tree({"README.md": "# Title only\n"})
    stdout, stderr = StringIO(), StringIO()
    code = run([str(root)], stdout=stdout, stderr=stderr)
    assert code == 1
    text = stdout.getvalue()
    assert "Target:" in text
    assert "fail" in text
    assert "Suggested fixes:" in text


def test_cli_fail_under_allows_partial_success(write_tree, tmp_path: Path):
    root = write_tree(complete_tree())
    # Drop the license so one check fails.
    (root / "LICENSE").unlink()
    stdout = StringIO()
    code = run([str(root), "--fail-under", "5", "--json"], stdout=stdout)
    payload = json.loads(stdout.getvalue())
    assert payload["passed"] == 5
    assert payload["failed"] == 1
    assert code == 0
    code_strict = run([str(root), "--strict"], stdout=StringIO())
    assert code_strict == 1


def test_cli_missing_directory_is_error(tmp_path: Path):
    missing = tmp_path / "nope"
    stderr = StringIO()
    code = run([str(missing)], stdout=StringIO(), stderr=stderr)
    assert code == 2
    assert "not a directory" in stderr.getvalue()


def test_cli_rejects_path_and_github_together(tmp_path: Path):
    stderr = StringIO()
    code = run([str(tmp_path), "--github", "owner/name"], stdout=StringIO(), stderr=stderr)
    assert code == 2
    assert "not both" in stderr.getvalue()
