#!/usr/bin/env python3
"""Capture a real ``pyproject-doctor`` run and write ``docs/demo.txt`` and ``docs/demo.svg``.

The sample repository is temporary. It has a README, a ``pyproject.toml`` with
ruff and pytest configuration, tests, a Python ``.gitignore``, and a GitHub
Actions workflow that runs pytest but not ruff. It has no LICENSE file.

Stdout and the process exit code are captured from the installed
``pyproject-doctor`` console script. Do not hand-edit ``demo.txt`` or
``demo.svg``; rerun this script after installing this repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pyproject_doctor import __version__

DOCS = Path(__file__).resolve().parent

SAMPLE_README = """\
# sample

A tiny Python package used to demonstrate pyproject-doctor.
It has a README, tests, pytest configuration, and ruff configuration.
Its GitHub Actions workflow runs pytest only.
There is no LICENSE file at the repository root.
"""

SAMPLE_PYPROJECT = """\
[project]
name = "sample"
version = "0.1.0"
requires-python = ">=3.8"
license = {text = "MIT"}

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
"""

SAMPLE_TEST = """\
def test_ok():
    assert True
"""

SAMPLE_GITIGNORE = """\
__pycache__/
*.py[cod]
.venv/
*.egg-info/
"""

# Pytest only. The word "ruff" must not appear here: the ruff check looks
# for that word in workflow files directly under .github/workflows/.
SAMPLE_WORKFLOW = """\
name: CI

on:
  push:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Pytest
        run: pytest
"""

FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace"
FONT_SIZE = 14
CHAR_WIDTH = 8.4
LINE_HEIGHT = 22
PAD_X = 22
PAD_Y = 16
TITLE_H = 40
FOOTER_H = 32

COLORS = {
    "text": "#e6edf3",
    "dim": "#9ca3af",
    "heading": "#e6edf3",
    "pass": "#3fb950",
    "fail": "#f85149",
    "fix": "#6e7681",
}


def main() -> int:
    cli = _find_cli()
    _require_this_project(cli)
    with tempfile.TemporaryDirectory(prefix="pyproject-doctor-demo-") as tmp:
        root = Path(tmp) / "sample"
        _write_sample(root)
        proc = subprocess.run(
            cli + [str(root)],
            check=False,
            capture_output=True,
            encoding="utf-8",
        )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    _write_transcript(cli, root, proc.returncode, stdout, stderr)
    svg = _render_svg(stdout, proc.returncode)
    (DOCS / "demo.svg").write_text(svg, encoding="utf-8")
    if stderr.strip():
        sys.stderr.write(stderr)
        return 2
    return 0


def _find_cli() -> list[str]:
    extra = [
        str(Path(sys.executable).resolve().parent),
        str(Path.home() / ".local" / "bin"),
    ]
    search = os.pathsep.join([os.environ.get("PATH", "")] + extra)
    found = shutil.which("pyproject-doctor", path=search)
    if not found:
        sys.stderr.write(
            "error: pyproject-doctor is not installed. "
            "Install this repository with `pip install .` and rerun docs/generate_demo.py.\n"
        )
        raise SystemExit(2)
    return [found]


def _require_this_project(cli: list[str]) -> None:
    proc = subprocess.run(cli + ["--version"], check=False, capture_output=True, encoding="utf-8")
    version_line = (proc.stdout or "").strip()
    expected = "pyproject-doctor %s" % __version__
    if proc.returncode != 0 or version_line != expected:
        sys.stderr.write(
            "error: `%s --version` returned %r (exit %s); expected %r. "
            "Install this repository. `pip install pyproject-doctor` is a different project.\n"
            % (cli[0], version_line, proc.returncode, expected)
        )
        raise SystemExit(2)


def _write_sample(root: Path) -> None:
    files = {
        "README.md": SAMPLE_README,
        "pyproject.toml": SAMPLE_PYPROJECT,
        "tests/test_sample.py": SAMPLE_TEST,
        ".gitignore": SAMPLE_GITIGNORE,
        ".github/workflows/ci.yml": SAMPLE_WORKFLOW,
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _write_transcript(
    cli: list[str],
    root: Path,
    exit_code: int,
    stdout: str,
    stderr: str,
) -> None:
    header = "command: %s %s\nexit_code: %s\n--- stdout ---\n" % (cli[0], root, exit_code)
    body = header + stdout
    if stderr:
        if not body.endswith("\n"):
            body += "\n"
        body += "--- stderr ---\n" + stderr
    (DOCS / "demo.txt").write_text(body, encoding="utf-8")


def _render_svg(stdout: str, exit_code: int) -> str:
    lines = stdout.splitlines()
    kinds = _classify(lines)
    longest = max([len(line) for line in lines] or [0])
    longest = max(longest, len("exit code %s" % exit_code), len("pyproject-doctor"))
    width = int(PAD_X * 2 + longest * CHAR_WIDTH + 12)
    height = TITLE_H + PAD_Y + max(len(lines), 1) * LINE_HEIGHT + PAD_Y + FOOTER_H
    footer_y = height - FOOTER_H
    exit_color = COLORS["pass"] if exit_code == 0 else COLORS["fail"]
    text_nodes = []
    for index, line in enumerate(lines):
        if line == "":
            continue
        baseline = TITLE_H + PAD_Y + FONT_SIZE + index * LINE_HEIGHT
        text_nodes.append(
            '  <text x="%s" y="%s" fill="%s" xml:space="preserve">%s</text>'
            % (PAD_X, baseline, COLORS[kinds[index]], _xml(line))
        )
    footer_baseline = footer_y + 21
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s" role="img">'
        % (width, height, width, height),
        "  <title>pyproject-doctor CLI demo</title>",
        "  <defs>",
        '    <clipPath id="frame"><rect width="%s" height="%s" rx="12"/></clipPath>' % (width, height),
        "  </defs>",
        '  <g clip-path="url(#frame)" font-family="%s" font-size="%s">' % (_xml(FONT), FONT_SIZE),
        '    <rect width="%s" height="%s" fill="#0d1117"/>' % (width, height),
        '    <rect width="%s" height="%s" fill="#161b22"/>' % (width, TITLE_H),
        '    <circle cx="20" cy="20" r="6" fill="#ff5f56"/>',
        '    <circle cx="40" cy="20" r="6" fill="#febc2e"/>',
        '    <circle cx="60" cy="20" r="6" fill="#28c840"/>',
        '    <text x="80" y="25" fill="#8b949e" font-size="13">pyproject-doctor</text>',
        "\n".join(text_nodes),
        '    <rect y="%s" width="%s" height="%s" fill="#161b22"/>' % (footer_y, width, FOOTER_H),
        '    <text x="%s" y="%s" fill="%s" font-size="13">exit code %s</text>'
        % (PAD_X, footer_baseline, exit_color, exit_code),
        "  </g>",
        "</svg>",
        "",
    ]
    return "\n".join(parts)


def _classify(lines: list[str]) -> list[str]:
    kinds = []
    in_fixes = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Suggested fixes:":
            in_fixes = True
            kinds.append("heading")
            continue
        if in_fixes:
            kinds.append("fix" if stripped else "text")
            continue
        first = stripped.split(" ", 1)[0] if stripped else ""
        if first == "pass":
            kinds.append("pass")
        elif first == "fail":
            kinds.append("fail")
        elif first == "STATUS" or (stripped and set(stripped) <= {"-", " "}):
            kinds.append("dim")
        else:
            kinds.append("text")
    return kinds


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    sys.exit(main())
