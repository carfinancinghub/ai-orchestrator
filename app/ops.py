# app/ops.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import os, json, re
import pathlib
from pathlib import Path

# ---------------- small utils ----------------
def _norm_slashes(s: str) -> str:
    return (s or "").replace("\\", "/")

def _safe_attr(obj, name):
    try:
        return getattr(obj, name)
    except Exception:
        return None

def _candidate_path(obj):
    v = _safe_attr(obj, "path")
    if v:
        return v
    v = _safe_attr(obj, "src_path")
    if v:
        return v
    if isinstance(obj, dict):
        return obj.get("path") or obj.get("src_path")
    return None
# ---------------------------------------------

# ---------------- scanning config ------------
IGNORE_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", ".turbo", ".cache",
    "artifacts", "reports", "coverage", "out", "tmp",
    "venv", ".venv", "env", ".env", ".pytest_cache", ".mypy_cache"
}
BACKUP_RX = re.compile(r"(?i)backup|zipped_batches|recovered|archive|snapshot")

EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
CRYPTIC_RX = re.compile(
    r"^(?:\$|_)?(?:[A-Z0-9]{6,}|[A-F0-9]{6,}|I[0-9A-Z]{6,})(?:\.[A-Za-z0-9_-]+)*$"
)

def _is_ignored_path(p: Path) -> bool:
    """True if any path segment is an ignored dir, backup-like, or site-packages."""
    parts_lower = [part.lower() for part in p.parts]
    if any(part in IGNORE_DIRS for part in parts_lower):
        return True
    if any("site-packages" in part for part in parts_lower):
        return True
    if any(BACKUP_RX.search(part or "") for part in parts_lower):
        return True
    return False

def _is_cryptic(name: str) -> bool:
    return bool(CRYPTIC_RX.match(Path(name).stem))

def _is_test_like(name: str) -> bool:
    n = name.lower()
    return ".test." in n or ".spec." in n
# ---------------------------------------------

@dataclass
class Candidate:
    repo: str
    branch: str
    path: str         # absolute or normalized absolute
    action: str       # "convert" for .js/.jsx without TS sibling, "evaluate" for .ts/.tsx

# ---------- file iteration (prunes ignored/backup/site-packages early) ----------
def _iter_files_pruned(root: Path):
    """
    os.walk with in-place dir pruning so we never descend into:
      - anything in IGNORE_DIRS,
      - backup-like dirs (backup, zipped_batches, recovered, archive, snapshot),
      - any directory containing 'site-packages'.
    This avoids listing 20k+ files and speeds scans significantly.
    """
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored + backup-like dirs + site-packages anywhere
        dirnames[:] = [
            d for d in dirnames
            if d.lower() not in IGNORE_DIRS
            and not BACKUP_RX.search(d)
            and "site-packages" not in d.lower()
        ]
        for fn in filenames:
            p = Path(dirpath) / fn
            yield p

# ------- local candidates for one root (excludes ignored/backup/site-packages) -------
def _list_local_candidates_one_root(root: Path, repo_alias: str = "local") -> List[Candidate]:
    js_jsx: List[Path] = []
    ts_tsx: List[Path] = []

    for p in _iter_files_pruned(root):
        if not p.is_file():
            continue
        if _is_ignored_path(p):
            continue
        ext = p.suffix.lower()
        if ext not in EXTS:
            continue
        if _is_cryptic(p.name):
            continue

        if ext in (".js", ".jsx"):
            js_jsx.append(p)
        elif ext in (".ts", ".tsx"):
            ts_tsx.append(p)

    # Build sibling TS base set using relpaths so Windows casing doesn't break us.
    def _base_rel(path_obj: Path) -> str:
        rel = _norm_slashes(os.path.relpath(str(path_obj), str(root)))
        return os.path.splitext(rel)[0].lower()

    ts_bases = { _base_rel(p) for p in ts_tsx }

    out: List[Candidate] = []
    # Convert: .js/.jsx without .ts/.tsx siblings
    for p in js_jsx:
        base = _base_rel(p)
        if base not in ts_bases:
            out.append(Candidate(
                repo=repo_alias, branch="local",
                path=_norm_slashes(str(p.resolve())),
                action="convert"
            ))
    # Evaluate existing .ts/.tsx
    for p in ts_tsx:
        out.append(Candidate(
            repo=repo_alias, branch="local",
            path=_norm_slashes(str(p.resolve())),
            action="evaluate"
        ))
    return out

