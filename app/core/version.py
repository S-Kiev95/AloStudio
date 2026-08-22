"""Which revision is this process running.

Exists because "did the deploy take?" was, until now, a deduction: you
compared a ``git pull`` in one terminal against a process you could not
interrogate. On 2026-08-22 two commits sat on disk for half an hour
while being reported as live, and the check that was supposed to catch
it ran the code in a *separate* Python process — which reads the file
from disk and proves nothing about what is serving traffic.

Resolution order:

1. ``APP_GIT_COMMIT`` in the environment — set it in an image build,
   where there is no working tree to read.
2. The working tree's ``.git``, read directly. No subprocess, so it
   works in a container that ships the repo without the git binary.

Returns ``None`` when neither is available, which is a legitimate state
(a source tarball) and must not break the health probe.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_HEX = set("0123456789abcdef")


def _looks_like_sha(value: str) -> bool:
    return len(value) == 40 and set(value.lower()) <= _HEX


def _git_dir(root: Path) -> Path | None:
    """``root/.git``, following the ``gitdir:`` indirection a worktree or
    submodule uses."""
    candidate = root / ".git"
    if candidate.is_dir():
        return candidate
    if candidate.is_file():
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text.startswith("gitdir:"):
            target = Path(text.split(":", 1)[1].strip())
            if not target.is_absolute():
                target = (root / target).resolve()
            return target if target.is_dir() else None
    return None


def _resolve_ref(git_dir: Path, ref: str) -> str | None:
    """A ref's sha, whether it is a loose file or packed."""
    loose = git_dir / ref
    if loose.is_file():
        value = loose.read_text(encoding="utf-8").strip()
        return value if _looks_like_sha(value) else None

    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.startswith(("#", "^")):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip() == ref:
                return parts[0] if _looks_like_sha(parts[0]) else None
    return None


def read_commit(root: Path) -> str | None:
    """The checked-out revision of the tree at ``root``, or None."""
    git_dir = _git_dir(root)
    if git_dir is None:
        return None
    head = git_dir / "HEAD"
    if not head.is_file():
        return None
    try:
        content = head.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if content.startswith("ref:"):
        return _resolve_ref(git_dir, content.split(":", 1)[1].strip())
    return content if _looks_like_sha(content) else None


@lru_cache(maxsize=1)
def git_commit() -> str | None:
    """The running revision. Resolved once — it cannot change under a
    live process, and that is exactly the point."""
    from_env = os.environ.get("APP_GIT_COMMIT", "").strip()
    if from_env:
        return from_env
    try:
        return read_commit(Path(__file__).resolve().parents[2])
    except OSError:
        return None


def short_commit() -> str | None:
    """The first 12 characters — what a person compares against
    ``git log --oneline``."""
    full = git_commit()
    return full[:12] if full else None


__all__ = ["git_commit", "read_commit", "short_commit"]
