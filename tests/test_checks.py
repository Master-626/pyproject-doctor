from __future__ import annotations

from pathlib import Path

import pytest

from pyproject_doctor.checks import (
    check_ci_pytest,
    check_gitignore,
    check_license,
    check_pyproject,
    check_readme,
    check_ruff,
    check_tests,
    run_checks,
)
from tests.helpers import MINIMAL_README, complete_tree, local


def test_complete_repo_passes_all_checks(write_tree, tmp_path: Path):
    root = write_tree(complete_tree())
    report = run_checks(local(root))
    assert report.ok
    assert report.passed == 7
    assert {item.id for item in report.checks} == {
        "readme",
        "pyproject",
        "tests",
        "ci_pytest",
        "ruff",
        "license",
        "gitignore",
    }


def test_readme_missing(write_tree, tmp_path: Path):
    root = write_tree({"notes.txt": "hi"})
    result = check_readme(local(root))
    assert not result.ok
    assert "no README" in result.detail
    assert result.fix and "README.md" in result.fix


def test_readme_trivial_title_only(write_tree, tmp_path: Path):
    root = write_tree({"README.md": "# Just a title\n"})
    result = check_readme(local(root))
    assert not result.ok
    assert "too short" in result.detail or "only a title" in result.detail


def test_readme_ok(write_tree, tmp_path: Path):
    root = write_tree({"README.md": MINIMAL_README})
    result = check_readme(local(root))
    assert result.ok
    assert "README.md" in result.detail


def test_pyproject_missing(write_tree, tmp_path: Path):
    root = write_tree({"README.md": MINIMAL_README})
    result = check_pyproject(local(root))
    assert not result.ok
    assert "no pyproject.toml" in result.detail


def test_pyproject_missing_fields(write_tree, tmp_path: Path):
    root = write_tree({"pyproject.toml": '[project]\nname = "demo"\n'})
    result = check_pyproject(local(root))
    assert not result.ok
    assert "version" in result.detail
    assert "requires-python" in result.detail
    assert "license" in result.detail
    assert result.fix and "requires-python" in result.fix


def test_pyproject_accepts_dynamic_version_and_license_files(write_tree, tmp_path: Path):
    root = write_tree(
        {
            "pyproject.toml": """
[project]
name = "demo"
dynamic = ["version"]
requires-python = ">=3.8"
license-files = ["LICENSE"]
"""
        }
    )
    result = check_pyproject(local(root))
    assert result.ok
    assert "version=dynamic" in result.detail


def test_pyproject_invalid_toml(write_tree, tmp_path: Path):
    root = write_tree({"pyproject.toml": "[project\nname = "})
    result = check_pyproject(local(root))
    assert not result.ok
    assert "could not parse" in result.detail


def test_tests_missing(write_tree, tmp_path: Path):
    root = write_tree({"src/demo.py": "x = 1\n"})
    result = check_tests(local(root))
    assert not result.ok
    assert "no tests/" in result.detail
    assert result.fix and "tests/" in result.fix


def test_tests_config_without_files(write_tree, tmp_path: Path):
    root = write_tree(
        {
            "pyproject.toml": "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n",
        }
    )
    result = check_tests(local(root))
    assert not result.ok
    assert "no test_" in result.detail


def test_tests_present(write_tree, tmp_path: Path):
    root = write_tree({"tests/test_demo.py": "def test_ok():\n    assert True\n"})
    result = check_tests(local(root))
    assert result.ok
    assert "1 test file" in result.detail


def test_ci_pytest_missing_workflow(write_tree, tmp_path: Path):
    root = write_tree({"README.md": MINIMAL_README})
    result = check_ci_pytest(local(root))
    assert not result.ok
    assert "no GitHub Actions workflow" in result.detail


def test_ci_pytest_workflow_without_pytest(write_tree, tmp_path: Path):
    root = write_tree({".github/workflows/ci.yml": "name: CI\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"})
    result = check_ci_pytest(local(root))
    assert not result.ok
    assert "none run pytest" in result.detail


def test_ci_pytest_present(write_tree, tmp_path: Path):
    root = write_tree({".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: pytest -q\n"})
    result = check_ci_pytest(local(root))
    assert result.ok


def test_ruff_missing_both(write_tree, tmp_path: Path):
    root = write_tree({"README.md": MINIMAL_README})
    result = check_ruff(local(root))
    assert not result.ok
    assert "not configured" in result.detail
    assert result.fix and "tool.ruff" in result.fix


def test_ruff_configured_but_not_in_ci(write_tree, tmp_path: Path):
    root = write_tree(
        {
            "ruff.toml": "line-length = 88\n",
            ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: pytest\n",
        }
    )
    result = check_ruff(local(root))
    assert not result.ok
    assert "not run in CI" in result.detail


def test_ruff_in_ci_but_not_configured(write_tree, tmp_path: Path):
    root = write_tree({".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: ruff check .\n"})
    result = check_ruff(local(root))
    assert not result.ok
    assert "no ruff config" in result.detail


def test_ruff_ok(write_tree, tmp_path: Path):
    root = write_tree(
        {
            "pyproject.toml": "[tool.ruff]\nline-length = 88\n",
            ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: ruff check .\n",
        }
    )
    result = check_ruff(local(root))
    assert result.ok


def test_license_missing(write_tree, tmp_path: Path):
    root = write_tree({"README.md": MINIMAL_README})
    result = check_license(local(root))
    assert not result.ok
    assert "no LICENSE" in result.detail


