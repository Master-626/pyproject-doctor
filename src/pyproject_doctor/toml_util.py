"""Parse TOML with the stdlib when available, else a small subset parser."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

TomlValue = Any


class TomlParseError(ValueError):
    """The document is not valid TOML (or not in the supported subset)."""


def loads(text: str) -> dict:
    """Parse a TOML document into a dict.

    Uses :mod:`tomllib` on Python 3.11+ and a built-in subset parser on
    older versions so the tool stays free of runtime dependencies.
    """
    try:
        import tomllib
    except ImportError:
        return _FallbackParser(text).parse()
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise TomlParseError(str(exc)) from exc


def table(data: dict, *path: str) -> dict:
    """Return a nested table, or an empty dict if any segment is missing."""
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return {}
        current = current[key]
    return current if isinstance(current, dict) else {}


def as_str_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str):
        return [value]
    return []


class _FallbackParser:
    """A compact TOML parser covering the subset common in pyproject.toml."""

    def __init__(self, text: str) -> None:
        self.s = text
        self.n = len(text)
        self.i = 0
        self.root: dict = {}
        self.current: dict = self.root

    def parse(self) -> dict:
        try:
            while self.i < self.n:
                self._skip_ws_and_comments()
                if self.i >= self.n:
                    break
                if self.s[self.i] == "[":
                    self._parse_table_header()
                else:
                    self._parse_key_value(self.current)
            return self.root
        except TomlParseError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface as a parse error
            raise TomlParseError("invalid TOML: %s" % exc) from exc

    def _peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def _advance(self) -> str:
        ch = self.s[self.i]
        self.i += 1
        return ch

    def _skip_ws_and_comments(self) -> None:
        while self.i < self.n:
            ch = self.s[self.i]
            if ch in " \t\r\n":
                self.i += 1
                continue
            if ch == "#":
                while self.i < self.n and self.s[self.i] not in "\r\n":
                    self.i += 1
                continue
            break

    def _skip_space(self) -> None:
        while self.i < self.n and self.s[self.i] in " \t":
            self.i += 1

    def _parse_table_header(self) -> None:
        self._advance()  # [
        array = False
        if self._peek() == "[":
            array = True
            self._advance()
        self._skip_space()
        keys = self._parse_key_path()
        self._skip_space()
        if array:
            if self._peek() != "]":
                raise TomlParseError("expected ]]")
            self._advance()
        if self._peek() != "]":
            raise TomlParseError("expected ] after table name")
        self._advance()
        target = self._ensure_table(keys, array=array)
        self.current = target

    def _ensure_table(self, keys: List[str], array: bool = False) -> dict:
        node: dict = self.root
        for index, key in enumerate(keys):
            last = index == len(keys) - 1
            if last and array:
                existing = node.get(key)
                if existing is None:
                    table = {}
                    node[key] = [table]
                    return table
                if not isinstance(existing, list):
                    raise TomlParseError("table/array conflict at %s" % ".".join(keys))
                table = {}
                existing.append(table)
                return table
            existing = node.get(key)
            if existing is None:
                nxt: dict = {}
                node[key] = nxt
                node = nxt
                continue
            if isinstance(existing, list):
                if not existing or not isinstance(existing[-1], dict):
                    raise TomlParseError("table/array conflict at %s" % ".".join(keys))
                node = existing[-1]
                continue
            if not isinstance(existing, dict):
                raise TomlParseError("table/value conflict at %s" % ".".join(keys))
            node = existing
        return node

    def _parse_key_value(self, target: dict) -> None:
        keys = self._parse_key_path()
        self._skip_space()
        if self._peek() != "=":
            raise TomlParseError("expected '=' after key")
        self._advance()
        self._skip_space()
        value = self._parse_value()
        node = target
        for key in keys[:-1]:
            existing = node.get(key)
            if existing is None:
                existing = {}
                node[key] = existing
            if not isinstance(existing, dict):
                raise TomlParseError("dotted key conflict")
            node = existing
        node[keys[-1]] = value

    def _parse_key_path(self) -> List[str]:
        keys = [self._parse_key()]
        self._skip_space()
        while self._peek() == ".":
            self._advance()
            self._skip_space()
            keys.append(self._parse_key())
            self._skip_space()
        return keys

    def _parse_key(self) -> str:
        ch = self._peek()
        if ch in ("'", '"'):
            value = self._parse_value()
            if not isinstance(value, str):
                raise TomlParseError("expected string key")
            return value
        start = self.i
        while self.i < self.n and (self.s[self.i].isalnum() or self.s[self.i] in "_-"):
            self.i += 1
        if self.i == start:
            raise TomlParseError("expected key")
        return self.s[start : self.i]

    def _parse_value(self) -> TomlValue:
        ch = self._peek()
        if ch == '"':
            return self._parse_basic_string()
        if ch == "'":
            return self._parse_literal_string()
        if ch == "[":
            return self._parse_array()
        if ch == "{":
            return self._parse_inline_table()
        if ch.isdigit() or ch in "+-":
            return self._parse_number()
        ident = self._parse_bare_ident()
        if ident == "true":
            return True
        if ident == "false":
            return False
        if ident in ("inf", "+inf", "nan", "+nan", "-inf", "-nan"):
            return float(ident)
        raise TomlParseError("unexpected value starting with %r" % ident)

    def _parse_bare_ident(self) -> str:
        start = self.i
        while self.i < self.n and (self.s[self.i].isalnum() or self.s[self.i] in "_+-."):
            self.i += 1
        return self.s[start : self.i]

    def _parse_number(self) -> Any:
        start = self.i
        if self._peek() in "+-":
            self.i += 1
        while self.i < self.n and (self.s[self.i].isdigit() or self.s[self.i] in "._xXbBoOabcdefABCDEF"):
            self.i += 1
        raw = self.s[start : self.i].replace("_", "")
        if any(c in raw for c in ".eE") and not raw.lower().startswith(("0x", "0o", "0b")):
            return float(raw)
        if raw.lower().startswith("0x"):
            return int(raw, 16)
        if raw.lower().startswith("0o"):
            return int(raw, 8)
        if raw.lower().startswith("0b"):
            return int(raw, 2)
        return int(raw)

    def _parse_array(self) -> list:
        self._advance()  # [
        items: list = []
        while True:
            self._skip_ws_and_comments()
            if self._peek() == "]":
                self._advance()
                return items
            items.append(self._parse_value())
            self._skip_ws_and_comments()
            if self._peek() == ",":
                self._advance()
                continue
            if self._peek() == "]":
                self._advance()
                return items
            raise TomlParseError("expected ',' or ']' in array")

    def _parse_inline_table(self) -> dict:
        self._advance()  # {
        table: dict = {}
        self._skip_space()
        if self._peek() == "}":
            self._advance()
            return table
        while True:
            self._skip_space()
            self._parse_key_value(table)
            self._skip_space()
            if self._peek() == ",":
                self._advance()
                continue
            if self._peek() == "}":
                self._advance()
                return table
            raise TomlParseError("expected ',' or '}' in inline table")

    def _parse_basic_string(self) -> str:
        self._advance()  # "
        if self.s[self.i : self.i + 2] == '""':
            self.i += 2
            return self._parse_multiline_basic()
        out: List[str] = []
        while self.i < self.n:
            ch = self._advance()
            if ch == '"':
                return "".join(out)
            if ch == "\\":
                out.append(self._escape())
                continue
            if ch in "\r\n":
                raise TomlParseError("newline in basic string")
            out.append(ch)
        raise TomlParseError("unterminated string")

    def _parse_multiline_basic(self) -> str:
        if self._peek() == "\n":
            self._advance()
        elif self.s[self.i : self.i + 2] == "\r\n":
            self.i += 2
        out: List[str] = []
        while self.i < self.n:
            if self.s[self.i : self.i + 3] == '"""':
                self.i += 3
                return "".join(out)
            ch = self._advance()
            if ch == "\\":
                self._skip_space()
                if self._peek() in "\r\n":
                    while self.i < self.n and self.s[self.i] in " \t\r\n":
                        self.i += 1
                    continue
                out.append(self._escape())
                continue
            out.append(ch)
        raise TomlParseError("unterminated multiline string")

    def _parse_literal_string(self) -> str:
        self._advance()  # '
        if self.s[self.i : self.i + 2] == "''":
            self.i += 2
            if self._peek() == "\n":
                self._advance()
            elif self.s[self.i : self.i + 2] == "\r\n":
                self.i += 2
            end = self.s.find("'''", self.i)
            if end < 0:
                raise TomlParseError("unterminated multiline literal string")
            value = self.s[self.i : end]
            self.i = end + 3
            return value
        end = self.s.find("'", self.i)
        if end < 0:
            raise TomlParseError("unterminated literal string")
        value = self.s[self.i : end]
        if "\n" in value:
            raise TomlParseError("newline in literal string")
        self.i = end + 1
        return value

    def _escape(self) -> str:
        if self.i >= self.n:
            raise TomlParseError("unterminated escape")
        ch = self._advance()
        mapping = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r", '"': '"', "\\": "\\"}
        if ch in mapping:
            return mapping[ch]
        if ch == "u":
            return chr(int(self._take(4), 16))
        if ch == "U":
            return chr(int(self._take(8), 16))
        raise TomlParseError("unknown escape \\%s" % ch)

    def _take(self, count: int) -> str:
        chunk = self.s[self.i : self.i + count]
        if len(chunk) != count:
            raise TomlParseError("truncated unicode escape")
        self.i += count
        return chunk


def parse_file_text(text: str) -> Tuple[Optional[dict], Optional[str]]:
    """Return (data, error_message)."""
    try:
        return loads(text), None
    except TomlParseError as exc:
        return None, str(exc)
