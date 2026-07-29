"""Filesystem tool — every operation is hard-scoped to a single workspace root.

Path traversal (``..``, absolute escapes, symlink escapes) is rejected. Agents
receive a :class:`Workspace` bound to ``workspaces/<run-id>/`` and can only touch
files beneath it.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(RuntimeError):
    """Raised on any attempt to escape the workspace root."""


@dataclass
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ── path safety ───────────────────────────────────────────────────
    def resolve(self, rel: str | os.PathLike) -> Path:
        """Resolve ``rel`` under the root, rejecting anything that escapes it."""
        candidate = (self.root / Path(rel)).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise WorkspaceError(f"path escapes workspace: {rel!r}")
        return candidate

    # ── reads ─────────────────────────────────────────────────────────
    def read(self, rel: str) -> str:
        return self.resolve(rel).read_text(encoding="utf-8")

    def exists(self, rel: str) -> bool:
        try:
            return self.resolve(rel).exists()
        except WorkspaceError:
            return False

    def glob(self, pattern: str) -> list[str]:
        """Return workspace-relative paths matching a glob (recursive with **)."""
        out: list[str] = []
        for p in self.root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.root).as_posix()
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(p.name, pattern):
                    out.append(rel)
        return sorted(out)

    def grep(self, pattern: str, *, glob: str = "*") -> list[tuple[str, int, str]]:
        """Return (relpath, lineno, line) for regex matches across matching files."""
        rx = re.compile(pattern)
        hits: list[tuple[str, int, str]] = []
        for rel in self.glob(glob):
            try:
                text = self.read(rel)
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    hits.append((rel, i, line))
        return hits

    def tree(self, *, max_entries: int = 400) -> list[str]:
        """A flat listing of files (for handing context to an agent)."""
        rels = [
            p.relative_to(self.root).as_posix()
            for p in self.root.rglob("*")
            if p.is_file() and "node_modules/" not in p.as_posix() and "/.git/" not in p.as_posix()
        ]
        return sorted(rels)[:max_entries]

    # ── writes ────────────────────────────────────────────────────────
    def write(self, rel: str, content: str) -> Path:
        path = self.resolve(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit(self, rel: str, old: str, new: str, *, count: int = 1) -> None:
        """Exact-substring replacement (like the harness's own Edit tool)."""
        text = self.read(rel)
        occurrences = text.count(old)
        if occurrences == 0:
            raise WorkspaceError(f"edit: pattern not found in {rel!r}")
        if count == 1 and occurrences > 1:
            raise WorkspaceError(
                f"edit: pattern not unique in {rel!r} ({occurrences} matches); pass count=-1 to replace all"
            )
        self.write(rel, text.replace(old, new, -1 if count == -1 else count))

    def mkdir(self, rel: str) -> Path:
        path = self.resolve(rel)
        path.mkdir(parents=True, exist_ok=True)
        return path
