"""Command-line interface for pyproject-doctor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence, TextIO

from pyproject_doctor import __version__
from pyproject_doctor.checks import Report, run_checks
from pyproject_doctor.report import render_json, render_text
from pyproject_doctor.sources import (
    GitHubSource,
    LocalSource,
    SourceError,
    github_token_from_env,
    parse_github_spec,
)

EXIT_OK = 0
EXIT_CHECKS = 1
EXIT_ERROR = 2


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Console script entry point."""
    sys.exit(run(argv))


def run(argv: Optional[Sequence[str]] = None, stdout: Optional[TextIO] = None, stderr: Optional[TextIO] = None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else EXIT_ERROR

    try:
        report = _scan(args)
    except SourceError as exc:
        err.write("error: %s\n" % exc)
        return EXIT_ERROR

    if args.json:
        out.write(render_json(report))
    else:
        out.write(render_text(report))

    if _should_fail(report, args.fail_under, args.strict):
        return EXIT_CHECKS
    return EXIT_OK


def _scan(args: argparse.Namespace) -> Report:
    if args.github:
        if args.path is not None:
            raise SourceError("pass either a local path or --github, not both")
        owner, repo = parse_github_spec(args.github)
        source = GitHubSource(owner, repo, token=github_token_from_env())
        return run_checks(source)
    root = Path(args.path) if args.path is not None else Path(".")
    return run_checks(LocalSource(root))


def _should_fail(report: Report, fail_under: Optional[int], strict: bool) -> bool:
    if fail_under is not None:
        return report.passed < fail_under
    # --strict is the default policy (any failed check is a non-zero exit).
    # It is kept as an explicit flag so scripts can opt into that behavior
    # even if the default later grows a warning status.
    if strict or fail_under is None:
        return not report.ok
    return not report.ok


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyproject-doctor",
        description=(
            "Check a small Python repo for README, pyproject.toml, tests, "
            "ruff/pytest CI, a LICENSE file, and a Python .gitignore, "
            "and suggest one-line fixes."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="local repository path (default: current directory)",
    )
    parser.add_argument(
        "--github",
        metavar="OWNER/NAME",
        help="scan a public GitHub repository (no token required; uses the public API)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the report as JSON",
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        metavar="N",
        default=None,
        help="exit 1 if fewer than N checks pass (default: fail when any check fails)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when any check fails (the default when --fail-under is not set)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="pyproject-doctor %s" % __version__,
    )
    return parser
