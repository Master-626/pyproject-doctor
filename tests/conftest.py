from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def write_tree(tmp_path: Path):
    def _write(tree: dict, root: Path = tmp_path) -> Path:
        for relpath, content in tree.items():
            path = root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    return _write
