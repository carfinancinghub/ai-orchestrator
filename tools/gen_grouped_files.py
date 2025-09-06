# tools/gen_grouped_files.py
from __future__ import annotations
import os, re, json
from pathlib import Path
from collections import defaultdict

REPORTS = Path(os.getenv("CFH_REPORTS_DIR") or r"C:\c\ai-orchestrator\reports")
REPORTS.mkdir(parents=True, exist_ok=True)
OUT = REPORTS / "grouped_files.txt"

# Roots: CFH_SCAN_ROOTS="C:\Backup_Projects\CFH\frontend;C:\c\ai-orchestrator"
env_roots = os.getenv("CFH_SCAN_ROOTS") or ""
roots = []
if env_roots:
    for p in re.split(r"[;,]", env_roots):
        p = p.strip()
        if p:
            roots.append(Path(p))
if not roots:
    roots = [Path(r"C:\Backup_Projects\CFH\frontend"), Path(r"C:\c\ai-orchestrator")]

IGNORE_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", ".turbo", ".cache",
    "zipped_batches", "Recovered", "archive",
    "artifacts", "reports", "coverage", "out", "tmp"
}
BACKUP_RX = re.compile(r"(?i)backup")  # any dir name containing 'backup'
EXTS = {".js",".jsx",".ts",".tsx",".mjs",".cjs"}
CRYPTIC_RX = re.compile(r"^(?:\$|_)?(?:[A-Z0-9]{6,}|[A-F0-9]{6,}|I[0-9A-Z]{6,})(?:\.[A-Za-z0-9_-]+)*$")

def in_ignored_dir(p: Path) -> bool:
    parts = {part.lower() for part in p.parts}
    if any(d in parts for d in (d.lower() for d in IGNORE_DIRS)):
        return True
    if any(BACKUP_RX.search(part) for part in p.parts):
        return True
    return False

def norm(s: str) -> str:
    return s.replace("\\","/")

def base_name(p: Path) -> str:
    b = p.stem
    lb = b.lower()
    if lb.endswith(".test"):
        b = b[:-5]
    if lb.endswith(".spec"):
        b = b[:-5]
    return b

def is_cryptic(name: str) -> bool:
    return bool(CRYPTIC_RX.match(Path(name).stem))

def collect():
    groups: dict[str, list[str]] = defaultdict(list)
    for r in roots:
        if not r.exists():
            continue
        for dp, dn, fn in os.walk(r):
            # prune noisy dirs
            dn[:] = [d for d in dn if d.lower() not in {x.lower() for x in IGNORE_DIRS} and not BACKUP_RX.search(d)]
            for f in fn:
                p = Path(dp) / f
                if in_ignored_dir(p): 
                    continue
                if p.suffix.lower() not in EXTS:
                    continue
                if is_cryptic(p.name):
                    continue
                b = base_name(p)
                rel = norm(str(p.relative_to(r)))
                if rel not in groups[b]:
                    groups[b].append(rel)
    return groups

def write(groups: dict[str, list[str]]):
    with OUT.open("w", encoding="utf-8") as fh:
        for b in sorted(groups.keys()):
            fh.write(f"{b}:\n")
            for rel in sorted(groups[b]):
                fh.write(f"  - {rel}\n")
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    groups = collect()
    write(groups)
