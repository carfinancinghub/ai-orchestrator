# Path: core/git_ops.py
from __future__ import annotations
from pathlib import Path
from typing import List
import subprocess

class GitOps:
    """Minimal git wrapper for batch add+commit."""
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        # Why: keep output for debugging if needed
        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True)

    def add_and_commit(self, paths: List[Path], batch_size: int = 100, message_prefix: str = "chore(convert): js→ts batch") -> int:
        if not paths:
            return 0
        total_commits = 0
        for i in range(0, len(paths), batch_size):
            chunk = paths[i:i + batch_size]
            rels = [str((p if p.is_absolute() else self.root / p).resolve().relative_to(self.root)) for p in chunk]
            r1 = self._run("add", "--", *rels)
            if r1.returncode != 0:
                continue  # skip chunk on error
            r2 = self._run("commit", "-m", f"{message_prefix} ({i//batch_size+1}/{(len(paths)+batch_size-1)//batch_size})")
            if r2.returncode == 0:
                total_commits += 1
        return total_commits
