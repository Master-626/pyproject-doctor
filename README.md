# pyproject-doctor

Zero-dependency CLI that checks small Python repositories for a README, a complete `pyproject.toml`, tests, ruff/pytest CI, and a LICENSE file, and prints a one-line fix for each failing check.

It only reads a local directory or the public GitHub API (optional `GITHUB_TOKEN`). There are no runtime dependencies.

## Install

From a clone:

```bash
pip install .
```

Or directly from GitHub:

```bash
pip install git+https://github.com/Master-626/pyproject-doctor.git
```

Python 3.8 or newer is required.

## Usage

```bash
# Scan the current directory
pyproject-doctor

# Scan a local path
pyproject-doctor path/to/repo

# Scan a public GitHub repository (no token required)
pyproject-doctor --github Master-626/pyproject-doctor

# Machine-readable output
pyproject-doctor --json

# Exit 0 if at least 5 checks pass
pyproject-doctor --fail-under 5
```

Set `GITHUB_TOKEN` (or `GH_TOKEN`) if you hit the unauthenticated GitHub API rate limit.

## Checks

| Check | Passes when |
| --- | --- |
| `readme` | A README exists at the repo root and is more than a title |
| `pyproject` | `pyproject.toml` has `[project]` `name`, `version` (or `dynamic = ["version"]`), `requires-python`, and `license` (or `license-files`) |
| `tests` | At least one `test_*.py` / `*_test.py` file is present |
| `ci_pytest` | A workflow under `.github/workflows/` runs `pytest` |
| `ruff` | Ruff is configured (`[tool.ruff]`, `ruff.toml`, or `.ruff.toml`) and is run in CI |
| `license` | A `LICENSE` (or `LICENCE` / `COPYING`) file exists at the repo root |

## Example output

Scanning a repo that is missing a license and ruff in CI:

```text
Target: /tmp/example

  STATUS  CHECK      DETAIL
  ------  ---------  ----------------------------------------------------------
  pass    README     README.md (214 characters)
  pass    pyproject  pyproject.toml (name=demo; version=0.1.0; requires-python=>=3.8; license=MIT)
  pass    tests      1 test file in tests/
  pass    CI pytest  pytest runs in .github/workflows/ci.yml
  fail    ruff       ruff is configured in pyproject.toml [tool.ruff] but is not run in CI
  fail    LICENSE    no LICENSE file at the repository root

4 passed, 2 failed

Suggested fixes:
  ruff        Add a CI step that runs `ruff check` in a workflow under .github/workflows/.
  license     Add a LICENSE file (for example the MIT license text) at the repository root.
```

The process exits with code `1` when any check fails, or when fewer than `N` checks pass if you set `--fail-under N`. Usage and network errors exit with code `2`.

`--json` prints the same report as a JSON object with `target`, `passed`, `failed`, `ok`, and a `checks` array (`id`, `name`, `status`, `detail`, `fix`).

## License

MIT
