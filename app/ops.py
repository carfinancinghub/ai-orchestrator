# ==== 0) AIO-OPS | STANDARD FILE HEADER - START ===============================
# File: app/ops.py
# Purpose: Orchestrator for CFH TypeScript migration automation.
# Loop: scan → review → generate → gates → upload → report
#
# Environment (key vars)
# - AIO_TARGET_REPO        : e.g. "carfinancinghub/cfh"
# - AIO_FRONTEND_DIR       : local path to CFH frontend (vite project)
# - AIO_RUN_GATES          : "1" to run build/test/lint gates
# - AIO_UPLOAD_TS          : "1" = timestamp branches, "0" = rolling branch
# - AIO_UPLOAD_BRANCH      : branch name when using rolling mode
# - OPENAI_API_KEY         : (present check only)
# - GEMINI_API_KEY         : (present check only)
# - GROK_API_KEY           : (present check only)
# - GITHUB_TOKEN           : required for uploads/comments/labels
# - AIO_NPM_BIN            : optional full path to npm(.cmd) if npm not in PATH
#
# Rolling PR logic (Cod1)
# - If AIO_UPLOAD_TS == "0" and AIO_UPLOAD_BRANCH is non-empty,
#   uploader uses the rolling branch and appends commits to a single PR.
# - Otherwise defaults to per-run timestamp branches.
#
# Reports / artifacts
# - reports/upload_<run_id>.txt   : PR URL for a run (used by helpers)
# - reports/gates_<run_id>.json   : build/test/lint results
# - reports/debug/*.md            : human-readable status bundles
# - reports/inv_*.csv             : inventories (when generated)
#
# Sections (by marker):
#   0) STANDARD FILE HEADER
#   1) IMPORTS & CONSTANTS
#   2) HELPERS
#   3) GROUPING & FILTERS
#   4) FUNCTION EXTRACTION
#   5) ACORN EXTRACTOR
#   6) WORTH SCORE & RECOMMENDATION
#   7) GATES
#   8) SPECIAL SCAN & PROCESS
#   9) COMPAT: fetch_candidates
#  10) MULTI-AI REVIEW / GENERATE
#  11) GITHUB UPLOAD
#  12) SG-Man multi-AI review hook
#  13) ECOSYSTEM HELPERS
#
# Notes
# - Keep UTF-8 (no BOM); ensure console + Python encoding are UTF-8.
# - Never print secrets; only presence-check keys.
# - Batches limited to 25 files per append.
# - Post gates summary as PR comment after each append.
# ==== 0) AIO-OPS | STANDARD FILE HEADER - END =================================

# ==== 1) AIO-OPS | IMPORTS & CONSTANTS - START ================================
import os
import re
import sys
import csv
import json
import time
import shlex
import queue
import hashlib
import logging
import random
import string
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# GitHub API (PyGithub)
from github import Github, Auth

# Constants
AIO_REPO   = os.environ.get("AIO_TARGET_REPO", "carfinancinghub/cfh")
FRONTEND   = Path(os.environ.get("AIO_FRONTEND_DIR", "C:/Backup_Projects/CFH/frontend"))
REPORTS    = Path("reports")
DEBUG_DIR  = REPORTS / "debug"
BATCH_SIZE = int(os.environ.get("AIO_BATCH_SIZE", "25"))

# Ensure dirs
REPORTS.mkdir(exist_ok=True)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize GitHub client
_gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"])) if os.environ.get("GITHUB_TOKEN") else None
_repo = _gh.get_repo(AIO_REPO) if _gh else None

# ==== 1) AIO-OPS | IMPORTS & CONSTANTS - END ==================================
# ==== 2) AIO-OPS | HELPERS - START ===========================================
def log(msg: str) -> None:
    """Lightweight logger with UTC timestamp."""
    ts = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    print(f"[{ts}] {msg}", flush=True)


