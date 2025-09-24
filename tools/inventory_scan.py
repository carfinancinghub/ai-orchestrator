# Path: tools/inventory_scan.py
r"""
Purpose
-------
Inventory the ai-orchestrator workspace with maximum signal, minimum noise.
- Recursively scans a root (default: C:\c\ai-orchestrator)
- Prunes node_modules and other heavy/backup dirs
- Outputs:
    reports/tree.txt                  (pretty tree of dirs/files)
    reports/inventory_index.json      (per-file facts: path, size, mtime, ext, sha1, first lines)
    reports/code_counts_by_ext.json   (counts of code files by extension)
    reports/top_dirs.csv              (top directories by file count)
    reports/debug_scan.txt            (what was pruned and why)
- Optional content search: --grep "pattern" (case-insensitive) -> reports/grep_results.txt

Config via env:
    CFH_SCAN_ROOT        (default: C:\c\ai-orchestrator)
    CFH_REPORTS_DIR      (default: .\reports)
    CFH_MAX_SAMPLE_BYTES (default: 4096)
    CFH_IGNORE_EXTRA     (comma-separated dir names to ignore in addition to the defaults)
"""

from __future__ import annotations
import os
import re
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterator, List, Dict, Tuple, Optional

# ---------------- Defaults ----------------
DEFAULT_ROOT = Path(os.getenv("CFH_SCAN_ROOT") or r"C:\c\ai-orchestrator")
REPORTS      = Path(os.getenv("CFH_REPORTS_DIR") or (DEFAULT_ROOT / "reports"))
REPORTS.mkdir(parents=True, exist_ok=True)

MAX_SAMPLE_BYTES = int(os.getenv("CFH_MAX_SAMPLE_BYTES") or "4096")

IGNORE_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", ".turbo", ".cache",
    "artifacts", "reports", "coverage", "out", "tmp",
    "venv", ".venv", "env", ".env", ".pytest_cache", ".mypy_cache",
    "zipped_batches", "recovered", "archive", "snapshot",
    # common python deps
    "site-packages", "__pycache__",
}
EXTRA_IGN = {d.strip().lower() for d in (os.getenv("CFH_IGNORE_EXTRA") or "").split(",") if d.strip()}
IGNORE_DIRS |= EXTRA_IGN
IGNORE_DIRS_LOWER = {d.lower() for d in IGNORE_DIRS}

BACKUP_RX = re.compile(r"(?i)(backup|zipped_batches|recovered|archive|snapshot)")

TEXT_EXTS = {
    ".js",".jsx",".ts",".tsx",".mjs",".cjs",".json",".jsonc",
    ".css",".scss",".sass",".less",
    ".md",".mdx",".yml",".yaml",".toml",".ini",".conf",".txt",".csv",".svg",
    ".py",".ps1",".psm1",".sh",".bat",".cmd",
}

CODE_EXTS = {
    ".js",".jsx",".ts",".tsx",".mjs",".cjs",
    ".py",".ps1",".psm1",".sh",".go",".rs",".java",".kt",".cs",".cpp",".c",".rb",".php",
}

BINARY_HINTS = {".png",".jpg",".jpeg",".gif",".webp",".ico",".ttf",".otf",".woff",".woff2",".zip",".7z",".pdf",".mp4",".mov",".exe",".dll"}

# ---------------- Helpers ----------------
def _should_prune_dir(name: str) -> bool:
    n = name.lower()
    return (
        n in IGNORE_DIRS_LOWER
        or "site-packages" in n
        or bool(BACKUP_RX.search(name))
    )

