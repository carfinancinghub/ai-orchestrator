from __future__ import annotations
import os, csv, shutil
from collections import defaultdict
from typing import List, Tuple

SKIP_DIRS = {".git","node_modules","dist","build","coverage",".next",".turbo",".yarn",".pnpm-store",".cache"}
PREF = (".ts",".tsx",".js",".jsx")

def _pref_key(p: str) -> int:
    p = p.lower()
    for i, ext in enumerate(PREF):
        if p.endswith(ext):
            return i
    return len(PREF) + 1

def duplicate_elimination(scan_roots: List[str], consolidated_dir: str=r"C:\cfh_consolidated") -> Tuple[str,str]:
    groups: dict[tuple[str,int], list[str]] = defaultdict(list)
    for root in scan_roots or []:
        root = os.path.abspath(root)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                groups[(os.path.basename(fn), sz)].append(fp)

    rows = []
    conv = []
    os.makedirs("reports", exist_ok=True)
    os.makedirs(consolidated_dir, exist_ok=True)

    for (base, sz), paths in groups.items():
        winner = sorted(paths, key=_pref_key)[0]
        losers = [p for p in paths if p != winner]
        if winner.lower().endswith((".js",".jsx")) and not any(p.lower().endswith((".ts",".tsx")) for p in paths):
            conv.append(winner)
        drive = os.path.splitdrive(winner)[0].replace(":","")
        outdir = os.path.join(consolidated_dir, drive)
        os.makedirs(outdir, exist_ok=True)
        try:
            shutil.copy2(winner, os.path.join(outdir, base))
        except Exception:
            pass
        rows.append([winner, base, sz, "kept", ";".join(losers)])

    csv_path = os.path.join("reports","duplicates_eliminated.csv")
    txt_path = os.path.join("reports","conversion_candidates.txt")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file_path","base_name","size","kept","discarded"])
        w.writerows(rows)
    with open(txt_path, "w", encoding="utf-8") as fh:
        for c in conv:
            fh.write(c + "\n")
    return csv_path, txt_path