def sha1_of_file(path: Path) -> str:
    """Return SHA1 hex digest of a file."""
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json_report(obj: Any, dest: Path) -> None:
    """Write a JSON report with UTF-8 encoding."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def read_json_report(src: Path) -> Optional[Any]:
    """Read JSON if exists, else None."""
    if not src.exists():
        return None
    with src.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_list(x: Any) -> List[Any]:
    """Wrap non-list into a list."""
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

# ==== 2) AIO-OPS | HELPERS - END =============================================
# ==== 3) AIO-OPS | GROUPING & FILTERS - START =================================

def group_by_extension(files: List[Path]) -> Dict[str, List[Path]]:
    """Group a list of Paths by their lowercase extension."""
    groups: Dict[str, List[Path]] = {}
    for p in files:
        ext = p.suffix.lower()
        groups.setdefault(ext, []).append(p)
    return groups


def filter_source_like(files: List[Path]) -> List[Path]:
    """Keep only .js/.jsx/.ts/.tsx files."""
    return [f for f in files if f.suffix.lower() in (".js", ".jsx", ".ts", ".tsx")]


def exclude_node_modules(files: List[Path]) -> List[Path]:
    """Remove files inside node_modules directories."""
    return [f for f in files if "node_modules" not in f.parts]

# ==== 3) AIO-OPS | GROUPING & FILTERS - END ===================================
# ==== 4) AIO-OPS | FUNCTION EXTRACTION - START ================================

import re as _re

_FUNC_PATTERN = _re.compile(r'function\s+([A-Za-z0-9_]+)\s*\(')

def extract_functions_js(src: str) -> List[str]:
    """
    Extract function names from a JavaScript/TypeScript source string.
    Uses a naive regex that matches `function name(...)`.
    """
    return _FUNC_PATTERN.findall(src)

def extract_functions_from_file(path: Path) -> List[str]:
    """Read a file and extract function names if it's source-like."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    return extract_functions_js(text)

# ==== 4) AIO-OPS | FUNCTION EXTRACTION - END ==================================
# ==== 5) AIO-OPS | ACORN EXTRACTOR - START ====================================

import subprocess as _subp

def acorn_extract(path: Path) -> Dict[str, Any]:
    """
    Run acorn (JS parser) on a given file path and return parsed JSON AST.
    Requires `acorn` installed globally or locally in node_modules/.bin.
    """
    acorn_bin = "npx"
    args = ["acorn", "--ecma2020", "--locations", "--sourceType", "module", "--json", str(path)]
    try:
        result = _subp.run([acorn_bin] + args, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e), "file": str(path)}

def acorn_extract_safe(path: Path) -> Dict[str, Any]:
    """Safe wrapper that never raises, returns dict with 'functions' if possible."""
    ast = acorn_extract(path)
    if "error" in ast:
        return ast
    funcs = []
    for node in ast.get("body", []):
        if node.get("type") == "FunctionDeclaration":
            funcs.append(node.get("id", {}).get("name"))
    return {"file": str(path), "functions": funcs}

# ==== 5) AIO-OPS | ACORN EXTRACTOR - END ======================================
# ==== 6) AIO-OPS | WORTH SCORE & RECOMMENDATION - START =======================

def worth_score(path: Path, functions: Optional[List[str]] = None) -> float:
    """
    Naive heuristic:
      + ext weight: .ts/.tsx > .js/.jsx
      + size penalty beyond 50 KB
      + bonus per discovered function (capped)
    """
    ext = path.suffix.lower()
    ext_w = {".tsx": 1.0, ".ts": 0.9, ".jsx": 0.7, ".js": 0.6}.get(ext, 0.3)

    try:
        size_kb = path.stat().st_size / 1024.0
    except Exception:
        size_kb = 0.0

    size_pen = max(0.0, (size_kb - 50.0) / 200.0)  # gentle penalty
    fn_bonus = min(0.4, 0.04 * (len(functions or [])))  # cap at +0.4

    return round(ext_w + fn_bonus - size_pen, 4)


def recommend(files: List[Path]) -> List[Tuple[Path, float]]:
    """
    Return files sorted by descending worth score.
    Uses regex extraction (fast) as function signal.
    """
    scored: List[Tuple[Path, float]] = []
    for p in files:
        fns = extract_functions_from_file(p)
        scored.append((p, worth_score(p, fns)))
    return sorted(scored, key=lambda t: t[1], reverse=True)

