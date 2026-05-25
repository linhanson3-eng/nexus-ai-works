from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _assign_port(branch: str, base: int = 3000, pool_size: int = 1000) -> int:
    """Deterministic port from branch name hash. Agor-style: hash % pool + base."""
    h = hashlib.sha256(branch.encode()).digest()
    num = int.from_bytes(h[:4], "big")
    return (num % pool_size) + base


class WorktreeManager:
    """Manage git worktrees as isolated workshop execution units.

    Each workshop = one git worktree = one branch + directory + unique port.
    """

    def __init__(
        self,
        repo_path: str = "",
        worktree_root: str | Path = "~/.factory/worktrees",
    ):
        self._repo = repo_path or os.environ.get(
            "NX_REPO_PATH",
            os.environ.get("NX_WORKSPACE_ROOT", ""),
        )
        if not self._repo:
            raise RuntimeError(
                "WorktreeManager requires repo_path or NX_REPO_PATH/NX_WORKSPACE_ROOT env var"
            )
        self._root = Path(worktree_root).expanduser().resolve()

    def _git(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a git command with timeout to prevent indefinite blocking."""
        cmd = ["git", "-C", self._repo] + list(args)
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Git command timed out after {timeout}s: {' '.join(cmd)}")

    def create(self, workshop_name: str) -> Path:
        branch = f"workshop/{workshop_name}"
        wt_id = f"wt-{workshop_name}"
        target = self._root / wt_id

        self._root.mkdir(parents=True, exist_ok=True)

        result = self._git("worktree", "add", str(target), "-b", branch)
        if result.returncode != 0:
            result2 = self._git("worktree", "add", str(target), branch)
            if result2.returncode != 0:
                raise RuntimeError(f"git worktree add failed: {result2.stderr}")

        port = _assign_port(branch)
        (target / ".env").write_text(f"PORT={port}\nWORKSHOP_NAME={workshop_name}\n")

        return target

    def list_all(self) -> list[dict]:
        result = self._git("worktree", "list", "--porcelain")
        trees: list[dict] = []
        current: dict = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    trees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD ") and current:
                current["head"] = line[5:]
            elif line.startswith("branch ") and current:
                current["branch"] = line[20:]
        if current:
            trees.append(current)
        return [
            {
                "name": Path(t.get("path", "")).name,
                "path": t.get("path", ""),
                "branch": t.get("branch", t.get("head", "")),
            }
            for t in trees
        ]

    def remove(self, workshop_name: str) -> None:
        wt_id = f"wt-{workshop_name}"
        target = self._root / wt_id
        if not target.exists():
            return
        self._git("worktree", "remove", str(target), "--force")
        try:
            self._git("branch", "-D", f"workshop/{workshop_name}")
        except RuntimeError:
            pass
