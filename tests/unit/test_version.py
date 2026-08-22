"""Resolving the running revision without shelling out to git.

The point of this is deploy verification, so the failure that matters is
returning *something plausible but wrong* — a stale sha, or a sha from a
different tree. Returning nothing is fine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.version import read_commit

SHA = "b969b2c9d78c77a011f966a7231823993615b729"
OTHER = "0123456789abcdef0123456789abcdef01234567"


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_a_checked_out_branch_resolves_through_its_loose_ref(tmp_path):
    root = _repo(tmp_path)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / ".git" / "refs" / "heads").mkdir(parents=True)
    (root / ".git" / "refs" / "heads" / "main").write_text(SHA + "\n")
    assert read_commit(root) == SHA


def test_a_packed_ref_resolves_too(tmp_path):
    """A freshly cloned repo has no loose refs at all."""
    root = _repo(tmp_path)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / ".git" / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        f"{OTHER} refs/heads/otra\n"
        f"{SHA} refs/heads/main\n"
        f"^{OTHER}\n"
    )
    assert read_commit(root) == SHA


def test_a_detached_head_is_the_sha_itself(tmp_path):
    root = _repo(tmp_path)
    (root / ".git" / "HEAD").write_text(SHA + "\n")
    assert read_commit(root) == SHA


def test_a_worktree_follows_its_gitdir_pointer(tmp_path):
    """In a worktree ``.git`` is a file, not a directory."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "HEAD").write_text(SHA + "\n")
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / ".git").write_text(f"gitdir: {real}\n")
    assert read_commit(tree) == SHA


def test_no_git_at_all_is_none_not_an_error(tmp_path):
    """A source tarball is a legitimate deployment; the probe must not
    500 because of it."""
    assert read_commit(tmp_path) is None


@pytest.mark.parametrize(
    "head",
    [
        "ref: refs/heads/desaparecida\n",  # ref points nowhere
        "no-es-un-sha\n",
        "",
    ],
)
def test_anything_unresolvable_is_none_never_a_guess(tmp_path, head):
    root = _repo(tmp_path)
    (root / ".git" / "HEAD").write_text(head)
    assert read_commit(root) is None


def test_a_truncated_sha_is_rejected(tmp_path):
    """Half a sha would compare unequal to the deployed one and send
    someone hunting a deploy problem that isn't there."""
    root = _repo(tmp_path)
    (root / ".git" / "HEAD").write_text(SHA[:20] + "\n")
    assert read_commit(root) is None