def walk_pruned(root: Path) -> Iterator[Tuple[str, list, list]]:
    """os.walk with in-place pruning of ignored/backup dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_prune_dir(d)]
        yield dirpath, dirnames, filenames

def is_probably_text(path: Path) -> bool:
    ext = path.suffix.lower()
    if ext in BINARY_HINTS:
        return False
    return ext in TEXT_EXTS or ext in CODE_EXTS

def safe_head_sample(path: Path, max_bytes: int = MAX_SAMPLE_BYTES) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        # Heuristic: if there are too many NULs, treat as binary
        if data.count(b"\x00") > 0:
            return ""
        # Try utf-8 then fallback
        for enc in ("utf-8", "utf-8-sig", "latin1"):
            try:
                return data.decode(enc, errors="ignore")
            except Exception:
                continue
        return ""
    except Exception:
        return ""

def sha1_of_file(path: Path, max_bytes: Optional[int] = None) -> str:
    try:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            if max_bytes is None:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            else:
                h.update(f.read(max_bytes))
        return h.hexdigest()
    except Exception:
        return ""

def rel(root: Path, p: Path) -> str:
    try:
        return str(p.resolve().relative_to(root.resolve())).replace("\\","/")
    except Exception:
        return str(p).replace("\\","/")

# ---------------- Collectors ----------------
def collect_inventory(root: Path, grep: Optional[str] = None) -> Dict:
    debug_lines: List[str] = []
    files: List[Dict] = []
    counts_by_ext: Dict[str, int] = {}
    top_dirs: Dict[str, int] = {}

    grep_rx = re.compile(grep, re.I) if grep else None
    grep_hits: List[Dict] = []

    for dirpath, dirnames, filenames in walk_pruned(root):
        # record pruned info (debug)
        pruned = [d for d in os.listdir(dirpath) if os.path.isdir(os.path.join(dirpath, d)) and _should_prune_dir(d)]
        if pruned:
            debug_lines.append(f"PRUNED @ {dirpath} --> {', '.join(sorted(pruned))}")

        for fn in filenames:
            p = Path(dirpath) / fn
            ext = p.suffix.lower()
            rp = rel(root, p)

            try:
                st = p.stat()
                size = st.st_size
                mtime = int(st.st_mtime)
            except Exception:
                size, mtime = 0, 0

            # statistics
            counts_by_ext[ext] = counts_by_ext.get(ext, 0) + 1
            top_dir = rp.split("/", 1)[0] if "/" in rp else rp
            top_dirs[top_dir] = top_dirs.get(top_dir, 0) + 1

            sample = ""
            if is_probably_text(p):
                sample = safe_head_sample(p, MAX_SAMPLE_BYTES)

            if grep_rx and sample:
                if grep_rx.search(sample) or grep_rx.search(rp):
                    grep_hits.append({"path": rp, "match": True})

            files.append({
                "path": rp,
                "ext": ext,
                "size": size,
                "mtime": mtime,
                "sha1_64k": sha1_of_file(p, 65536),  # fast-ish integrity/fingerprint
                "sample": sample[:4000],             # cap per-file sample
            })

    # pretty dir tree
    tree_lines = []
    for dirpath, dirnames, filenames in walk_pruned(root):
        rel_dir = rel(root, Path(dirpath))
        depth = 0 if rel_dir == "." else rel_dir.count("/")
        indent = "  " * depth
        tree_lines.append(f"{indent}{rel_dir or '.'}/")
        for f in sorted(filenames):
            tree_lines.append(f"{indent}  {f}")

    return {
        "files": files,
        "counts_by_ext": dict(sorted(counts_by_ext.items(), key=lambda kv: (-kv[1], kv[0]))),
        "top_dirs": dict(sorted(top_dirs.items(), key=lambda kv: (-kv[1], kv[0]))),
        "tree": tree_lines,
        "debug": debug_lines,
        "grep_hits": grep_hits,
        "root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

def write_reports(root: Path, inv: Dict):
    (REPORTS / "inventory_index.json").write_text(json.dumps({
        "root": inv["root"],
        "generated_at": inv["generated_at"],
        "counts_by_ext": inv["counts_by_ext"],
        "top_dirs": inv["top_dirs"],
        "files": inv["files"],
    }, indent=2), encoding="utf-8")

    (REPORTS / "code_counts_by_ext.json").write_text(json.dumps(inv["counts_by_ext"], indent=2), encoding="utf-8")

    # tree
    (REPORTS / "tree.txt").write_text("\n".join(inv["tree"]) + "\n", encoding="utf-8")

    # debug
    if inv["debug"]:
        (REPORTS / "debug_scan.txt").write_text("\n".join(inv["debug"]) + "\n", encoding="utf-8")

    # grep
    if inv["grep_hits"]:
        (REPORTS / "grep_results.txt").write_text("\n".join(hit["path"] for hit in inv["grep_hits"]) + "\n", encoding="utf-8")

# ---------------- CLI ----------------
def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Inventory ai-orchestrator repo (pruned).")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="Root folder to scan")
    ap.add_argument("--grep", default=None, help="Optional case-insensitive pattern to search in paths/samples")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 2

    inv = collect_inventory(root, grep=args.grep)
    write_reports(root, inv)
    print(f"Wrote:\n - {REPORTS / 'inventory_index.json'}\n - {REPORTS / 'code_counts_by_ext.json'}\n - {REPORTS / 'tree.txt'}")
    if inv["debug"]:
        print(f" - {REPORTS / 'debug_scan.txt'}")
    if inv["grep_hits"]:
        print(f" - {REPORTS / 'grep_results.txt'} (matches: {len(inv['grep_hits'])})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