def _list_local_candidates_multi(roots: List[Path]) -> List[Candidate]:
    out: List[Candidate] = []
    for idx, r in enumerate(roots):
        if not r or not r.exists():
            continue
        alias = r.name or f"root{idx+1}"
        out.extend(_list_local_candidates_one_root(r, repo_alias=alias))
    return out
# ----------------------------------------------------------------------

# ---------------- grouping output (safe write in reports/) -------------
def _build_groups_from_candidates(roots: List[Path], cands: List[Candidate]) -> Dict[str, List[str]]:
    """
    Groups by base name (without .test/.spec) and lists per-root relative paths.
    Skips cryptic names & ignored dirs.
    """
    # Map path prefix -> root Path to compute relpaths
    root_map: Dict[str, Path] = { _norm_slashes(str(r.resolve())): r for r in roots }

    groups: Dict[str, List[str]] = {}
    for c in cands:
        p = Path(c.path)
        if not p.exists():
            continue
        if _is_ignored_path(p) or _is_cryptic(p.name):
            continue
        base = p.stem
        # normalize base by stripping .test/.spec
        if base.lower().endswith(".test"):
            base = base[:-5]
        if base.lower().endswith(".spec"):
            base = base[:-5]

        # Find which root we belong to for a nice relpath
        rel = None
        p_str = _norm_slashes(str(p.resolve()))
        for rp_str, r in root_map.items():
            if p_str.startswith(rp_str + "/") or p_str == rp_str:
                rel = _norm_slashes(os.path.relpath(p_str, rp_str))
                break
        if not rel:
            # fallback: just use filename
            rel = p.name

        groups.setdefault(base, [])
        if rel not in groups[base]:
            groups[base].append(rel)
    return groups

