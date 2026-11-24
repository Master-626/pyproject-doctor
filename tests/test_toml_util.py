from __future__ import annotations

import math

import pytest

from pyproject_doctor.toml_util import TomlParseError, _FallbackParser, has_table, loads, table

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


def test_has_table_distinguishes_empty_from_missing():
    data = loads("[tool.ruff]\n[tool.pytest.ini_options]\n")
    assert has_table(data, "tool", "ruff")
    assert table(data, "tool", "ruff") == {}
    assert has_table(data, "tool", "pytest", "ini_options")
    assert not has_table(data, "tool", "mypy")


def test_fallback_signed_exponent_and_inf():
    data = _FallbackParser("n = 1e-10\nmid = 1.5e-1\nbig = 1e+2\npos = +inf\nneg = -inf\nnan = +nan\n").parse()
    assert data["n"] == 1e-10
    assert data["mid"] == 0.15
    assert data["big"] == 100.0
    assert data["pos"] == float("inf")
    assert data["neg"] == float("-inf")
    assert math.isnan(data["nan"])
    assert loads("n = 1.5e-1\n")["n"] == 0.15


def test_fallback_rejects_truncated_exponent():
    with pytest.raises(TomlParseError):
        _FallbackParser("n = 1e-\n").parse()


def test_fallback_rejects_duplicate_table():
    text = '[project]\nname = "a"\n\n[project]\nversion = "0.1.0"\n'
    with pytest.raises(TomlParseError):
        _FallbackParser(text).parse()
    with pytest.raises(TomlParseError):
        loads(text)


def test_fallback_allows_parent_after_child_table():
    text = """
[tool.ruff.lint]
select = ["E", "F"]

[tool.ruff]
line-length = 100

[project.urls]
Homepage = "https://example.com"

[project]
name = "demo"
"""
    data = _FallbackParser(text).parse()
    assert data["tool"]["ruff"]["line-length"] == 100
    assert data["tool"]["ruff"]["lint"]["select"] == ["E", "F"]
    assert data["project"]["name"] == "demo"
    assert data["project"]["urls"]["Homepage"] == "https://example.com"


def test_fallback_array_of_tables_can_repeat_and_grow_subtables():
    text = """
[[fruit]]
name = "apple"

[[fruit]]
name = "banana"

[fruit.physical]
color = "yellow"
"""
    data = _FallbackParser(text).parse()
    assert [item["name"] for item in data["fruit"]] == ["apple", "banana"]
    assert data["fruit"][1]["physical"]["color"] == "yellow"


def test_fallback_table_conflicts_with_array_of_tables():
    text = '[[project]]\nname = "a"\n\n[project]\nversion = "0.1.0"\n'
    with pytest.raises(TomlParseError):
        _FallbackParser(text).parse()


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
