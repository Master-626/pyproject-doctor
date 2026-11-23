from __future__ import annotations

from pyproject_doctor.toml_util import _FallbackParser, loads, table

SAMPLE = """
# comment
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.8"
license = {text = "MIT"}
dynamic = ["readme"]
authors = [
  { name = "Ada", email = "ada@example.com" },
]

[project.urls]
Homepage = "https://example.com"

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
"""


def test_stdlib_or_fallback_parses_pyproject_subset():
    data = loads(SAMPLE)
    project = table(data, "project")
    assert project["name"] == "demo"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.8"
    assert project["license"]["text"] == "MIT"
    assert project["dynamic"] == ["readme"]
    assert table(data, "tool", "ruff")["line-length"] == 100
    assert table(data, "tool", "pytest", "ini_options")["testpaths"] == ["tests"]
    assert table(data, "project", "urls")["Homepage"] == "https://example.com"


def test_fallback_parser_matches_sample():
    data = _FallbackParser(SAMPLE).parse()
    assert data["project"]["license"]["text"] == "MIT"
    assert data["project"]["authors"][0]["name"] == "Ada"
    assert data["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


def test_fallback_multiline_and_escapes():
    text = '''
description = """
hello\\nworld
"""
literal = \'\'\'keep\\nraw\'\'\'
'''
    data = _FallbackParser(text).parse()
    assert "hello" in data["description"]
    assert "world" in data["description"]
    assert data["literal"] == "keep\\nraw"
