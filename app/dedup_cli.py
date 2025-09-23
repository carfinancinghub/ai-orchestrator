from __future__ import annotations
import argparse, csv, hashlib, os, re, shutil, sys
from pathlib import Path
from typing import Iterable, Dict, List, Tuple

NUMERIC_RUN = re.compile(r"\d{3,}")  # any 3+ consecutive digits

PREF_ORDER = [".ts", ".tsx", ".js", ".jsx"]

def is_numeric_junk(stem: str) -> bool:
    s = stem.strip().lower()
    if not s:
        return True
    # all digits (>=3)
    if s.isdigit() and len(s) >= 3:
        return True
    # contains any 3+ digit run
    if NUMERIC_RUN.search(s):
        return True
    return False

def iter_files(roots: Iterable[Path], exts: Iterable[str], skip_dirs: Iterable[str]) -> Iterable[Path]:
    exts_l = {("." + e.lower().lstrip(".")) for e in exts}
    skip_set = {d.lower() for d in skip_dirs}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_dir():
                # skip by directory name anywhere in path
                if any(part.lower() in skip_set for part in p.parts):
                    continue
                continue
            if any(part.lower() in skip_set for part in p.parts):
                continue
            ext = p.suffix.lower()
            if ext in exts_l and not is_numeric_junk(p.stem):
                yield p

def choose_best(files: List[Path]) -> Path:
    # prefer by extension order; tie-break by shortest path (stable)
    files = sorted(files, key=lambda p: (PREF_ORDER.index(p.suffix.lower()) if p.suffix.lower() in PREF_ORDER else 99, len(str(p))))
    return files[0]

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="CFH dedup + numeric junk filter")
    ap.add_argument("--roots", help="CSV list of roots; else AIO_SCAN_ROOTS; else CWD", default=None)
    ap.add_argument("--skip-dirs", default="node_modules,dist,.git,build,coverage,.cache,.next,.turbo,.yarn,.pnpm-store,storybook-static,out")
    ap.add_argument("--exts", default="js,jsx,ts,tsx")
    ap.add_argument("--out", default=r"C:\cfh_consolidated")
    ap.add_argument("--reports", default="reports")
    args = ap.parse_args(argv)

    roots = []
    if args.roots:
        roots = [Path(p.strip()) for p in args.roots.split(",") if p.strip()]
    else:
        env_roots = os.getenv("AIO_SCAN_ROOTS", "")
        roots = [Path(p.strip()) for p in env_roots.split(",") if p.strip()] or [Path.cwd()]

    skip_dirs = [s.strip() for s in args.skip_dirs.split(",") if s.strip()]
    exts = [e.strip() for e in args.exts.split(",") if e.strip()]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    reports_root = Path(args.reports)
    reports_root.mkdir(parents=True, exist_ok=True)
    reports_root.joinpath("debug").mkdir(parents=True, exist_ok=True)

    groups: Dict[Tuple[str,int], List[Path]] = {}
    candidates: List[Path] = []

    for f in iter_files(roots, exts, skip_dirs):
        key = (f.stem.lower(), f.stat().st_size)
        groups.setdefault(key, []).append(f)

    keepers: List[Path] = []
    eliminated_rows = []

    for key, files in groups.items():
        keep = choose_best(files)
        keepers.append(keep)
        discarded = [p for p in files if p != keep]
        eliminated_rows.append({
            "stem": key[0],
            "size": key[1],
            "keep": str(keep),
            "kept_ext": keep.suffix.lower(),
            "discard_count": len(discarded),
            "total": len(files)
        })
        if keep.suffix.lower() in (".js", ".jsx"):
            candidates.append(keep)

    # Copy keepers into out_dir (ensure uniqueness)
    for i, src in enumerate(keepers):
        digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:8]
        dest = out_dir / (src.stem + src.suffix)
        if dest.exists():
            dest = out_dir / f"{src.stem}_{digest}{src.suffix}"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        except Exception as e:
            print(f"[copy] WARN {src} -> {dest}: {e}", file=sys.stderr)

    # Write reports
    dup_csv = reports_root / "duplicates_eliminated.csv"
    with dup_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stem","size","keep","kept_ext","discard_count","total"])
        w.writeheader()
        for row in sorted(eliminated_rows, key=lambda r: (r["stem"], r["size"])):
            w.writerow(row)

    cand_txt = reports_root / "conversion_candidates.txt"
    with cand_txt.open("w", encoding="utf-8") as f:
        for c in sorted(candidates, key=lambda p: str(p).lower()):
            f.write(str(c) + "\n")

    print(f'{{"ok": true, "keepers": {len(keepers)}, "candidates": {len(candidates)}, "out": "{out_dir}"}}')
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
