import os, csv, shutil
from pathlib import Path

PREF_EXTS = [".ts", ".tsx", ".d.ts"]
BAD_EXTS  = [".js", ".jsx"]

def _pref_rank(p: Path) -> int:
    ext = p.suffix.lower()
    if ext in PREF_EXTS: return 0
    if ext in BAD_EXTS:  return 2
    return 1

def duplicate_elimination(scan_roots: list[str], out_root: str, reports_root: str):
    out_dir = Path(out_root); out_dir.mkdir(parents=True, exist_ok=True)
    rpt_dir = Path(reports_root); rpt_dir.mkdir(parents=True, exist_ok=True)

    groups = {}
    for root in scan_roots:
        rootp = Path(root)
        if not rootp.exists():
            continue
        for p in rootp.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in PREF_EXTS + BAD_EXTS:
                continue
            key = (p.stem, p.stat().st_size)
            groups.setdefault(key, []).append(p)

    unique = []
    eliminated = []
    for key, paths in groups.items():
        paths_sorted = sorted(paths, key=_pref_rank)
        keep = paths_sorted[0]
        unique.append((key, keep, [x for x in paths if x != keep]))
        for d in paths_sorted[1:]:
            eliminated.append((key, d))

    # Copy uniques
    for (_, keep, _dups) in unique:
        dest = Path(out_dir) / keep.name
        if not dest.exists():
            shutil.copy2(keep, dest)

    # Reports
    with (Path(reports_root)/"duplicates_eliminated.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["base+size","kept","eliminated"])
        for (key, keep, dups) in unique:
            w.writerow([f"{key[0]}:{key[1]}", str(keep), ";".join(map(str, dups))])

    with (Path(reports_root)/"conversion_candidates.txt").open("w", encoding="utf-8") as f:
        for (key, keep, _dups) in unique:
            if keep.suffix.lower() in BAD_EXTS:
                f.write(str(keep) + "\n")

    print(f"[dedupe] unique kept: {len(unique)}; duplicates removed: {len(eliminated)}")
