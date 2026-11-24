"""Local and GitHub repository views used by the checks."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from pyproject_doctor import __version__

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
}

USER_AGENT = "pyproject-doctor/%s (+https://github.com/Master-626/pyproject-doctor)" % __version__
API_VERSION = "2022-11-28"
DEFAULT_API = "https://api.github.com"


class SourceError(Exception):
    """The repository could not be read."""


class RepoSource:
    """A read-only view of a repository tree."""

    def label(self) -> str:
        raise NotImplementedError

    def list_files(self) -> List[str]:
        raise NotImplementedError

    def read_text(self, relpath: str) -> Optional[str]:
        raise NotImplementedError

    def find_files(self, names: Sequence[str], directory: str = "") -> List[str]:
        """Return matching paths, case-insensitive, optionally limited to a directory."""
        wanted = {name.lower() for name in names}
        prefix = directory.rstrip("/") + "/" if directory else ""
        matches = []
        for path in self.list_files():
            if prefix:
                if not path.lower().startswith(prefix.lower()):
                    continue
                rest = path[len(prefix) :]
                if "/" in rest:
                    continue
                if rest.lower() in wanted:
                    matches.append(path)
            else:
                if "/" in path:
                    continue
                if path.split("/")[-1].lower() in wanted:
                    matches.append(path)
        return matches

    def files_under(self, directory: str, suffixes: Optional[Sequence[str]] = None) -> List[str]:
        prefix = directory.rstrip("/") + "/"
        suffix_set = {item.lower() for item in suffixes} if suffixes else None
        found = []
        for path in self.list_files():
            if not path.replace("\\", "/").startswith(prefix) and path != directory.rstrip("/"):
                # also accept case-insensitive directory prefix
                lower = path.lower()
                if not lower.startswith(prefix.lower()):
                    continue
            if suffix_set is not None and not any(path.lower().endswith(s) for s in suffix_set):
                continue
            found.append(path)
        return found


class LocalSource(RepoSource):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise SourceError("not a directory: %s" % root)
        self._files: Optional[List[str]] = None

    def label(self) -> str:
        return str(self.root)

    def list_files(self) -> List[str]:
        if self._files is not None:
            return self._files
        files: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [
                name
                for name in dirnames
                if name not in SKIP_DIR_NAMES and not name.endswith(".egg-info")
            ]
            for filename in filenames:
                full = Path(dirpath) / filename
                rel = full.relative_to(self.root).as_posix()
                files.append(rel)
        self._files = sorted(files)
        return self._files

    def read_text(self, relpath: str) -> Optional[str]:
        path = self.root / relpath
        if not path.is_file():
            # try case-insensitive match among listed files
            matches = [item for item in self.list_files() if item.lower() == relpath.lower()]
            if not matches:
                return None
            path = self.root / matches[0]
            if not path.is_file():
                return None
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise SourceError("could not read %s: %s" % (path, exc)) from exc


class GitHubSource(RepoSource):
    def __init__(
        self,
        owner: str,
        repo: str,
        token: Optional[str] = None,
        api_base: str = DEFAULT_API,
        opener=None,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self.api_base = api_base.rstrip("/")
        self._opener = opener or urllib.request.urlopen
        self._files: Optional[List[str]] = None
        self._sha_by_path: Dict[str, str] = {}
        self._cache: Dict[str, str] = {}
        self.default_branch = ""
        self._load_tree()

    def label(self) -> str:
        label = "%s/%s" % (self.owner, self.repo)
        if self.default_branch:
            return "%s@%s" % (label, self.default_branch)
        return label

    def list_files(self) -> List[str]:
        return list(self._files or [])

    def read_text(self, relpath: str) -> Optional[str]:
        if relpath in self._cache:
            return self._cache[relpath]
        matches = [item for item in self.list_files() if item.lower() == relpath.lower()]
        if not matches:
            return None
        path = matches[0]
        if path in self._cache:
            return self._cache[path]
        url = "%s/repos/%s/%s/contents/%s" % (
            self.api_base,
            self.owner,
            self.repo,
            urllib.parse.quote(path, safe="/"),
        )
        if self.default_branch:
            url += "?ref=%s" % _quote_ref(self.default_branch)
        data = self._request(url, accept="application/vnd.github.raw")
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        else:
            text = data
        self._cache[path] = text
        return text

    def _load_tree(self) -> None:
        meta = self._request_json("%s/repos/%s/%s" % (self.api_base, self.owner, self.repo))
        self.default_branch = str(meta.get("default_branch") or "main")
        tree = self._request_json(
            "%s/repos/%s/%s/git/trees/%s?recursive=1"
            % (
                self.api_base,
                self.owner,
                self.repo,
                _quote_ref(self.default_branch),
            )
        )
        if tree.get("truncated"):
            raise SourceError(
                "GitHub file list for %s/%s is truncated; clone the repository and scan the local directory"
                % (self.owner, self.repo)
            )
        files: List[str] = []
        for entry in tree.get("tree") or []:
            if entry.get("type") != "blob":
                continue
            path = entry.get("path")
            if not path:
                continue
            parts = path.split("/")
            if any(part in SKIP_DIR_NAMES or part.endswith(".egg-info") for part in parts[:-1]):
                continue
            files.append(path)
            if entry.get("sha"):
                self._sha_by_path[path] = entry["sha"]
        self._files = sorted(files)

    def _request_json(self, url: str) -> dict:
        raw = self._request(url, accept="application/vnd.github+json")
        if isinstance(raw, bytes):
            return json.loads(raw.decode("utf-8"))
        if isinstance(raw, str):
            return json.loads(raw)
        raise SourceError("unexpected GitHub response")

    def _request(self, url: str, accept: str) -> bytes:
        headers = {
            "Accept": accept,
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        }
        token = self.token
        if token:
            headers["Authorization"] = "Bearer %s" % token
        request = urllib.request.Request(url, headers=headers)
        try:
            with self._opener(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001
                body = b""
            detail = _http_error_detail(exc.code, body)
            raise SourceError(
                "GitHub API error for %s/%s: %s" % (self.owner, self.repo, detail)
            ) from exc
        except urllib.error.URLError as exc:
            raise SourceError("could not reach GitHub: %s" % exc.reason) from exc


def _http_error_detail(code: int, body: bytes) -> str:
    message = ""
    try:
        payload = json.loads(body.decode("utf-8"))
        message = str(payload.get("message") or "")
    except Exception:  # noqa: BLE001
        message = body.decode("utf-8", errors="replace")[:200]
    if code == 404:
        return "repository not found (it may be private, or the name is wrong)"
    if code == 403 and "rate limit" in message.lower():
        return "API rate limit exceeded; set GITHUB_TOKEN and try again"
    if message:
        return "HTTP %s: %s" % (code, message)
    return "HTTP %s" % code


_GITHUB_HTTP_PREFIXES = (
    "https://github.com/",
    "http://github.com/",
    "https://www.github.com/",
    "http://www.github.com/",
    "github.com/",
    "www.github.com/",
)


def _quote_ref(ref: str) -> str:
    """Percent-encode a Git ref, including slashes (``release/1.0`` -> ``release%2F1.0``)."""
    return urllib.parse.quote(ref, safe="")


def parse_github_spec(spec: str) -> tuple:
    text = spec.strip()
    lower = text.lower()
    recognized = False
    if lower.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
        recognized = True
    elif lower.startswith("ssh://git@github.com/"):
        text = text[len("ssh://git@github.com/") :]
        recognized = True
    elif lower.startswith("ssh://git@github.com:"):
        text = text[len("ssh://git@github.com:") :]
        recognized = True
    else:
        for prefix in _GITHUB_HTTP_PREFIXES:
            if lower.startswith(prefix):
                text = text[len(prefix) :]
                recognized = True
                break
    if not recognized and ("://" in lower or lower.startswith("git@")):
        raise SourceError("expected a GitHub repo of the form owner/name, got %r" % spec)
    text = text.split("?", 1)[0].split("#", 1)[0].strip().strip("/")
    if text.lower().endswith(".git"):
        text = text[: -len(".git")]
    parts = [part for part in text.split("/") if part]
    if len(parts) < 2:
        raise SourceError("expected a GitHub repo of the form owner/name, got %r" % spec)
    owner, repo = parts[0], parts[1]
    if any(char in owner + repo for char in " :?#"):
        raise SourceError("expected a GitHub repo of the form owner/name, got %r" % spec)
    return owner, repo


def github_token_from_env(env: Optional[Iterable] = None) -> Optional[str]:
    mapping = os.environ if env is None else env  # type: ignore[assignment]
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = mapping.get(key) if hasattr(mapping, "get") else None
        if value:
            return str(value)
    return None