# ==== 6) AIO-OPS | WORTH SCORE & RECOMMENDATION - END =========================
# ==== 7) AIO-OPS | GATES - START ==============================================

def _run_cmd(cmd: List[str], cwd: Path) -> Dict[str, Any]:
    """Run a command and capture output/exit status."""
    try:
        p = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
        return {
            "cmd": " ".join(cmd),
            "exit": p.returncode,
            "stdout": p.stdout[-10000:],  # cap to keep report light
            "stderr": p.stderr[-10000:],
            "pass": p.returncode == 0,
        }
    except FileNotFoundError as e:
        return {"cmd": " ".join(cmd), "exit": 127, "stdout": "", "stderr": str(e), "pass": False}
    except Exception as e:
        return {"cmd": " ".join(cmd), "exit": 1, "stdout": "", "stderr": repr(e), "pass": False}


def run_gates(run_id: str) -> Path:
    """
    Run build/test/lint gates (when AIO_RUN_GATES == '1') in FRONTEND.
    Writes reports/gates_<run_id>.json and returns that path.
    """
    gates_path = REPORTS / f"gates_{run_id}.json"

    should_run = (os.environ.get("AIO_RUN_GATES", "0") == "1")
    npm_bin = os.environ.get("AIO_NPM_BIN", "npm")

    data: Dict[str, Any] = {
        "run_id": run_id,
        "frontend": str(FRONTEND),
        "tooling": {"npm_bin": npm_bin},
        "steps": {},
    }

    if not should_run:
        data["skipped"] = True
        write_json_report(data, gates_path)
        return gates_path

    # Ensure node_modules present (best effort)
    if not (FRONTEND / "node_modules").exists():
        data["steps"]["ci"] = _run_cmd([npm_bin, "ci", "--no-audit", "--no-fund"], FRONTEND)

    # Build
    data["steps"]["build"] = _run_cmd([npm_bin, "run", "build", "--silent"], FRONTEND)

    # Test (vitest, allow project scripts to wire it)
    data["steps"]["test"] = _run_cmd([npm_bin, "run", "test", "--silent", "--", "-r"], FRONTEND)

    # Lint (eslint, allow project scripts)
    data["steps"]["lint"] = _run_cmd([npm_bin, "run", "lint", "--silent"], FRONTEND)

    write_json_report(data, gates_path)
    return gates_path

# ==== 7) AIO-OPS | GATES - END ================================================
# ==== 8) AIO-OPS | SPECIAL SCAN & PROCESS - START =============================

PREFERRED_EXT_RANK = {".ts": 0, ".tsx": 0, ".js": 1, ".jsx": 1}

def _dedupe_prefer_ts(paths: List[Path]) -> List[Path]:
    """
    Group by (basename,size). Within each group prefer .ts/.tsx over .js/.jsx.
    """
    groups: Dict[Tuple[str, int], List[Path]] = {}
    for p in paths:
        try:
            size = p.stat().st_size
        except Exception:
            size = -1
        key = (p.stem.lower(), size)
        groups.setdefault(key, []).append(p)

    kept: List[Path] = []
    for key, items in groups.items():
        # Rank by preferred extension, then shortest path for determinism
        items_sorted = sorted(
            items,
            key=lambda ip: (PREFERRED_EXT_RANK.get(ip.suffix.lower(), 99), len(str(ip)))
        )
        kept.append(items_sorted[0])
    return kept


def _load_conversion_candidates_list() -> Optional[List[Path]]:
    """
    Optional override list from reports/conversion_candidates.txt (absolute paths).
    One path per line. Non-existent paths are ignored.
    """
    cand_file = REPORTS / "conversion_candidates.txt"
    if not cand_file.exists():
        return None
    out: List[Path] = []
    for line in cand_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        p = Path(line)
        if p.exists():
            out.append(p)
    return out or None


