# reports/tools/run_reviewer.py
from __future__ import annotations
import json, os, sys
from pathlib import Path

# 1) Ensure repo root is on sys.path (this file is 2 levels under repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# 2) Now imports from the repo will work
from app.ai.reviewer import review_batch  # type: ignore

def main() -> None:
    label = os.environ.get("CFH_REVIEW_LABEL", "auctions_wow")
    paths_file = REPO_ROOT / f"reports/paths_{label}.txt"
    if not paths_file.exists():
        raise SystemExit(f"Paths list not found: {paths_file}")

    paths = [p.strip() for p in paths_file.read_text(encoding="utf-8").splitlines() if p.strip()]
    if not paths:
        raise SystemExit("No candidate file paths provided in paths list.")

    res = review_batch(paths, tier="wow", label=label, md_first=True)
    print(json.dumps(res, indent=2))

    # Show where artifacts went
    out_dir = REPO_ROOT / f"reports/{label}/mds"
    print(f"\n[info] per-file MD dir: {out_dir.as_posix()}")
    if out_dir.exists():
        count = len(list(out_dir.glob("*.md")))
        print(f"[info] per-file MD count: {count}")

if __name__ == "__main__":
    main()
