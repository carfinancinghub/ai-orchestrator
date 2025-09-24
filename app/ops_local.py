# Path: app/ops_local.py
from __future__ import annotations
from pathlib import Path
import json
import re
import time
from typing import Dict, List, Tuple

REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)

JUNK_DIRS = {".git", "node_modules", "dist", "build", ".next", ".cache", "coverage", "out"}
RECYCLE_TOKENS = {"$recycle.bin", "__macosx"}
NUM_NAME_RE = re.compile(r"^(?:\d+|\w*\d{2,}\w*)$", re.IGNORECASE)

class LocalCandidate:
    def __init__(self, repo: str, branch: str, src_path: str, size: int = 0):
        self.repo = repo
        self.branch = branch
        self.src_path = src_path
        self.size = size

def _should_skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & RECYCLE_TOKENS:
        return True
    if any(d in JUNK_DIRS for d in parts):
        return True
    if NUM_NAME_RE.match(path.name):
        return True
    return False

def _has_ts_sibling(p: Path) -> bool:
    base = p.with_suffix("")
    return base.with_suffix(".ts").exists() or base.with_suffix(".tsx").exists()

def _bundle_for(p: Path) -> List[str]:
    base = p.with_suffix("")
    sibs = []
    for ext in (".test.js", ".spec.js", ".test.jsx", ".spec.jsx", ".md"):
        sp = base.with_suffix(ext)
        if sp.exists():
            sibs.append(str(sp))
    return sibs

def scan_local(root: str, run_id: str, cap: int = 2000) -> Tuple[List[LocalCandidate], Dict[str, List[str]], List[Dict]]:
    rootp = Path(root)
    if not rootp.exists():
        return [], {}, [{"repo": "local", "branches": ["local"]}]
    cands: List[LocalCandidate] = []
    bundles: Dict[str, List[str]] = {}
    count_by_ext = {"js":0, "jsx":0, "ts":0, "tsx":0, "md":0}
    for p in rootp.rglob("*"):
        if not p.is_file():
            continue
        if _should_skip(p):
            continue
        ext = p.suffix.lower()
        if ext in (".ts", ".tsx", ".js", ".jsx", ".md"):
            count_by_ext[ext.lstrip(".")] = count_by_ext.get(ext.lstrip("."), 0) + 1
        if ext not in (".js", ".jsx"):
            continue
        if _has_ts_sibling(p):
            continue
        cand = LocalCandidate(repo="local", branch="local", src_path=str(p), size=p.stat().st_size)
        bundles[str(p)] = _bundle_for(p)
        cands.append(cand)
        if len(cands) >= cap:
            break

    payload = {
        "run_id": run_id,
        "root": str(rootp),
        "found_js_jsx": len(cands),
        "counts": count_by_ext,
        "discrepancies": {"local": len(cands)},  # repo-only totals
        "ts_siblings_skipped": True,
        "cap": cap,
        "generated_at": int(time.time()),
    }
    out = REPORTS / f"scan_{run_id}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # also write/refresh a latest pointer
    (REPORTS / "scan_latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return cands, bundles, [{"repo": "local", "branches": ["local"]}]