def _maybe_write_grouped_files(roots: List[Path], cands: List[Candidate], reports_dir: Path):
    """
    Writes reports/grouped_files.txt only if missing, unless CFH_FORCE_GROUPING=1.
    Always safe: confined to reports/.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "grouped_files.txt"
    force = (os.getenv("CFH_FORCE_GROUPING") == "1")
    if out.exists() and not force:
        return

    groups = _build_groups_from_candidates(roots, cands)
    with out.open("w", encoding="utf-8") as fh:
        for base in sorted(groups.keys()):
            fh.write(f"{base}:\n")
            for rel in sorted(groups[base]):
                fh.write(f"  - {rel}\n")
# ----------------------------------------------------------------------

# ---------------- public API (unchanged signatures) --------------------
def _parse_roots_from_env() -> List[Path]:
    """
    CFH_SCAN_ROOTS: semicolon or comma separated list of roots
    Fallback to CFH_SCAN_ROOT or CFH_ROOT
    Optional CFH_EXTRA_ROOTS to append.
    """
    roots: List[str] = []
    env_roots = os.getenv("CFH_SCAN_ROOTS") or ""
    if env_roots:
        parts = [p.strip() for p in re.split(r"[;,]", env_roots) if p.strip()]
        roots.extend(parts)

    one = os.getenv("CFH_SCAN_ROOT") or os.getenv("CFH_ROOT") or ""
    if one and one.strip():
        roots.append(one.strip())

    extra = os.getenv("CFH_EXTRA_ROOTS") or ""
    if extra:
        parts = [p.strip() for p in re.split(r"[;,]", extra) if p.strip()]
        roots.extend(parts)

    # De-dup while preserving order
    seen = set()
    out = []
    for r in roots:
        nr = os.path.normpath(r)
        if nr not in seen:
            seen.add(nr)
            out.append(Path(nr))
    return out

def _bundle_by_source(cands: List[Candidate]) -> Dict[str, List[int]]:
    bundles: Dict[str, List[int]] = {}
    for i, c in enumerate(cands):
        src = _candidate_path(c) or f"cand_{i}"
        bundles.setdefault(src, []).append(i)
    return bundles

def fetch_candidates(
    org: Optional[str],
    user: Optional[str],
    repo_name: Optional[str],
    platform: str,
    token: Optional[str],
    run_id: str,
    branches: List[str],
    local_inventory_paths: Optional[List[str]] = None,
) -> Tuple[List[Candidate], Dict[str, List[int]], Dict[str, List[str]]]:
    """
    Safe, minimal, multi-root local scan:
    - Reads roots from env (CFH_SCAN_ROOTS / CFH_SCAN_ROOT / CFH_ROOT [+ CFH_EXTRA_ROOTS])
    - Excludes ignored, backup-like, and site-packages directories
    - Filters cryptic filenames
    - Writes reports/grouped_files.txt if missing (or CFH_FORCE_GROUPING=1)
    """
    roots = _parse_roots_from_env()
    if not roots:
        return [], {}, {}
    cands = _list_local_candidates_multi(roots)

    # Safe grouped files output
    reports_dir = Path(os.getenv("CFH_REPORTS_DIR") or "reports")
    _maybe_write_grouped_files(roots, cands, reports_dir)

    # sources map is informational for callers
    sources_map: Dict[str, List[str]] = {"roots": [str(r) for r in roots]}
    return cands, _bundle_by_source(cands), sources_map

# -------------------- batch processing (non-destructive) --------------------
def _worth_score_for(path: str, action: str) -> int:
    """
    Heuristic worth score 0–100:
    - Convert (no TS sibling): base 70
    - Evaluate (already TS): base 40
    - Tests/specs get -10
    - Size bumps: +0..20 based on kb up to ~50KB
    """
    base = 70 if action == "convert" else 40
    name = os.path.basename(path).lower()
    if ".test." in name or ".spec." in name:
        base -= 10
    try:
        sz = os.path.getsize(path)
    except Exception:
        sz = 0
    kb = min(int(sz / 1024), 50)
    bump = int((kb / 50) * 20)  # up to +20
    score = max(0, min(100, base + bump))
    return score

def _recommendation(score: int) -> str:
    if score >= 70: return "keep"
    if score >= 40: return "merge"
    return "discard"

def process_batch(
    platform: str,
    token: Optional[str],
    candidates: List[Candidate],
    bundle_by_src: Dict[str, List[int]],
    run_id: str,
    batch_offset: int = 0,
    batch_limit: int = 100,
) -> List[Dict]:
    """
    Non-destructive batch processor:
    - Slices candidates and returns a PASS placeholder per item
    - Adds worth_score (0-100) and recommendation keep/merge/discard
    - No external calls; safe for dashboards & dry-runs
    """
    try:
        start = int(batch_offset or 0)
    except Exception:
        start = 0
    try:
        lim = int(batch_limit or 0)
    except Exception:
        lim = 0

    batch = candidates[start:start + lim] if lim and lim > 0 else candidates[start:]
    results: List[Dict] = []
    for i, c in enumerate(batch):
        p = _candidate_path(c) or ""
        base = _norm_slashes(p).replace("/", "__") or f"cand_{start + i}"
        score = _worth_score_for(p, getattr(c, "action", "convert"))
        results.append({
            "index": start + i,
            "repo": getattr(c, "repo", "local"),
            "branch": getattr(c, "branch", "local"),
            "path": p,
            "action": getattr(c, "action", "convert"),
            "base": base,
            "status": "PASS",
            "run_id": run_id,
            "worth_score": score,
            "recommendation": _recommendation(score),
        })
    return results
# ---------------------------------------------------------------------------