def scan_frontend_sources(limit: int = BATCH_SIZE) -> List[Path]:
    """
    Scan FRONTEND/src for source-like files, exclude node_modules and dist,
    dedupe by (basename,size) preferring TS/TSX, and return up to `limit`.
    """
    src_root = FRONTEND / "src"
    if not src_root.exists():
        log(f"scan_frontend_sources: missing {src_root}")
        return []

    # 1) Start from explicit candidate list if present
    explicit = _load_conversion_candidates_list()
    if explicit:
        base = explicit
    else:
        # 2) Walk src tree
        all_files: List[Path] = [
            p for p in src_root.rglob("*")
            if p.is_file()
               and p.suffix.lower() in (".js", ".jsx", ".ts", ".tsx")
               and "node_modules" not in p.parts
               and "dist" not in p.parts
        ]
        base = all_files

    # 3) Dedupe and sort by heuristic score
    uniques = _dedupe_prefer_ts(base)
    scored = recommend(uniques)
    chosen = [p for (p, _s) in scored[:limit]]

    log(f"scan_frontend_sources: selected {len(chosen)} (of {len(uniques)} uniques)")
    return chosen

# ==== 8) AIO-OPS | SPECIAL SCAN & PROCESS - END ===============================
# ==== 9) AIO-OPS | COMPAT: fetch_candidates - START ===========================

def _parse_scan_roots() -> List[Path]:
    """
    Parse AIO_SCAN_ROOTS (CSV of absolute/relative dirs). Non-existent paths ignored.
    """
    envv = os.environ.get("AIO_SCAN_ROOTS", "")
    roots: List[Path] = []
    for raw in (envv.split(",") if envv else []):
        p = Path(raw.strip())
        if p.exists():
            roots.append(p)
    return roots

def fetch_candidates(limit: Optional[int] = None,
                     roots: Optional[List[Path]] = None) -> List[Path]:
    """
    Compatibility API returning a list of candidate source files.
    - If roots provided/AIO_SCAN_ROOTS set: scan those trees similarly to scan_frontend_sources.
    - Else: use scan_frontend_sources(FRONTEND/src).
    """
    lim = limit or BATCH_SIZE

    # Prefer explicit roots if provided or via env
    scan_roots = roots or _parse_scan_roots()
    if not scan_roots:
        return scan_frontend_sources(limit=lim)

    files: List[Path] = []
    for root in scan_roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".js", ".jsx", ".ts", ".tsx"):
                if "node_modules" in p.parts or "dist" in p.parts:
                    continue
                files.append(p)

    uniques = _dedupe_prefer_ts(files)
    scored  = recommend(uniques)
    chosen  = [p for (p, _s) in scored[:lim]]

    log(f"fetch_candidates: selected {len(chosen)} from {len(uniques)} uniques across {len(scan_roots)} roots")
    return chosen

# ==== 9) AIO-OPS | COMPAT: fetch_candidates - END =============================
# ==== 10) AIO-OPS | MULTI-AI REVIEW / GENERATE - START ========================

ARTIFACTS_DIR = Path("artifacts")
REVIEWS_DIR   = ARTIFACTS_DIR / "reviews"

def _norm_paths(cands: List[Any]) -> List[Path]:
    out: List[Path] = []
    for c in cands or []:
        p = Path(str(c))
        if p.exists() and p.is_file():
            out.append(p)
    return out

def _rel_from_frontend(p: Path) -> str:
    """Return a stable repo-side relative path (prefer under FRONTEND/src)."""
    try:
        p = p.resolve()
        src = (FRONTEND / "src").resolve()
        if str(p).startswith(str(src)):
            rel = p.relative_to(src).as_posix()
            return rel
    except Exception:
        pass
    # fallback: filename only
    return p.name

def _draft_stub_for(path: Path) -> str:
    """
    Produce a minimal TypeScript stub body.
    Later we can replace this with actual AST-guided synthesis + model calls.
    """
    banner = "// Auto-generated stub by Cod1 — safe placeholder\n"
    note   = f"// source: {path.as_posix()}\n"
    body   = "export {};\n"
    return banner + note + "\n" + body

