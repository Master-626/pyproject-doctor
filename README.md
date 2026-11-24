# pyproject-doctor

Zero-dependency CLI that checks small Python repositories for a README, a complete `pyproject.toml`, tests, ruff/pytest CI, a LICENSE file, and a Python `.gitignore`, and prints a one-line fix for each failing check.

It only reads a local directory or the public GitHub API (optional `GITHUB_TOKEN`). There are no runtime dependencies.

**中文简介：** pyproject-doctor 是一个零依赖的命令行工具，用来检查小型 Python 仓库是否具备 README、完整的 `pyproject.toml`、测试、会运行 ruff 与 pytest 的 GitHub Actions、LICENSE，以及会忽略 Python 缓存的 `.gitignore`。每一项失败都会附带一行修复建议。它只读取本地目录，或通过公开的 GitHub API 读取远程仓库（可选环境变量 `GITHUB_TOKEN`）。

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

# Exit 0 when at least 6 of the 7 checks pass
pyproject-doctor --fail-under 6
```

Set `GITHUB_TOKEN` (or `GH_TOKEN`) if you hit the unauthenticated GitHub API rate limit.

## Checks

| Check | Passes when |
| --- | --- |
| `readme` | A README exists at the repo root and is more than a title |
| `pyproject` | `pyproject.toml` has `[project]` `name`, `version` (or `dynamic = ["version"]`), `requires-python`, and `license` (or `license-files`) |
| `tests` | At least one `test_*.py` / `*_test.py` file is present |
| `ci_pytest` | A workflow file directly in `.github/workflows/` runs `pytest` |
| `ruff` | Ruff is configured (`[tool.ruff]`, `ruff.toml`, or `.ruff.toml`) and a workflow file directly in `.github/workflows/` runs it |
| `license` | A `LICENSE` (or `LICENCE` / `COPYING`) file exists at the repo root |
| `gitignore` | A root `.gitignore` ignores Python bytecode, a virtualenv, egg-info, or a tool cache such as `.pytest_cache` |

## Example output

Scanning a repo that is missing a license and ruff in CI:

```text
Target: /tmp/example

  STATUS  CHECK       DETAIL
  ------  ----------  -----------------------------------------------------------------------------
  pass    README      README.md (146 characters)
  pass    pyproject   pyproject.toml (name=demo; version=0.1.0; requires-python=>=3.8; license=MIT)
  pass    tests       1 test file in tests/
  pass    CI pytest   pytest runs in .github/workflows/ci.yml
  fail    ruff        ruff is configured in pyproject.toml [tool.ruff] but is not run in CI
  fail    LICENSE     no LICENSE file at the repository root
  pass    .gitignore  .gitignore ignores Python artifacts

5 passed, 2 failed

Suggested fixes:
  ruff        Add a CI step that runs `ruff check` in a workflow under .github/workflows/.
  license     Add a LICENSE file (for example the MIT license text) at the repository root.
```

The process exits with code `1` when any check fails, or when fewer than `N` checks pass if you set `--fail-under N`. Usage and network errors exit with code `2`.

`--json` prints the same report as a JSON object with `target`, `passed`, `failed`, `total`, `ok`, and a `checks` array (`id`, `name`, `status`, `detail`, `fix`).

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

The package has no runtime dependencies. On Python 3.11 and newer, TOML is parsed with the standard library. Python 3.8-3.10 use the fallback parser in `src/pyproject_doctor/toml_util.py`.

## License

MIT
