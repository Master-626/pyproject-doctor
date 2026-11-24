from __future__ import annotations

from pathlib import Path
from typing import Dict

from pyproject_doctor.sources import LocalSource

MINIMAL_README = (
    "# Demo\n\n"
    "This is a small Python project used in tests. It documents install and usage "
    "so the README check treats it as non-trivial.\n"
)

COMPLETE_PYPROJECT = """
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.8"
license = {text = "MIT"}

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
"""

CI_BOTH = """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: ruff check .
      - run: pytest
"""

MIT_LICENSE = "MIT License\n\nCopyright (c) 2026 Example\n"

GITIGNORE = """\
__pycache__/
*.py[cod]
.venv/
*.egg-info/
"""


def complete_tree() -> Dict[str, str]:
    return {
        "README.md": MINIMAL_README,
        "pyproject.toml": COMPLETE_PYPROJECT,
        "tests/test_demo.py": "def test_ok():\n    assert True\n",
        ".github/workflows/ci.yml": CI_BOTH,
        "LICENSE": MIT_LICENSE,
        ".gitignore": GITIGNORE,
    }


def local(root: Path) -> LocalSource:
    return LocalSource(root)
