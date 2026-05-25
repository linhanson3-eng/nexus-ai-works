from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from factory.worktree.manager import WorktreeManager, _assign_port


class TestPortAssignment:
    def test_deterministic(self):
        assert _assign_port("workshop/demo") == _assign_port("workshop/demo")

    def test_different_branches(self):
        p1 = _assign_port("workshop/a")
        p2 = _assign_port("workshop/b")
        assert p1 != p2

    def test_port_in_range(self):
        p = _assign_port("workshop/test")
        assert 3000 <= p <= 3999


class TestWorktreeManager:
    @pytest.fixture
    def bare_repo(self):
        """Create a temporary bare git repo with initial commit for testing."""
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "bare.git"
            # First create a normal repo with initial commit, then clone as bare
            tmp = Path(td) / "tmp"
            tmp.mkdir()
            subprocess.run(["git", "-C", str(tmp), "init"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(tmp), "commit", "--allow-empty", "-m", "init"],
                check=True, capture_output=True,
                env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test", "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test"},
            )
            subprocess.run(
                ["git", "clone", "--bare", str(tmp), str(repo)],
                check=True, capture_output=True,
            )
            yield repo

    @pytest.fixture
    def worktree_root(self):
        with tempfile.TemporaryDirectory() as td:
            yield Path(td) / "worktrees"

    def test_create_and_list_worktree(self, bare_repo, worktree_root):
        mgr = WorktreeManager(
            repo_path=str(bare_repo),
            worktree_root=str(worktree_root),
        )
        wt_path = mgr.create("test-workshop")
        assert wt_path.exists()

        trees = mgr.list_all()
        assert any("test-workshop" in t["name"] for t in trees)

        mgr.remove("test-workshop")
        assert not wt_path.exists()

    def test_remove_nonexistent(self, bare_repo, worktree_root):
        mgr = WorktreeManager(
            repo_path=str(bare_repo),
            worktree_root=str(worktree_root),
        )
        mgr.remove("nonexistent")  # Should not raise

    def test_missing_repo_path_raises(self):
        with pytest.raises(RuntimeError, match="repo_path"):
            WorktreeManager(repo_path="", worktree_root="/tmp/nonexistent")
