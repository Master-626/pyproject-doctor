"""Project hygiene checks and one-line fix suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from pyproject_doctor.sources import RepoSource
from pyproject_doctor.toml_util import as_str_list, parse_file_text, table

README_NAMES = ("README.md", "README.rst", "README.txt", "README", "README.markdown")
LICENSE_NAMES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "LICENCE",
    "LICENCE.md",
    "LICENCE.txt",
    "COPYING",
    "COPYING.md",
    "UNLICENSE",
)
RUFF_FILENAMES = ("ruff.toml", ".ruff.toml")
PYTEST_CONFIG_NAMES = ("pytest.ini", "pytest.toml", "setup.cfg", "tox.ini")
TEST_DIR_NAMES = ("tests", "test")
WORKFLOW_DIR = ".github/workflows"
MIN_README_CHARS = 80

STATUS_PASS = "pass"
STATUS_FAIL = "fail"


@dataclass
class CheckResult:
    id: str
    name: str
    status: str
    detail: str
    fix: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_PASS

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "fix": self.fix,
        }


@dataclass
class Report:
    target: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for item in self.checks if item.ok)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.checks if not item.ok)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "ok": self.ok,
            "checks": [item.to_dict() for item in self.checks],
        }


def run_checks(source: RepoSource) -> Report:
    report = Report(target=source.label())
    report.checks.append(check_readme(source))
    report.checks.append(check_pyproject(source))
    report.checks.append(check_tests(source))
    report.checks.append(check_ci_pytest(source))
    report.checks.append(check_ruff(source))
    report.checks.append(check_license(source))
    return report


def _first_file(source: RepoSource, names: Sequence[str], directory: str = "") -> Optional[str]:
    matches = source.find_files(names, directory=directory)
    return matches[0] if matches else None


def check_readme(source: RepoSource) -> CheckResult:
    name = "README"
    path = _first_file(source, README_NAMES)
    if path is None:
        return CheckResult(
            id="readme",
            name=name,
            status=STATUS_FAIL,
            detail="no README file at the repository root",
            fix="Add a README.md that explains what the project does, how to install it, and how to use it.",
        )
    text = source.read_text(path) or ""
    stripped = text.strip()
    if _readme_is_trivial(stripped):
        return CheckResult(
            id="readme",
            name=name,
            status=STATUS_FAIL,
            detail="%s is too short or is only a title (%s characters)"
            % (path, len(stripped)),
            fix="Expand %s with a short description, install steps, and usage examples." % path,
        )
    return CheckResult(
        id="readme",
        name=name,
        status=STATUS_PASS,
        detail="%s (%s characters)" % (path, len(stripped)),
    )


def _readme_is_trivial(text: str) -> bool:
    if len(text) < MIN_README_CHARS:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) == 1 and lines[0].startswith("#"):
        return True
    return False


def check_pyproject(source: RepoSource) -> CheckResult:
    name = "pyproject"
    path = _first_file(source, ("pyproject.toml",))
    if path is None:
        return CheckResult(
            id="pyproject",
            name=name,
            status=STATUS_FAIL,
            detail="no pyproject.toml at the repository root",
            fix='Add a pyproject.toml with a [project] table that sets name, version, requires-python, and license, e.g. requires-python = ">=3.8" and license = {text = "MIT"}.',
        )
    text = source.read_text(path) or ""
    data, error = parse_file_text(text)
    if data is None:
        return CheckResult(
            id="pyproject",
            name=name,
            status=STATUS_FAIL,
            detail="could not parse %s: %s" % (path, error),
            fix="Fix the TOML syntax in pyproject.toml, then set [project] name, version, requires-python, and license.",
        )
    project = table(data, "project")
    if not project:
        return CheckResult(
            id="pyproject",
            name=name,
            status=STATUS_FAIL,
            detail="pyproject.toml has no [project] table",
            fix='Add a [project] table to pyproject.toml with name, version, requires-python, and license, e.g. requires-python = ">=3.8" and license = {text = "MIT"}.',
        )
    missing = _missing_project_fields(project)
    if missing:
        return CheckResult(
            id="pyproject",
            name=name,
            status=STATUS_FAIL,
            detail="missing [project] fields: %s" % ", ".join(missing),
            fix=_pyproject_fix(missing),
        )
    extras = []
    extras.append("name=%s" % project.get("name"))
    extras.append("version=%s" % _version_label(project))
    extras.append("requires-python=%s" % project.get("requires-python"))
    extras.append("license=%s" % _license_label(project))
    return CheckResult(
        id="pyproject",
        name=name,
        status=STATUS_PASS,
        detail="%s (%s)" % (path, "; ".join(extras)),
    )


def _missing_project_fields(project: dict) -> List[str]:
    missing: List[str] = []
    name = project.get("name")
    if not isinstance(name, str) or not name.strip():
        missing.append("name")
    if not _has_version(project):
        missing.append("version")
    requires = project.get("requires-python")
    if not isinstance(requires, str) or not requires.strip():
        missing.append("requires-python")
    if not _has_license_field(project):
        missing.append("license")
    return missing


def _has_version(project: dict) -> bool:
    version = project.get("version")
    if isinstance(version, str) and version.strip():
        return True
    dynamic = as_str_list(project.get("dynamic"))
    return "version" in dynamic


def _version_label(project: dict) -> str:
    version = project.get("version")
    if isinstance(version, str) and version.strip():
        return version
    return "dynamic"


def _has_license_field(project: dict) -> bool:
    if project.get("license") not in (None, "", {}, []):
        return True
    files = project.get("license-files")
    return bool(files)


def _license_label(project: dict) -> str:
    license_field = project.get("license")
    if isinstance(license_field, str):
        return license_field
    if isinstance(license_field, dict):
        if license_field.get("text"):
            return str(license_field["text"])
        if license_field.get("file"):
            return "file=%s" % license_field["file"]
    files = as_str_list(project.get("license-files"))
    if files:
        return "files=%s" % ",".join(files)
    return "set"


def _pyproject_fix(missing: Sequence[str]) -> str:
    examples = []
    if "name" in missing:
        examples.append('name = "your-package"')
    if "version" in missing:
        examples.append('version = "0.1.0"')
    if "requires-python" in missing:
        examples.append('requires-python = ">=3.8"')
    if "license" in missing:
        examples.append('license = {text = "MIT"}')
    return "Add %s to the [project] table in pyproject.toml, e.g. %s." % (
        ", ".join(missing),
        "; ".join(examples),
    )


def check_tests(source: RepoSource) -> CheckResult:
    name = "tests"
    test_files = _test_files(source)
    config = _pytest_config(source)
    if test_files:
        locations = ", ".join(_summarize_dirs(test_files))
        extra = "; %s" % config if config else ""
        return CheckResult(
            id="tests",
            name=name,
            status=STATUS_PASS,
            detail="%s test file%s in %s%s"
            % (len(test_files), "" if len(test_files) == 1 else "s", locations, extra),
        )
    if config:
        return CheckResult(
            id="tests",
            name=name,
            status=STATUS_FAIL,
            detail="pytest is configured (%s) but no test_*.py or *_test.py files were found" % config,
            fix="Create a tests/ directory with at least one test_*.py file.",
        )
    return CheckResult(
        id="tests",
        name=name,
        status=STATUS_FAIL,
        detail="no tests/ directory and no pytest configuration",
        fix="Create a tests/ directory with at least one test_*.py file, and add [tool.pytest.ini_options] to pyproject.toml (or a pytest.ini).",
    )


def _test_files(source: RepoSource) -> List[str]:
    found: List[str] = []
    for path in source.list_files():
        lower = path.lower()
        if not lower.endswith(".py"):
            continue
        filename = lower.rsplit("/", 1)[-1]
        if filename.startswith("test_") or filename.endswith("_test.py"):
            found.append(path)
    return found


def _summarize_dirs(paths: Sequence[str]) -> List[str]:
    dirs = []
    seen = set()
    for path in paths:
        directory = path.rsplit("/", 1)[0] if "/" in path else "."
        top = directory.split("/", 1)[0]
        if top not in seen:
            seen.add(top)
            dirs.append(top + "/" if top != "." else ".")
    return dirs


def _pytest_config(source: RepoSource) -> Optional[str]:
    pyproject = _first_file(source, ("pyproject.toml",))
    if pyproject:
        data, _error = parse_file_text(source.read_text(pyproject) or "")
        if data is not None:
            if table(data, "tool", "pytest") or table(data, "tool", "pytest", "ini_options"):
                return "pyproject.toml [tool.pytest]"
    path = _first_file(source, PYTEST_CONFIG_NAMES)
    if path is None:
        return None
    text = source.read_text(path) or ""
    lower_name = path.lower()
    if lower_name.endswith("pytest.ini") or lower_name.endswith("pytest.toml"):
        return path
    if re.search(r"(?m)^\[(pytest|tool:pytest)\]", text):
        return "%s [pytest]" % path
    return None


def check_ci_pytest(source: RepoSource) -> CheckResult:
    name = "CI pytest"
    workflows = _workflow_files(source)
    if not workflows:
        return CheckResult(
            id="ci_pytest",
            name=name,
            status=STATUS_FAIL,
            detail="no GitHub Actions workflow under .github/workflows/",
            fix="Add a GitHub Actions workflow under .github/workflows/ that runs pytest.",
        )
    running = [path for path in workflows if _mentions(source.read_text(path) or "", "pytest")]
    if not running:
        listed = ", ".join(workflows)
        return CheckResult(
            id="ci_pytest",
            name=name,
            status=STATUS_FAIL,
            detail="workflows found (%s) but none run pytest" % listed,
            fix="Add a step that runs pytest to a workflow in .github/workflows/.",
        )
    return CheckResult(
        id="ci_pytest",
        name=name,
        status=STATUS_PASS,
        detail="pytest runs in %s" % ", ".join(running),
    )


def check_ruff(source: RepoSource) -> CheckResult:
    name = "ruff"
    config = _ruff_config(source)
    workflows = _workflow_files(source)
    in_ci = [path for path in workflows if _mentions(source.read_text(path) or "", "ruff")]
    if config and in_ci:
        return CheckResult(
            id="ruff",
            name=name,
            status=STATUS_PASS,
            detail="configured in %s; run in %s" % (config, ", ".join(in_ci)),
        )
    if not config and not in_ci:
        return CheckResult(
            id="ruff",
            name=name,
            status=STATUS_FAIL,
            detail="ruff is not configured and is not run in CI",
            fix="Add [tool.ruff] to pyproject.toml (or a ruff.toml) and a CI step that runs `ruff check`.",
        )
    if not config:
        return CheckResult(
            id="ruff",
            name=name,
            status=STATUS_FAIL,
            detail="ruff runs in %s but no ruff config file or [tool.ruff] table was found"
            % ", ".join(in_ci),
            fix="Add [tool.ruff] to pyproject.toml (or a ruff.toml) so ruff settings are checked in.",
        )
    return CheckResult(
        id="ruff",
        name=name,
        status=STATUS_FAIL,
        detail="ruff is configured in %s but is not run in CI" % config,
        fix="Add a CI step that runs `ruff check` in a workflow under .github/workflows/.",
    )


def _ruff_config(source: RepoSource) -> Optional[str]:
    path = _first_file(source, RUFF_FILENAMES)
    if path:
        return path
    pyproject = _first_file(source, ("pyproject.toml",))
    if pyproject:
        data, _error = parse_file_text(source.read_text(pyproject) or "")
        if data is not None and table(data, "tool", "ruff"):
            return "pyproject.toml [tool.ruff]"
    return None


def check_license(source: RepoSource) -> CheckResult:
    name = "LICENSE"
    path = _first_file(source, LICENSE_NAMES)
    if path is None:
        return CheckResult(
            id="license",
            name=name,
            status=STATUS_FAIL,
            detail="no LICENSE file at the repository root",
            fix="Add a LICENSE file (for example the MIT license text) at the repository root.",
        )
    text = source.read_text(path) or ""
    kind = _license_kind(text)
    detail = "%s (%s)" % (path, kind) if kind else path
    return CheckResult(
        id="license",
        name=name,
        status=STATUS_PASS,
        detail=detail,
    )


def _license_kind(text: str) -> Optional[str]:
    lower = text.lower()
    if "mit license" in lower or (
        "permission is hereby granted, free of charge" in lower and "the software is provided" in lower
    ):
        return "MIT"
    if "apache license" in lower:
        return "Apache"
    if "gnu general public license" in lower:
        return "GPL"
    if "bsd " in lower or "redistribution and use" in lower:
        return "BSD"
    if "creativecommons" in lower or "cc0" in lower:
        return "CC"
    return None


def _workflow_files(source: RepoSource) -> List[str]:
    return source.files_under(WORKFLOW_DIR, suffixes=(".yml", ".yaml"))


def _mentions(text: str, word: str) -> bool:
    return re.search(r"(?i)\b%s\b" % re.escape(word), text) is not None
