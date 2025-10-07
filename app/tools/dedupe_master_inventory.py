#!/usr/bin/env python3
"""
Dedupe Master Inventory (Windows path aware)

Input CSV columns (7):
root, abs_path, rel_path, base_name, ext, size, mtime

Policy:
- Normalize rel_path with casefold + backslashes
- Key = (rel_path_norm, size)
- Keep the row whose root has higher precedence (default: C:\CFH > C:\cfh > others)
- Output:
  - *_clean.csv : kept rows
  - *_dupes.csv : discarded rows (with 'kept_abs_path' column)
  - *_summary.md : counts
"""

from __future__ import annotations
import csv
import sys
from pathlib import Path
from typing import List, Dict, Tuple

DEFAULT_PRECEDENCE = [
    r"C:\CFH",
    r"C:\cfh",
]

HEADERS = ["root","abs_path","rel_path","base_name","ext","size","mtime"]

def norm_rel(p: str) -> str:
    # Normalize to backslashes and casefold for Windows case-insensitivity
    return p.replace("/", "\\").casefold()

def precedence_index(root: str, precedence: List[str]) -> int:
    # lower index = higher priority; unknown roots sink to the end
    try:
        return precedence.index(root)
    except ValueError:
        return len(precedence)

def read_rows(csv_path: Path) -> List[Dict[str,str]]:
    rows: List[Dict[str,str]] = []
    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Handle files that may have been exported without headers in exact order
        if reader.fieldnames is None:
            # Fall back to positional read
            f.seek(0)
            reader = csv.reader(f)
            for raw in reader:
                if not raw:
                    continue
                row = dict(zip(HEADERS, raw))
                rows.append(row)
        else:
            # Best-effort column mapping
            fn = [h.strip() for h in reader.fieldnames]
            # If columns match, use DictReader directly
            if all(h in fn for h in HEADERS):
                for r in reader:
                    rows.append({k: r.get(k, "") for k in HEADERS})
            else:
                # Positional fallback
                f.seek(0)
                reader2 = csv.reader(f)
                for raw in reader2:
                    if not raw:
                        continue
                    row = dict(zip(HEADERS, raw))
                    rows.append(row)
    return rows

def write_csv(path: Path, rows: List[Dict[str,str]], headers: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in headers})

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: dedupe_master_inventory.py <input_csv> [<out_dir>] [<precedence_csv>]")
        print(" - <precedence_csv> optional: one root per line in priority order")
        return 2

    in_csv = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else in_csv.parent
    precedence_file = Path(sys.argv[3]) if len(sys.argv) >= 4 else None

    precedence = DEFAULT_PRECEDENCE[:]
    if precedence_file and precedence_file.exists():
        precedence = [line.strip() for line in precedence_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    rows = read_rows(in_csv)

    kept_by_key: Dict[Tuple[str, str], Dict[str,str]] = {}
    dupes: List[Dict[str,str]] = []

    for r in rows:
        rel_norm = norm_rel(r.get("rel_path",""))
        size = r.get("size","")
        key = (rel_norm, size)

        if key not in kept_by_key:
            kept_by_key[key] = r
        else:
            current = kept_by_key[key]
            # Compare precedence
            curr_idx = precedence_index(current.get("root",""), precedence)
            cand_idx = precedence_index(r.get("root",""), precedence)
            if cand_idx < curr_idx:
                # new candidate wins, previous becomes dupe
                prev = current
                kept_by_key[key] = r
                prev_dupe = prev.copy()
                prev_dupe["kept_abs_path"] = r.get("abs_path","")
                dupes.append(prev_dupe)
            else:
                # candidate becomes dupe
                d = r.copy()
                d["kept_abs_path"] = current.get("abs_path","")
                dupes.append(d)

    kept = list(kept_by_key.values())

    # Outputs
    stem = in_csv.stem
    out_clean = out_dir / f"{stem}_clean.csv"
    out_dupes = out_dir / f"{stem}_dupes.csv"
    out_summary = out_dir / f"{stem}_summary.md"

    write_csv(out_clean, kept, HEADERS)
    write_csv(out_dupes, dupes, HEADERS + ["kept_abs_path"])

    # Summary
    total = len(rows)
    kept_n = len(kept)
    dupes_n = len(dupes)
    summary_md = [
        f"# Dedupe Summary — {in_csv.name}",
        "",
        f"- Total rows: **{total}**",
        f"- Kept: **{kept_n}**",
        f"- Duplicates removed: **{dupes_n}**",
        "",
        "## Policy",
        "- Key: `(rel_path normalized case-insensitively, size)`",
        f"- Precedence: {', '.join(precedence) if precedence else '(none)'}",
    ]
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_summary.write_text("\n".join(summary_md), encoding="utf-8")

    print(f"Wrote: {out_clean}")
    print(f"Wrote: {out_dupes}")
    print(f"Wrote: {out_summary}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

