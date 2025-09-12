import os, subprocess
from pathlib import Path

def upload_generated(branch: str = "ts-migration/generated", dry_run: bool = False):
    repo_root = Path(os.environ.get("AIO_REPO_ROOT", ".")).resolve()
    gen_dir = repo_root / "artifacts" / "generated"
    if not gen_dir.exists():
        print(f"[upload] nothing to upload: {gen_dir}")
        return
    def run(cmd):
        print("[upload]", " ".join(cmd))
        if dry_run: 
            return 0
        return subprocess.check_call(cmd, cwd=repo_root)

    run(["git", "fetch", "origin"])
    try:
        run(["git", "checkout", "-B", branch])
    except Exception:
        run(["git", "checkout", branch])
    run(["git", "add", str(gen_dir)])
    run(["git", "commit", "-m", "chore(ts-migration): upload generated TS artifacts"])
    run(["git", "push", "-u", "origin", branch])

if __name__ == "__main__":
    upload_generated(branch=os.environ.get("AIO_UPLOAD_BRANCH", "ts-migration/generated"),
                     dry_run=os.environ.get("AIO_DRY_RUN","false").lower()=="true")
