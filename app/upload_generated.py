# app/upload_generated.py
from __future__ import annotations
import subprocess, os, sys
from pathlib import Path

def run(cmd: list[str], cwd: str | None = None):
    print("[upload]"," ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=True)

def upload_generated(branch: str="ts-migration/generated", repo_root: str="."):
    repo = Path(repo_root)
    gen  = repo / "artifacts" / "generated"
    if not gen.exists():
        print("[upload] no artifacts/generated to upload")
        return False
    run(["git","fetch","origin"], cwd=repo_root)
    run(["git","checkout","-B", branch], cwd=repo_root)
    run(["git","add", str(gen)], cwd=repo_root)
    run(["git","commit","-m","chore(ts-migration): upload generated TS artifacts"], cwd=repo_root)
    run(["git","push","-u","origin", branch], cwd=repo_root)
    return True

if __name__ == "__main__":
    ok = upload_generated()
    print({"ok": ok})