def _write_stub(staging_root: Path, rel_repo_path: str) -> Path:
    """
    Create a .ts file inside staging_root mirroring rel_repo_path (extension forced to .ts).
    """
    rel = Path(rel_repo_path)
    # change extension to .ts
    if rel.suffix.lower() not in (".ts", ".tsx"):
        rel = rel.with_suffix(".ts")
    out_path = staging_root / rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("// placeholder\nexport {};\n", encoding="utf-8")
    return out_path

def _stage_stubs(run_id: str, files: List[Path]) -> Tuple[Path, List[Tuple[str, Path]]]:
    """
    Create stubs under artifacts/stubs/<run_id>/... and return (staging_root, [(repo_rel, local_path), ...]).
    """
    staging_root = ARTIFACTS_DIR / "stubs" / run_id
    staged: List[Tuple[str, Path]] = []
    for p in files:
        rel = _rel_from_frontend(p)
        out = _write_stub(staging_root, rel)
        # overwrite with more informative content
        out.write_text(_draft_stub_for(p), encoding="utf-8")
        staged.append((Path(rel).as_posix(), out))
    return staging_root, staged

def _save_run_review(run_id: str, staged: List[Tuple[str, Path]]) -> None:
    """
    Save a light review index (we’ll expand with model outputs later).
    """
    run_dir = REVIEWS_DIR / run_id / "Free"    # Free tier first
    run_dir.mkdir(parents=True, exist_ok=True)
    index = {
        "run_id": run_id,
        "count": len(staged),
        "items": [{"repo_rel": a, "local": str(b)} for (a, b) in staged],
        "tier": "Free",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json_report(index, run_dir / "index.json")

def process_batch_ext(source: str,
                      roots: Optional[List[str]],
                      cands: List[Any],
                      opts: Dict[str, Any],
                      run_id: str,
                      batch_limit: int = 999,
                      mode: str = "generate") -> List[Dict[str, Any]]:
    """
    Main entrypoint used by Cod1 scripts.

    Modes:
      - "cod1"     : delegate to the Cod1 continuity dispatcher (review→suggest→spec→generate→verify).
      - "generate" : default stub generation + upload to rolling/timestamp PR.

    Steps (generate mode): scan/normalize → dedupe/limit → generate stubs → save review → upload → return summary.
    """

    # Normalize and/or discover candidates
    paths = _norm_paths(cands)
    if not paths:
        # If no cands provided, fall back to scan_frontend_sources
        paths = scan_frontend_sources(limit=BATCH_SIZE)

    # Cap per run
    cap = min(BATCH_SIZE, int(batch_limit or BATCH_SIZE))
    paths = paths[:cap]

    if not paths:
        log("process_batch_ext: no candidates after filtering.")
        return []

    # ---- Mode dispatch -------------------------------------------------------
    if mode == "cod1":
        # Use Cod1 continuity pipeline dispatcher (defined at end of file).
        # It expects absolute file paths.
        gh_repo = opts.get("gh_repo") if isinstance(opts, dict) else None
        try:
            res = cod1([str(p) for p in paths], gh_repo=gh_repo)  # returns list of dicts
        except NameError:
            log("process_batch_ext[cod1]: cod1 dispatcher not available; falling back to no-op.")
            res = []
        return res
    # -------------------------------------------------------------------------

    # Default: stub generation + upload
    staging_root, staged = _stage_stubs(run_id, paths)

    # Persist a simple review bundle for this run
    _save_run_review(run_id, staged)

    # Upload stubs to GitHub (rolling PR logic handled in Section 11)
    repo_files: List[Tuple[str, Path]] = [(f"generated/{rel}", lp) for (rel, lp) in staged]
    try:
        upload_to_github(run_id, repo_files)  # defined in Section 11
    except NameError:
        log("WARN: upload_to_github not available at call-time; skipping upload.")
    except Exception as e:
        log(f"ERROR: upload_to_github failed: {e!r}")

    # Return concise group summary
    return [{
        "run_id": run_id,
        "source": source,
        "mode": mode,
        "count": len(paths),
        "staging": str(staging_root),
    }]

# ==== 10) AIO-OPS | MULTI-AI REVIEW / GENERATE - END ==========================

# ==== 11) AIO-OPS | GITHUB UPLOAD - START =====================================
def _gh_required():
    if not _repo:
        raise RuntimeError("GITHUB_TOKEN not set or repo init failed; cannot upload.")


def upload_to_github(run_id: str,
                     repo_files: List[Tuple[str, Path]],
                     base_branch: str = os.environ.get("AIO_BASE_BRANCH", "main"),
                     pr_title: Optional[str] = None,
                     pr_body: Optional[str] = None) -> str:
    """
    Push `repo_files` ([(repo_rel_path, local_path), ...]) to GitHub under
    either a per-run timestamp branch or a rolling branch, then open/reuse a draft PR.
    Returns the PR URL and writes it to reports/upload_<run_id>.txt.
    """
    _gh_required()

    # 0) Sanity
    repo_files = [(str(rp).replace("\\", "/"), Path(lp)) for (rp, lp) in repo_files]
    repo_files = [(rp, lp) for (rp, lp) in repo_files if lp.exists() and lp.is_file()]
    if not repo_files:
        raise ValueError("upload_to_github: no valid repo_files to upload")

    # 1) Resolve base commit
    base_ref = _repo.get_branch(base_branch)
    base_commit = base_ref.commit
    base_tree = base_commit.commit.tree

    # 2) Prepare blobs and tree elements
    from github import InputGitTreeElement as _IGTE  # local import to avoid top-level dependency
    elements = []
    for repo_rel, local_path in repo_files:
        content = local_path.read_text(encoding="utf-8", errors="ignore")
        blob = _repo.create_git_blob(content, "utf-8")
        elements.append(_IGTE(repo_rel, "100644", "blob", sha=blob.sha))

    new_tree = _repo.create_git_tree(elements, base_tree=base_tree)

    # 3) Create commit
    msg = pr_title or f"TS migration stubs (run {run_id})"
    new_commit = _repo.create_git_commit(msg, new_tree, [base_commit.commit])

    # 4) Decide head branch (rolling vs timestamp) — uses Cod1 chooser
    default_head = f"ts-migration/generated-{run_id}"
    head_branch = _cod1_branch_for_run(default_head, run_id)

    # 5) Move branch ref to our new commit (create if missing)
    ref_name = f"heads/{head_branch}"
    try:
        ref = _repo.get_git_ref(ref_name)              # OK to use "heads/<...>" for GET
        ref.edit(sha=new_commit.sha, force=True)
    except Exception:
        full_ref = ref_name if ref_name.startswith("refs/") else f"refs/{ref_name}"
        ref = _repo.create_git_ref(ref=full_ref, sha=new_commit.sha)  # MUST be "refs/heads/<...>"

    # 6) Reuse or open a draft PR
    existing = None
    for pr in _repo.get_pulls(state="open"):
        if pr.head.ref == head_branch and pr.base.ref == base_branch:
            existing = pr
            break

    if existing:
        pr = existing
    else:
        pr = _repo.create_pull(
            title=msg if head_branch == default_head else "TS migration stubs (rolling)",
            body=pr_body or f"Automated stubs upload for run {run_id}",
            head=head_branch,
            base=base_branch,
            draft=True,
        )

    # 7) Record PR URL for this run
    (REPORTS / f"upload_{run_id}.txt").write_text(pr.html_url, encoding="utf-8")

    log(f"upload_to_github: PR #{pr.number}  head={head_branch}  base={base_branch}")
    return pr.html_url
# ==== 11) AIO-OPS | GITHUB UPLOAD - END =======================================
# ==== 12) AIO-OPS | SG-Man multi-AI review hook - START =======================

def _latest_upload_txt() -> Optional[Path]:
    """Return the newest reports/upload_*.txt path (if any)."""
    if not REPORTS.exists():
        return None
    files = sorted(REPORTS.glob("upload_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read_pr_number_from_url(url: str) -> Optional[int]:
    """Extract PR number from a GitHub PR URL."""
    try:
        parts = url.rstrip("/").split("/")
        return int(parts[-1])
    except Exception:
        return None


def _comment_gates_to_pr(pr_number: int, run_id: str) -> None:
    """Post a summary of gates_<run_id>.json as a PR comment."""
    _gh_required()
    gates_path = REPORTS / f"gates_{run_id}.json"
    data = read_json_report(gates_path)
    if not data:
        log(f"_comment_gates_to_pr: gates file missing for run {run_id}: {gates_path}")
        return

    b = data["steps"].get("build", {})
    t = data["steps"].get("test", {})
    l = data["steps"].get("lint", {})

    body = (
        f"**Gates report {run_id}**\n\n"
        f"- build: pass={b.get('pass')} exit={b.get('exit')}\n"
        f"- test : pass={t.get('pass')} exit={t.get('exit')}\n"
        f"- lint : pass={l.get('pass')} exit={l.get('exit')}\n\n"
        f"(Frontend: `{data.get('frontend','?')}`; npm: `{(data.get('tooling') or {}).get('npm_bin','?')}`)"
    )

    pr = _repo.get_pull(pr_number)
    pr.create_issue_comment(body)
    log(f"commented gates on PR #{pr.number}")


def sgman_after_append(run_id: str, also_label: bool = True) -> None:
    """
    Run gates (if enabled) and comment the summary on the newest upload PR.
    Optionally ensure labels: ts-migration, analysis.
    """
    _gh_required()

    # 1) Run gates (honors AIO_RUN_GATES)
    gates_path = run_gates(run_id)
    log(f"sgman_after_append: wrote {gates_path}")

    # 2) Resolve newest upload PR URL
    up = _latest_upload_txt()
    if not up:
        log("sgman_after_append: no upload_*.txt files found; cannot comment.")
        return
    pr_url = up.read_text(encoding="utf-8").strip()
    pr_num = _read_pr_number_from_url(pr_url)
    if not pr_num:
        log(f"sgman_after_append: cannot parse PR number from {pr_url!r}")
        return

    # 3) Comment gates summary
    _comment_gates_to_pr(pr_num, run_id)

    # 4) Labels (idempotent)
    if also_label:
        try:
            def _ensure_label(name: str, color: str):
                try:
                    return _repo.get_label(name)
                except Exception:
                    return _repo.create_label(name=name, color=color)
            pr = _repo.get_pull(pr_num)
            pr.add_to_labels(_ensure_label("ts-migration", "0E8A16"),
                             _ensure_label("analysis", "5319E7"))
            log(f"sgman_after_append: labeled PR #{pr.number}")
        except Exception as e:
            log(f"sgman_after_append: label step skipped ({e!r})")

# ==== 12) AIO-OPS | SG-Man multi-AI review hook - END =========================

# ==== 13) AIO-OPS | ECOSYSTEM HELPERS — START =================================

# --- Cod1: rolling-PR chooser (import-safe; no run_id at import) ---------------
def _cod1_branch_for_run(default_branch: str, run_id: str) -> str:
    """
    Decide which head branch to use for uploads.
    - If AIO_UPLOAD_TS == "0" and AIO_UPLOAD_BRANCH is non-empty, return that.
    - Else fall back to `default_branch` (usually the timestamped one).
    """
    _env = os.environ
    rolling_on = (_env.get("AIO_UPLOAD_TS", "1").strip() == "0")
    rolling_nm = (_env.get("AIO_UPLOAD_BRANCH") or "").strip()
    if rolling_on and rolling_nm:
        return rolling_nm
    return default_branch
# ------------------------------------------------------------------------------


def env_keys_presence() -> Dict[str, bool]:
    """
    Presence-only check (never prints values).
    Keys: OPENAI_API_KEY, GEMINI_API_KEY, GROK_API_KEY, GITHUB_TOKEN.
    """
    keys = ["OPENAI_API_KEY", "GEMINI_API_KEY", "GROK_API_KEY", "GITHUB_TOKEN"]
    return {k: bool(os.environ.get(k)) for k in keys}


def write_cod1_status(run_id: str, pr_url: Optional[str]) -> Path:
    """
    Write a concise Cod1 status markdown in reports/debug/.
    """
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    p = DEBUG_DIR / f"cod1_report_{run_id[:12]}.md"
    gates_json = REPORTS / f"gates_{run_id}.json"
    gates = read_json_report(gates_json) or {}
    steps = gates.get("steps", {})
    build = steps.get("build", {})
    test  = steps.get("test", {})
    lint  = steps.get("lint", {})

    lines = [
        f"# Cod1 Report ({run_id})",
        "",
        "**Task:** 25-file batch to rolling PR + gates comment",
        f"**Run ID:** {run_id}",
        f"**PR URL:** {pr_url or 'n/a'}",
        "",
        f"**Gates JSON:** {gates_json.as_posix()}",
        f"- build.pass = {build.get('pass')}",
        f"- test.pass  = {test.get('pass')}",
        f"- lint.pass  = {lint.get('pass')}",
        "",
        "**Notes:**",
        f"- Rolling PR branch env: AIO_UPLOAD_TS={os.environ.get('AIO_UPLOAD_TS','?')} AIO_UPLOAD_BRANCH={os.environ.get('AIO_UPLOAD_BRANCH','?')}",
        f"- Frontend dir: `{FRONTEND}`",
        "- Encoding: UTF-8 (no BOM)",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _parse_csv_list(s: Optional[str]) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _now_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def _cli() -> int:
    r"""
    Minimal CLI:
      python -m app.ops --mode generate --limit 25 --files "C:\path\one.tsx,C:\path\two.ts"
    If --files omitted, falls back to scan_frontend_sources().
    After upload, runs sgman_after_append(run_id) to post gates comment and labels.
    """
    import argparse
    ap = argparse.ArgumentParser(prog="cod1-ops", description="CFH TS migration orchestrator")
    ap.add_argument("--mode", default="generate", choices=["generate"])
    ap.add_argument("--limit", type=int, default=BATCH_SIZE)
    ap.add_argument("--files", type=str, default="")
    ap.add_argument("--roots", type=str, default="")  # CSV of roots (optional)
    ap.add_argument("--run-id", type=str, default=_now_run_id())
    args = ap.parse_args()

    run_id = args.run_id
    files  = _parse_csv_list(args.files)
    roots  = _parse_csv_list(args.roots)

    # Normalize files -> Paths
    cands: List[str] = files
    group = process_batch_ext(
        source="cli",
        roots=roots or None,
        cands=cands,
        opts={},
        run_id=run_id,
        batch_limit=args.limit,
        mode=args.mode,
    )

    # Try to find the PR URL written by upload_to_github
    upload_txt = REPORTS / f"upload_{run_id}.txt"
    pr_url = upload_txt.read_text(encoding="utf-8").strip() if upload_txt.exists() else None

    # Gates + comment + labels
    try:
        sgman_after_append(run_id)
    except Exception as e:
        log(f"sgman_after_append failed: {e!r}")

    # Final status file
    status_md = write_cod1_status(run_id, pr_url)
    log(f"cod1 status: {status_md.as_posix()}")
    return 0


if __name__ == "__main__":
    # Only execute when run as a script, never at import.
    try:
        sys.exit(_cli())
    except KeyboardInterrupt:
        sys.exit(130)

# ==== 13) AIO-OPS | ECOSYSTEM HELPERS — END ===================================


# ==== 14) AIO-OPS | COD1 CONTINUITY HOOKS - START ============================

# Import-safe: we only wire the pipeline if the helper module is present.
try:
    from app.cod1_continuity import cod1_pipeline_for_file
except Exception as _e:
    cod1_pipeline_for_file = None  # fallback if module missing

# Lightweight dispatcher used by process_batch_ext(mode="cod1").
# Accepts absolute file paths and optional gh_repo.
if "cod1" not in globals():
    from typing import Optional, List

    def cod1(file_paths: List[str], gh_repo: Optional[str] = None) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if cod1_pipeline_for_file is None:
            return results
        for fp in file_paths:
            try:
                res = cod1_pipeline_for_file(Path(fp), gh_repo=gh_repo)
                # ensure a dict result shape
                if isinstance(res, dict):
                    results.append(res)
                else:
                    results.append({"file": fp, "result": res})
            except Exception as e:
                results.append({"error": str(e), "file": fp})
        return results

# ==== 14) AIO-OPS | COD1 CONTINUITY HOOKS - END ==============================
