# scripts/dedup_numeric.py
from pathlib import Path
import csv
import os
from collections import defaultdict
from app.utils.numeric_junk import is_numeric_junk

ROOTS = [p.strip() for p in os.getenv("AIO_SCAN_ROOTS", "").split(",") if p.strip()]
SKIP  = {p.strip().lower() for p in os.getenv("AIO_SKIP_DIRS", "").split(",") if p.strip()}

OUT_DIR   = Path("reports")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH  = OUT_DIR / "duplicates_eliminated.csv"
CAND_PATH = OUT_DIR / "conversion_candidates.txt"

EXTS = {".js", ".jsx", ".ts", ".tsx"}

def in_skip_parts(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(s in parts for s in SKIP)

def main() -> None:
    candidates = []
    for root in ROOTS:
        r = Path(root)
        if not r.exists():
            continue
        for p in r.rglob("*"):
            if not p.is_file(): continue
            if in_skip_parts(p): continue
            if p.suffix.lower() not in EXTS: continue
            if is_numeric_junk(str(p)): continue
            candidates.append(p)

    groups = defaultdict(list)
    for p in candidates:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        key = (p.stem.lower(), size)
        groups[key].append(p)

    kept, eliminated = [], []
    for key, files in groups.items():
        files_sorted = sorted(files, key=lambda z: (0 if z.suffix.lower() in {".ts", ".tsx"} else 1, str(z).lower()))
        best = files_sorted[0]
        kept.append(best)
        eliminated.extend((best, other) for other in files_sorted[1:])

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kept", "eliminated"])
        for best, other in eliminated:
            w.writerow([str(best), str(other)])

    with CAND_PATH.open("w", encoding="utf-8") as f:
        for c in kept:
            f.write(str(c) + "\n")

    print(f"[dedup] kept={len(kept)} eliminated={len(eliminated)} groups={len(groups)}")
    print(f"[dedup] wrote {CSV_PATH} and {CAND_PATH}")

if __name__ == "__main__":
    main()