def test_license_present(write_tree, tmp_path: Path):
    root = write_tree({"LICENSE": "MIT License\n\nPermission is hereby granted, free of charge\nTHE SOFTWARE IS PROVIDED\n"})
    result = check_license(local(root))
    assert result.ok
    assert "MIT" in result.detail


def test_this_repository_passes():
    root = Path(__file__).resolve().parents[1]
    report = run_checks(local(root))
    assert report.ok, [item.to_dict() for item in report.checks if not item.ok]


def test_pyproject_empty_table_lists_missing_fields(write_tree, tmp_path: Path):
    root = write_tree({"pyproject.toml": "[project]\n"})
    result = check_pyproject(local(root))
    assert not result.ok
    assert "missing [project] fields" in result.detail
    assert "name" in result.detail
    assert "version" in result.detail


@pytest.mark.parametrize(
    "license_line",
    [
        'license = {text = ""}',
        'license = {file = "  "}',
        'license = "  "',
        'license-files = [""]',
    ],
)
def test_pyproject_rejects_blank_license_values(write_tree, tmp_path: Path, license_line: str):
    root = write_tree(
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.1.0"\n'
                'requires-python = ">=3.8"\n%s\n' % license_line
            )
        }
    )
    result = check_pyproject(local(root))
    assert not result.ok
    assert "license" in result.detail


def test_tests_directory_without_modules_is_not_described_as_missing(write_tree, tmp_path: Path):
    root = write_tree({"tests/conftest.py": "import pytest\n", "tests/__init__.py": ""})
    result = check_tests(local(root))
    assert not result.ok
    assert "no tests/ directory" not in result.detail
    assert "tests exists" in result.detail
    assert "no test_" in result.detail
    assert result.fix and "tests" in result.fix


def test_tests_empty_pytest_table_counts_as_config(write_tree, tmp_path: Path):
    root = write_tree({"pyproject.toml": "[tool.pytest]\n"})
    result = check_tests(local(root))
    assert not result.ok
    assert "pytest is configured" in result.detail


def test_tests_config_and_directory_without_modules(write_tree, tmp_path: Path):
    root = write_tree(
        {
            "pyproject.toml": "[tool.pytest.ini_options]\n",
            "tests/conftest.py": "",
        }
    )
    result = check_tests(local(root))
    assert not result.ok
    assert "pytest is configured" in result.detail
    assert "in tests" in result.detail
    assert result.fix and result.fix.startswith("Add at least one")


def test_tests_empty_ini_options_counts_as_config(write_tree, tmp_path: Path):
    root = write_tree({"pyproject.toml": "[tool.pytest.ini_options]\n"})
    result = check_tests(local(root))
    assert not result.ok
    assert "pytest is configured" in result.detail


def test_ci_pytest_ignores_nested_workflow_files(write_tree, tmp_path: Path):
    root = write_tree(
        {
            ".github/workflows/ci.yml": "name: CI\njobs:\n  lint:\n    runs-on: ubuntu-latest\n",
            ".github/workflows/templates/pytest.yml": "run: pytest\n",
        }
    )
    result = check_ci_pytest(local(root))
    assert not result.ok
    assert "none run pytest" in result.detail
    assert "templates" not in result.detail


def test_ci_pytest_uses_top_level_workflow_only(write_tree, tmp_path: Path):
    root = write_tree(
        {
            ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: pytest -q\n",
            ".github/workflows/templates/unused.yml": "name: unused\n",
        }
    )
    result = check_ci_pytest(local(root))
    assert result.ok
    assert "ci.yml" in result.detail
    assert "templates" not in result.detail


def test_ruff_empty_tool_table_counts_as_configured(write_tree, tmp_path: Path):
    root = write_tree(
        {
            "pyproject.toml": "[tool.ruff]\n",
            ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: ruff check .\n",
        }
    )
    result = check_ruff(local(root))
    assert result.ok


def test_ruff_ignores_nested_workflow_files(write_tree, tmp_path: Path):
    root = write_tree(
        {
            "pyproject.toml": "[tool.ruff]\nline-length = 88\n",
            ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: pytest\n",
            ".github/workflows/templates/ruff.yml": "run: ruff check .\n",
        }
    )
    result = check_ruff(local(root))
    assert not result.ok
    assert "not run in CI" in result.detail


@pytest.mark.parametrize(
    "text",
    [
        "__pycache__/\n",
        "*.py[cod]\n",
        ".venv/\n",
        "venv/\n",
        "*.egg-info/\n",
        ".pytest_cache/\n",
        "# comment\n__pycache__/  # bytecode\n",
    ],
)
def test_gitignore_python_rules_pass(write_tree, tmp_path: Path, text: str):
    root = write_tree({".gitignore": text})
    result = check_gitignore(local(root))
    assert result.ok
    assert "ignores Python artifacts" in result.detail


def test_gitignore_missing(write_tree, tmp_path: Path):
    root = write_tree({"README.md": MINIMAL_README})
    result = check_gitignore(local(root))
    assert not result.ok
    assert "no .gitignore" in result.detail
    assert result.fix and "__pycache__" in result.fix


def test_gitignore_without_python_rules(write_tree, tmp_path: Path):
    root = write_tree({".gitignore": "node_modules/\ndist/\n"})
    result = check_gitignore(local(root))
    assert not result.ok
    assert "does not ignore" in result.detail


def test_gitignore_comment_does_not_count(write_tree, tmp_path: Path):
    root = write_tree({".gitignore": "# ignore __pycache__ later\nnode_modules/\n"})
    result = check_gitignore(local(root))
    assert not result.ok
