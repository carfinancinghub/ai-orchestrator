# --- Cod1: compute head branch (rolling if enabled) ---
_default_branch = f"ts-migration/generated-{run_id}"
head_branch     = _cod1_branch_for_run(_default_branch, run_id)

# Move/point the branch ref to our new commit
ref_name = f"heads/{head_branch}"
try:
    ref = repo.get_git_ref(ref_name)
    ref.edit(sha=new_commit.sha, force=True)
except Exception:
    ref = repo.create_git_ref(ref=ref_name, sha=new_commit.sha)

# Reuse/open a PR targeting the same head/base
existing = None
for pr in repo.get_pulls(state="open"):
    if pr.head.ref == head_branch and pr.base.ref == base_branch:
        existing = pr
        break

if existing:
    pr = existing
else:
    pr = repo.create_pull(
        title=f"TS migration stubs (run {run_id})" if head_branch == _default_branch else "TS migration stubs (rolling)",
        body=f"Automated stubs upload for run {run_id}",
        head=head_branch,
        base=base_branch,
        draft=True,
    )

# Record the PR URL for this run (status scripts rely on this file)
(Path("reports")/f"upload_{run_id}.txt").write_text(pr.html_url, encoding="utf-8")
# --- /Cod1 branch & PR ---
# Purpose:
#   Core operations for scanning, scoring, reviewing, and generating frontend
#   artifacts. This module powers the CLI in app/ops_cli.py and writes reports
#   and stubs under ./reports and ./artifacts.
#
# Public API (imported by app/ops_cli.py):
#   - fetch_candidates(...)                          # local scanner - groups by basename
#   - filter_cryptic(...), write_grouped_files(...)  # helper utilities
#   - worth_score_and_reco(paths)                    # heuristic score + recommendation
#   - extract_js_functions(text)                     # JS/TS fuzzy function extraction
#   - extract_js_functions_ast(path, text?)          # AST (acorn) extractor with fallback
#   - process_batch_ext(..., mode=...)               # multi-AI review/generate wrapper
#   - process_batch(...)                             # compat wrapper
#   - scan_special(...), process_special(..., ...)   # SPECIAL pipeline
#   - run_gates(run_id)                              # gated build/test/lint (safe by default)
#   - upload_generated_to_github(...)                # optional GitHub upload of stubs
#
# Inputs / Outputs (relative to repo root):
#   - reports/
#       grouped_files.txt
#       review_multi_<run_id>.json
#       review_summary_special_<run_id>.json
#       special_scan_<run_id>.json
#       special_inventory_<run_id>.csv
#       gates_<run_id>.json
#       _last_review.txt
#   - artifacts/
#       generated/<base>.ts
#       _staged_all/src/components/<base>.ts
#       _staged_all/src/tests/<base>.test.tsx
#
# Environment Variables:
#   - AIO_RUN_GATES    : "1" to actually run npm build/test/lint; else skip
#   - AIO_FRONTEND_DIR : path to frontend (default C:/Backup_Projects/CFH/frontend)
#   - AIO_FRONTEND_ROOT: optional alias for AIO_FRONTEND_DIR
#   - OPENAI_API_KEY   : optional; presence logged only (no network calls)
#   - GEMINI_API_KEY   : optional; presence logged only (no network calls)
#   - GROK_API_KEY     : optional; presence logged only (no network calls)
#   - AIO_UPLOAD_TS    : "1" to attempt GitHub upload of generated stubs
#   - AIO_TARGET_REPO  : "<owner>/<repo>" for upload destination
#   - GITHUB_TOKEN     : PAT for upload
#
# Conventions:
#   - Timestamp format       : YYYYMMDD_HHMMSS
#   - Test file detection    : /.test.|.spec./i (e.g., foo.test.tsx)
#   - Supported extensions   : .js, .jsx, .ts, .tsx (plus .mjs/.mts where noted)
#   - Scoring heuristic      : tests (+25), mixed - siblings (+35), group size
#   - Stub naming            : sanitized base name - <base>.ts
#
# SPDX-License-Identifier: MIT
# Last-Updated: 2025-09-14
# ==== 0) AIO-OPS | STANDARD FILE HEADER - END =================================

# ==== 1) AIO-OPS | IMPORTS & CONSTANTS - START ================================
import os, re, json, csv, hashlib, time, subprocess, shlex
from pathlib import Path
from app.path_filters import is_skipped
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Core dirs (created on import)
_REPORTS = Path("reports")
_ARTIFACTS = Path("artifacts")
_GENERATED = _ARTIFACTS / "generated"
_STAGED_ALL = _ARTIFACTS / "_staged_all"
_REPORTS.mkdir(parents=True, exist_ok=True)
_GENERATED.mkdir(parents=True, exist_ok=True)
_STAGED_ALL.mkdir(parents=True, exist_ok=True)

# File kinds & quick patterns
_JS_TS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".mts"}
_TEST_RX = re.compile(r"(?:\.test\.|\.spec\.)", re.I)
_LETTERS_ONLY_RX = re.compile(r"^[A-Za-z]+$")
# ==== 1) AIO-OPS | IMPORTS & CONSTANTS - END ==================================

# ==== 2) AIO-OPS | HELPERS - START ===========================================
def _now_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

def _hash(s: Any) -> str:
    try:
        return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:8]
    except Exception:
        return "00000000"

def _coerce_path(obj: Any) -> Optional[Path]:
    if obj is None:
        return None
    if isinstance(obj, Path):
        return obj
    if isinstance(obj, str):
        return Path(obj)
    if isinstance(obj, dict):
        for k in ("path", "file", "src"):
            v = obj.get(k)
            if isinstance(v, str):
                return Path(v)
    return None

def _iter_candidate_paths(candidates: Any) -> Iterable[Path]:
    """Yield Path objects from many shapes: list/tuple/set, dicts, nested groups, etc."""
    if not candidates:
        return []
    def _walk(x: Any):
        if x is None:
            return
        if isinstance(x, (list, tuple, set)):
            for it in x:
                yield from _walk(it)
            return
        if isinstance(x, dict):
            if any(k in x for k in ("path","file","src")):
                p = _coerce_path(x)
                if p:
                    yield p
                return
            for v in x.values():
                yield from _walk(v)
            return
        p = _coerce_path(x)
        if p:
            yield p

    for p in _walk(candidates):
        if p.exists() and (p.suffix.lower() in _JS_TS_EXTS):
            yield p

def _sanitize_base(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)

def _safe_read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _group_by_base(paths: Iterable[Path]) -> Dict[str, List[Path]]:
    groups: Dict[str, List[Path]] = {}
    for p in paths:
        groups.setdefault(p.stem, []).append(p)
    return groups
# ==== 2) AIO-OPS | HELPERS - END =============================================

# ==== 3) AIO-OPS | GROUPING & FILTERS - START =================================
def filter_cryptic(candidates: Any) -> List[Path]:
    """
    Drop obviously cryptic basenames like '$I2H07PR.test.ts'.
    Accepts list[str|Path|{path:...}|mixed]; returns flat list[Path].
    """
    out: List[Path] = []
    for p in _iter_candidate_paths(candidates):
        base = p.stem
        # starts with $I****** (Windows temp) > drop
        if re.match(r"^\$I[A-Z0-9]{5,}$", base):
            continue
        # too many non-letters vs letters > drop
        if len(re.sub(r"[A-Za-z]", "", base)) > max(4, len(base) // 2):
            continue
        out.append(p)
    return out

def write_grouped_files(candidates: Any, out_path: str = "reports/grouped_files.txt") -> str:
    groups = _group_by_base(_iter_candidate_paths(candidates))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for base in sorted(groups.keys()):
            fh.write(f"{base}: {', '.join(str(p) for p in groups[base])}\n")
    return str(out)
# ==== 3) AIO-OPS | GROUPING & FILTERS - END ===================================

# ==== 4) AIO-OPS | FUNCTION EXTRACTION - START ================================
_FUNC_PATTERNS = [
    re.compile(r"\bfunction\s+([A-Za-z0-9_]+)\s*\(", re.M),
    re.compile(r"\bconst\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.M),
    re.compile(r"\bexport\s+function\s+([A-Za-z0-9_]+)\s*\(", re.M),
    re.compile(r"\bexport\s+default\s+function\s+([A-Za-z0-9_]+)?\s*\(", re.M),
    re.compile(r"\bclass\s+([A-Za-z0-9_]+)\b", re.M),  # include classes for review context
]

def extract_js_functions(src_text: str) -> List[str]:
    names: List[str] = []
    for rx in _FUNC_PATTERNS:
        for m in rx.finditer(src_text or ""):
            nm = (m.group(1) or "").strip()
            if nm and nm not in names:
                names.append(nm)
    return names
# ==== 4) AIO-OPS | FUNCTION EXTRACTION - END ==================================

# ==== 5) AIO-OPS | ACORN EXTRACTOR - START ====================================
def _node_has_acorn() -> bool:
    """Return True if `node` is available and can require('acorn')."""
    try:
        p = subprocess.run(["node", "-e", "require('acorn')"], capture_output=True, text=True)
        return p.returncode == 0
    except Exception:
        return False

def _extract_with_acorn_one(path: Path) -> List[str]:
    """
    Use Node + acorn (+ jsx/typescript plugins if available) to extract
    function/class names from a single JS/TS/TSX/JSX file. Returns [] on failure.
    """
    script = r"""
const fs = require('fs');
function tryReq(n){ try { return require(n); } catch { return null; } }
const acorn = tryReq('acorn') || require('acorn');
const acornJsx = tryReq('acorn-jsx');
const acornTs  = tryReq('acorn-typescript');

const filename = process.argv[2];
const src = fs.readFileSync(filename, 'utf8');

let Parser = acorn.Parser;
if (acornJsx) Parser = Parser.extend(acornJsx());
if (acornTs)  Parser = Parser.extend(acornTs());

let tree;
try {
  tree = Parser.parse(src, { ecmaVersion: 'latest', sourceType: 'module' });
} catch (e) {
  console.error('PARSE_ERR', e.message);
  console.log('[]');
  process.exit(0);
}

const names = new Set();
function add(n){ if(n) names.add(n); }

function walk(node){
  if (!node || typeof node !== 'object') return;
  switch(node.type){
    case 'FunctionDeclaration':
      add(node.id && node.id.name);
      break;
    case 'VariableDeclaration':
      for (const d of node.declarations || []) {
        if (d.id && d.id.name && (d.init && (d.init.type === 'ArrowFunctionExpression' || d.init.type === 'FunctionExpression'))) {
          add(d.id.name);
        }
      }
      break;
    case 'ClassDeclaration':
      add(node.id && node.id.name);
      break;
  }
  for (const k of Object.keys(node)) {
    const v = node[k];
    if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') walk(v);
  }
}

walk(tree);
console.log(JSON.stringify(Array.from(names)));
"""
    try:
        tmp = _REPORTS / "_tmp_acorn.js"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(script, encoding="utf-8")
        p = subprocess.run(["node", str(tmp), str(path)], capture_output=True, text=True, timeout=20)
        if p.returncode == 0 and (p.stdout or "").strip().startswith("["):
            return json.loads(p.stdout.strip())
    except Exception:
        pass
    return []

def extract_js_functions_ast(path: Path, fallback_text: Optional[str] = None) -> List[str]:
    """
    Prefer AST-based extraction (Node+acorn); fallback to regex extractor.
    """
    if _node_has_acorn():
        names = _extract_with_acorn_one(path)
        if names:
            return names
    txt = fallback_text if fallback_text is not None else _safe_read_text(path)
    return extract_js_functions(txt)
# ==== 5) AIO-OPS | ACORN EXTRACTOR - END ======================================

# ==== 6) AIO-OPS | WORTH SCORE & RECOMMENDATION - START =======================
def worth_score_and_reco(paths: List[Path]) -> Tuple[int, str]:
    score = 10
    has_test = any(_TEST_RX.search(p.name) for p in paths)
    has_js   = any(p.suffix.lower() in {".js", ".jsx"} for p in paths)
    has_ts   = any(p.suffix.lower() in {".ts", ".tsx"} for p in paths)
    if has_test: score += 25
    if has_js and has_ts: score += 35
    if len(paths) >= 3: score += 10
    score = max(0, min(100, score))
    reco = "discard" if score < 30 else ("keep" if score < 60 else "merge")
    return score, reco
# ==== 6) AIO-OPS | WORTH SCORE & RECOMMENDATION - END =========================

# ==== 7) AIO-OPS | GATES - START ==============================================
def run_gates(run_id: str) -> str:
    """
    Writes reports/gates_<run_id>.json.
    If AIO_RUN_GATES=1, runs npm build/test/lint in AIO_FRONTEND_DIR/AIO_FRONTEND_ROOT.

    Honors AIO_NPM_BIN for the npm path. If it's a PowerShell shim (.ps1),
    try to use a sibling npm.cmd/npm.exe. For .cmd/.bat, wrap with
    ['cmd.exe', '/c', ...] to keep shell=False.
    """
    rpt = _REPORTS
    rpt.mkdir(parents=True, exist_ok=True)
    out = rpt / f"gates_{run_id}.json"

    payload: Dict[str, Any] = {
        "run_id": run_id,
        "timestamp": time.time(),
        "dry_run": os.getenv("AIO_RUN_GATES", "0") != "1",
    }

    def _try(cmd: List[str], cwd: Optional[str] = None, cap: int = 120) -> Dict[str, Any]:
        try:
            p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=cap, shell=False)
            tail = (p.stdout or "").splitlines()[-15:] + (p.stderr or "").splitlines()[-15:]
            return {"cmd": " ".join(cmd), "exit": p.returncode, "pass": p.returncode == 0, "tail": tail}
        except Exception as e:
            return {"cmd": " ".join(cmd), "exit": -1, "pass": False, "tail": [str(e)]}

    def _wrap_cmd(npm_bin: str, args: List[str]) -> List[str]:
        nb = (npm_bin or "npm").strip('"')
        # .cmd/.bat must run via command interpreter on Windows
        if nb.lower().endswith((".cmd", ".bat")):
            return ["cmd.exe", "/c", nb] + args
        return [nb] + args

    if os.getenv("AIO_RUN_GATES", "0") == "1":
        default_fe = r"C:/Backup_Projects/CFH/frontend"
        fe = os.getenv("AIO_FRONTEND_DIR") or os.getenv("AIO_FRONTEND_ROOT") or default_fe
        npm = os.getenv("AIO_NPM_BIN") or "npm"

        # If pointed at a PowerShell shim, try a sibling npm.cmd/npm.exe
        if npm.lower().endswith(".ps1"):
            ps = Path(npm)
            for cand in ("npm.cmd", "npm.exe"):
                alt = ps.with_name(cand)
                if alt.exists():
                    npm = str(alt)
                    break

        payload["frontend"] = fe
        payload["tooling"] = {"npm_bin": npm}

        payload["steps"] = {
            "build": _try(_wrap_cmd(npm, ["run", "build"]), cwd=fe, cap=180),
            "test":  _try(_wrap_cmd(npm, ["test"]),        cwd=fe, cap=240),
            "lint":  _try(_wrap_cmd(npm, ["run", "lint"]), cwd=fe, cap=120),
        }
    else:
        payload["steps"] = {
            "build": {"exit": -1, "pass": False, "tail": ["skipped: AIO_RUN_GATES!=1"]},
            "test":  {"exit": -1, "pass": False, "tail": ["skipped: AIO_RUN_GATES!=1"]},
            "lint":  {"exit": -1, "pass": False, "tail": ["skipped: AIO_RUN_GATES!=1"]},
        }

    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(out)
# ==== 7) AIO-OPS | GATES - END ================================================

# ==== 8) AIO-OPS | SPECIAL SCAN & PROCESS - START =============================
def scan_special(
    roots: List[str],
    exts: List[str],
    extra_skips: List[str],
    run_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    run_id = run_id or f"special_{_now_id()}_{_hash(roots)}"
    exts_set = {"." + e.lower().lstrip(".") for e in (exts or ["js","jsx","ts","tsx","md"]) }
    skip_terms = [s.lower() for s in (extra_skips or []) if s]

    paths: List[Path] = []
    for root in roots or []:
        rp = Path(root)
        if not rp.exists():
            continue
        for p in rp.rglob("*"):
            if not p.is_file():
                continue
            parts_lower = [seg.lower() for seg in p.parts]
            if any(st in parts_lower or any(st in seg for seg in parts_lower) for st in skip_terms):
                continue
            if p.suffix.lower() in exts_set:
                paths.append(p)

    items: List[Dict[str, Any]] = []
    for p in paths:
        items.append({
            "path": str(p),
            "base": p.stem,
            "ext": p.suffix.lstrip(".").lower(),
            "category": "test" if _TEST_RX.search(p.name) else ("letters_only" if _LETTERS_ONLY_RX.match(p.stem) else "other"),
        })

    # grouped files (for quick eyeballing)
    grouped_out = _REPORTS / "grouped_files.txt"
    groups: Dict[str, List[str]] = {}
    for p in paths:
        groups.setdefault(p.stem, []).append(str(p))
    with grouped_out.open("w", encoding="utf-8") as fh:
        for base in sorted(groups.keys()):
            fh.write(f"{base}: {', '.join(groups[base])}\n")

    # inventory CSV
    inv_csv = _REPORTS / f"special_inventory_{run_id}.csv"
    with inv_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["base", "ext", "category", "path"])
        for it in items:
            w.writerow([it["base"], it["ext"], it["category"], it["path"]])

    # summary json
    summary_json = _REPORTS / f"special_scan_{run_id}.json"
    summary_json.write_text(json.dumps({
        "run_id": run_id,
        "counts": {"items": len(items), "groups": len(groups)},
        "outputs": {"grouped_files": str(grouped_out), "inventory_csv": str(inv_csv)},
    }, indent=2), encoding="utf-8")

    return items


def process_special(
    items: List[Dict[str, Any]],
    run_id: str,
    limit: int = 100,
    mode: str = "review",
) -> List[Dict[str, Any]]:
    mode = (mode or "review").lower()
    out_art = _ARTIFACTS / "generations_special"
    out_art.mkdir(parents=True, exist_ok=True)

    # group per base
    groups: Dict[str, List[str]] = {}
    for it in items[: max(0, limit)]:
        groups.setdefault(it["base"], []).append(it["path"])

    def _ws_and_reco(paths: List[str]) -> Tuple[int, str]:
        names = [str(Path(p)).lower() for p in paths]
        score = 10
        if any(".test." in n or ".spec." in n for n in names): score += 25
        has_js = any(n.endswith(".js") or n.endswith(".jsx") for n in names)
        has_ts = any(n.endswith(".ts") or n.endswith(".tsx") for n in names)
        if has_js and has_ts: score += 35
        score = max(0, min(100, score))
        reco = "discard" if score < 30 else ("keep" if score < 60 else "merge")
        return score, reco

    results: List[Dict[str, Any]] = []
    for base, paths in sorted(groups.items()):
        score, reco = _ws_and_reco(paths)

        gen_path = None
        if mode in {"generate", "all"}:
            safe = _sanitize_base(base)
            stub = f"""// Special stub for {base}
// worth_score: {score} | recommendation: {reco}
export const { safe } = () => null;
"""
            gen_path = out_art / f"{safe}.ts"
            try:
                gen_path.write_text(stub, encoding="utf-8")
            except Exception:
                gen_path = None

        results.append({
            "base": base,
            "paths": paths,
            "worth_score": score,
            "recommendation": reco,
            "artifact": str(gen_path) if gen_path else None,
        })

    out_json = _REPORTS / f"review_summary_special_{run_id}.json"
    out_json.write_text(json.dumps({"run_id": run_id, "mode": mode, "results": results}, indent=2), encoding="utf-8")
    return results
# ==== 8) AIO-OPS | SPECIAL SCAN & PROCESS - END ===============================

# ==== 9) AIO-OPS | COMPAT: fetch_candidates - START ===========================
def fetch_candidates(
    org: Optional[str] = None,
    user: Optional[str] = None,
    repo_name: Optional[str] = None,
    platform: str = "local",
    token: Optional[str] = None,
    run_id: Optional[str] = None,
    branches: Optional[List[str]] = None,
    local_inventory_paths: Optional[List[str]] = None,
) -> Tuple[List[Path], Dict[str, List[Path]], Dict[str, Any]]:
    """
    Lightweight local fetch:
      - roots from AIO_SCAN_ROOTS (CSV) if set; else [cwd, C:/Backup_Projects/CFH/frontend if exists]
      - includes: *.js, *.jsx, *.ts, *.tsx
      - skips: node_modules, dist, .git (+ AIO_SKIP_DIRS)
    Returns: (candidates, bundles_by_base, repos_meta)
    """
    roots: List[Path] = []
    env_roots = os.getenv("AIO_SCAN_ROOTS")
    if env_roots:
        for r in [p.strip() for p in env_roots.replace(";", ",").split(",") if p.strip()]:
            rp = Path(r)
            if rp.exists():
                roots.append(rp)
    else:
        roots = [Path.cwd()]
        default_fe = Path(r"C:/Backup_Projects/CFH/frontend")
        if default_fe.exists():
            roots.append(default_fe)

    skip_terms = {"node_modules", "dist", ".git"}
    extra_skips = {s.strip().lower() for s in (os.getenv("AIO_SKIP_DIRS", "") or "").replace(";", ",").split(",") if s.strip()}
    skip_terms |= extra_skips

    candidates: List[Path] = []
    for root in roots:
        for p in root.rglob("*"):
            if is_skipped(p) or (not p.is_file()):
                continue
            parts_lower = [seg.lower() for seg in p.parts]
            if any(st in parts_lower or any(st in seg for seg in parts_lower) for st in skip_terms):
                continue
            if p.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
                candidates.append(p)

    # optional filtering
    try:
        clean = filter_cryptic(candidates)  # type: ignore
    except Exception:
        clean = candidates

    # group by basename
    bundles: Dict[str, List[Path]] = {}
    for p in clean:
        bundles.setdefault(p.stem, []).append(p)

    repos = {"platform": platform, "roots": [str(r) for r in roots]}
    return clean, bundles, repos
# ==== 9) AIO-OPS | COMPAT: fetch_candidates - END =============================

# ==== 10) AIO-OPS | MULTI-AI REVIEW / GENERATE - START ========================
def _make_stub_for_base(base: str, score: int, reco: str) -> str:
    safe = _sanitize_base(base)
    return f"""// Auto-generated stub for base: {base}
// worth_score: {score} | recommendation: {reco}
export function {safe}(...args: any[]): any {{
  return null;
}}
"""

def process_batch_ext(
    platform: str,
    token: Optional[str],
    candidates: Any,
    bundle_by_src: Any,
    run_id: str,
    batch_offset: int = 0,
    batch_limit: int = 50,
    mode: str = "all",
) -> List[Dict[str, Any]]:
    """
    Minimal, local-only implementation:
    - scores groups, extracts function names (regex + optional acorn)
    - writes TS stubs to artifacts/generated
    - stages a copy under artifacts/_staged_all/src/components or src/tests
    - returns review JSON payload compatible with ops_cli expectations
    """
    mode = (mode or "all").lower()
    groups: Dict[str, List[Path]] = {}

    # collect from candidates
    for p in _iter_candidate_paths(candidates):
        groups.setdefault(p.stem, []).append(p)
    # include anything in bundle_by_src too
    if isinstance(bundle_by_src, dict):
        for k, v in bundle_by_src.items():
            for p in _iter_candidate_paths(v):
                groups.setdefault(k, []).append(p)

    bases = sorted(groups.keys())
    if batch_limit > 0:
        bases = bases[batch_offset : batch_offset + batch_limit]

    results: List[Dict[str, Any]] = []
    gen_paths: List[Path] = []

    for base in bases:
        paths = groups.get(base, [])
        score, reco = worth_score_and_reco(paths)
        func_names: List[str] = []
        if paths:
            p0 = paths[0]
            text = _safe_read_text(p0)
            func_names = extract_js_functions_ast(p0, text)

        gen_path = None
        stage_path = None
        if mode in {"generate", "persist", "all"}:
            stub = _make_stub_for_base(base, score, reco)
            gen_path = _GENERATED / f"{_sanitize_base(base)}.ts"
            gen_path.write_text(stub, encoding="utf-8")
            gen_paths.append(gen_path)

            # Stage: tests - src/tests, others - src/components
            target_dir = _STAGED_ALL / ("src/tests" if _TEST_RX.search(base) else "src/components")
            target_dir.mkdir(parents=True, exist_ok=True)
            stage_name = f"{_sanitize_base(base)}.test.tsx" if _TEST_RX.search(base) else f"{_sanitize_base(base)}.ts"
            stage_path = target_dir / stage_name
            stage_path.write_text(stub, encoding="utf-8")

        results.append({
            "base": base,
            "files": [str(p) for p in paths],
            "functions": func_names,
            "worth_score": score,
            "recommendation": "keep" if reco == "keep" else ("merge" if reco == "merge" else "discard"),
            "generated": str(gen_path) if gen_path else None,
            "staged": str(stage_path) if stage_path else None,
        })

    # write a review file for the run + pointer
    review_path = _REPORTS / f"review_multi_{run_id}.json"
    review_path.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    (_REPORTS / "_last_review.txt").write_text(str(review_path), encoding="utf-8")

            # Optional: upload to GitHub if requested
    if os.getenv("AIO_UPLOAD_TS", "0") == "1" and gen_paths:
        try:
            pr_url = upload_generated_to_github(run_id, gen_paths)
            if pr_url:
                (_REPORTS / f"upload_{run_id}.txt").write_text(pr_url, encoding="utf-8")
        except Exception as e:
            import traceback as _tb
            (_REPORTS / f"upload_err_{run_id}.txt").write_text(
                f"{e}\n\n{_tb.format_exc()}",
                encoding="utf-8",
            )

    return results



def process_batch(
    platform: str,
    token: Optional[str],
    candidates: Any,
    bundle_by_src: Any,
    run_id: str,
    batch_offset: int = 0,
    batch_limit: int = 50,
    mode: str = "all",
) -> List[Dict[str, Any]]:
    """Compatibility wrapper used by ops_cli."""
    return process_batch_ext(
        platform=platform,
        token=token,
        candidates=candidates,
        bundle_by_src=bundle_by_src,
        run_id=run_id,
        batch_offset=batch_offset,
        batch_limit=batch_limit,
        mode=mode,
    )
# ==== 10) AIO-OPS | MULTI-AI REVIEW / GENERATE - END ==========================

# ==== 11) AIO-OPS | GITHUB UPLOAD - START =====================================
# --- Cod1: rolling-PR chooser (non-breaking) ---
import os as _os

_AIO_UPLOAD_BRANCH = (_os.environ.get("AIO_UPLOAD_BRANCH") or "").strip()
_AIO_UPLOAD_TS     = (_os.environ.get("AIO_UPLOAD_TS") or "1").strip()

def _cod1_branch_for_run(default_branch: str, run_id: str) -> str:
    """
    If AIO_UPLOAD_TS == "0" and AIO_UPLOAD_BRANCH is set, always use that branch.
    Otherwise fall back to the timestamp branch name derived from run_id.
    """
    if _AIO_UPLOAD_TS == "0" and _AIO_UPLOAD_BRANCH:
        return _AIO_UPLOAD_BRANCH
    return default_branch  # caller typically passes f"ts-migration/generated-{run_id}"
# --- /Cod1 chooser ---

def upload_generated_to_github(run_id: str, generated_paths: List[Path]) -> Optional[str]:
    """
    Push generated TS files to a new branch 'ts-migration/generated-<run_id>'
    in repo specified by AIO_TARGET_REPO (e.g., 'carfinancinghub/cfh').
    Requires: GITHUB_TOKEN and PyGithub installed.
    Returns: PR URL (str) or None.
    """
    try:
        from github import Github, InputGitTreeElement, Auth  # PyGithub
    except Exception:
        return None

    token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("AIO_TARGET_REPO")
    if not token or not repo_name:
        return None

    # Ensure we actually have files to upload
    up_paths = [p for p in (generated_paths or []) if isinstance(p, Path) and p.exists()]
    if not up_paths:
        return None

    gh = Github(auth=Auth.Token(token))
    repo = gh.get_repo(repo_name)

    # Base branch, commit, and its tree (GitTree object, not just a SHA)
    base_branch = repo.default_branch
    base_ref = repo.get_branch(base_branch)
    base_commit = repo.get_commit(base_ref.commit.sha)
    base_tree = repo.get_git_tree(base_commit.sha)

    branch_name = f"ts-migration/generated-{run_id}"
    ref_name = f"refs/heads/{branch_name}"

    # Create branch from base (ignore if it already exists)
    try:
        repo.create_git_ref(ref=ref_name, sha=base_commit.sha)
    except Exception:
        pass

    # Build a tree with our files under 'generated/'
    elements = []
    for p in up_paths:
        rel_path = f"generated/{p.name}"
        content = p.read_text(encoding="utf-8")
        elements.append(
            InputGitTreeElement(
                path=rel_path,
                mode="100644",
                type="blob",
                content=content,
            )
        )

    tree = repo.create_git_tree(elements, base_tree)

    # Create a commit on the new tree, parented to base
    commit = repo.create_git_commit(
        f"feat(ts-migration): add generated stubs for run {run_id}",
        tree,
        [base_commit.commit],
    )

    # Move branch ref to our new commit
    ref = repo.get_git_ref(f"heads/{branch_name}")
    ref.edit(commit.sha, force=True)

    # Open a draft PR
    pr = repo.create_pull(
        title=f"TS migration stubs (run {run_id})",
        body="Automated upload from ai-orchestrator.",
        head=branch_name,
        base=base_branch,
        draft=True,
    )
    return pr.html_url
# ==== 11) AIO-OPS | GITHUB UPLOAD - END =======================================


# ==== 12) AIO-OPS | SG-Man multi-AI review hook - START =======================
# Non-destructive: thin wrapper that calls app.review_multi.run
# and (optionally) stages an upload plan via app.github_uploader if present.
# Keeps SG-Man-friendly names without overwriting existing implementations.

from typing import List as _ListType  # local alias to avoid any typing import issues

# Try to import the multi-review runner (scaffold you executed)
try:
    from app.review_multi import run as _run_reviews
except Exception:
    _run_reviews = None  # type: ignore

# Try to import a "plan" style uploader separate from this module's own uploader impl
try:
    from app.github_uploader import upload_generated_to_github as _stage_upload_plan
except Exception:
    _stage_upload_plan = None  # type: ignore

def process_batch_reviews(files: _ListType[str], run_id: str | None = None, root: str | None = None) -> list[str]:
    """
    SG-Man hook: batch review router (append-only).
    Produces artifacts/reviews/<run_id>/<tier>/... via app.review_multi.run
    Returns list of written JSON paths.
    """
    run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
    root   = root or os.getenv("AIO_FRONTEND_ROOT") or os.getenv("AIO_FRONTEND_DIR") or os.getcwd()

    if not _run_reviews:
        # Scaffold not available; keep it quiet & harmless.
        return []

    out = _run_reviews(files, run_id, root)

    # Optional: stage upload plan if the separate uploader supports it
    if _stage_upload_plan:
        try:
            plan = _stage_upload_plan(run_id)  # plan-style uploader (no paths arg)
            if plan:
                print(f"[upload-plan] {plan}")
        except Exception:
            # Never fail the run because of optional planning
            pass

    return out

# Back-compat alias ONLY if not already defined to avoid clobbering existing impl.
if "process_batch_ext" not in globals():
    process_batch_ext = process_batch_reviews  # type: ignore
# ==== 12) AIO-OPS | SG-Man multi-AI review hook - END =========================

# ==== 13) AIO-OPS | ECOSYSTEM HELPERS - START =================================
# These helpers are additive only and do not change sections 1â€“12.

from typing import Iterable as _IterableType

def scan_and_group_files(roots: List[str], exts: List[str]) -> Dict[str, List[str]]:
    """
    Scan roots and group files by base name. Skips common vendor dirs.
    Writes reports/grouped_files.txt for inspection.
    """
    allow = {"." + e.lower().lstrip(".") for e in (exts or ["js","jsx","ts","tsx","md"])}
    groups: Dict[str, List[str]] = {}
    skip_terms = {"node_modules", "dist", ".git", "build", "coverage", ".next", ".turbo"}
    out_txt = _REPORTS / "grouped_files.txt"
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    for root in roots or []:
        rp = Path(root)
        if not rp.exists():
            continue
        for p in rp.rglob("*"):
            if not p.is_file():
                continue
            parts_lower = [seg.lower() for seg in p.parts]
            if any(st in parts_lower or any(st in seg for seg in parts_lower) for st in skip_terms):
                continue
            if p.suffix.lower() in allow:
                groups.setdefault(p.stem, []).append(str(p))

    with out_txt.open("w", encoding="utf-8") as fh:
        for base in sorted(groups):
            fh.write(f"{base}: {', '.join(groups[base])}\n")
    return groups


def generate_ts_file(src_file: str, ai_reviews: Optional[Dict[str, Any]]=None, out_dir: Optional[Path]=None) -> str:
    """
    Create a simple TS/TSX stub for the given file. Adds TODOs from ai_reviews if present.
    Returns path to the generated file under artifacts/generated.
    """
    p = Path(src_file)
    base = _sanitize_base(p.stem)
    ts_name = base + (".tsx" if p.suffix.lower() in {".jsx", ".tsx"} else ".ts")
    out_dir = out_dir or _GENERATED
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / ts_name

    todos: List[str] = []
    if ai_reviews:
        for tier, payload in ai_reviews.items():
            try:
                summary = (payload.get("summary") or payload.get("hint") or "").strip()
            except Exception:
                summary = ""
            if summary:
                todos.append(f"[{tier}] {summary}")

    header = [
        f"// Auto-generated from: {p.name}",
        "// NOTE: Replace this stub with real conversion when ready.",
    ]
    if todos:
        header.append("// TODOs:")
        for t in todos[:8]:
            header.append(f"//  - {t}")

    body = f"""
export function {base}(...args: any[]): any {{
  return null;
}}
""".lstrip("\n")

    outp.write_text("\n".join(header) + "\n\n" + body, encoding="utf-8")
    return str(outp)


def review_generated_file(gen_file: str, original_reviews: Optional[Dict[str, Any]], reviewer: str, run_id: Optional[str]=None) -> Dict[str, Any]:
    """
    Lightweight verification: checks for exports, type annotations, and presence of suggested keywords.
    Writes artifacts/reviews/<run_id>/verify/<base>.json if run_id is given.
    """
    p = Path(gen_file)
    txt = _safe_read_text(p)
    checks = {
        "has_export": "export " in txt,
        "has_types_hint": (": " in txt) or ("interface " in txt) or ("type " in txt),
        "non_empty": bool(txt.strip()),
    }

    suggestions_present: List[str] = []
    suggestions_missing: List[str] = []
    if original_reviews:
        for tier, payload in original_reviews.items():
            try:
                s = (payload.get("summary") or "").lower()
            except Exception:
                s = ""
            hit = 0
            for key in ["type", "prop", "memo", "lazy", "refactor", "split", "config"]:
                if key in s and key in txt.lower():
                    hit += 1
            if hit:
                suggestions_present.append(tier)
            else:
                suggestions_missing.append(tier)

    result = {
        "file": str(p),
        "checks": checks,
        "suggestions_present_from_tiers": suggestions_present,
        "suggestions_missing_from_tiers": suggestions_missing,
        "reviewer": reviewer,
        "timestamp": time.time(),
    }

    if run_id:
        outv = _ARTIFACTS / "reviews" / run_id / "verify"
        outv.mkdir(parents=True, exist_ok=True)
        (outv / (p.stem + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def duplicate_elimination_wrapper(scan_roots: List[str]) -> Tuple[str, str]:
    """
    Thin wrapper around app.dedup. Returns (csv_path, txt_path).
    """
    try:
        from app.dedup import duplicate_elimination as _de
    except Exception as e:
        raise RuntimeError(f"dedup module missing: {e}")
    return _de(scan_roots)


def _offline_review_summary(path: str) -> Dict[str, Any]:
    p = Path(path)
    text = _safe_read_text(p)
    names = extract_js_functions(text)
    return {
        "model": "offline",
        "summary": f"Offline summary for {p.name}. functions: {', '.join(names[:10])}",
        "confidence": 0.25 + min(0.5, len(names)/50.0),
    }


def ai_review_file(path: str, tier: str) -> Dict[str, Any]:
    """
    Returns a dict with keys: model, summary, confidence.
    Live calls only if AIO_LIVE_AI=1 and the relevant key is set; otherwise returns offline stub.
    """
    live = os.getenv("AIO_LIVE_AI", "0") == "1"
    tier = (tier or "Free").strip()
    if not live:
        return _offline_review_summary(path)

    try:
        import requests  # noqa
    except Exception:
        return _offline_review_summary(path)

    text = _safe_read_text(Path(path))[:5000]

    if tier in ("Free", "Premium"):
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return _offline_review_summary(path)
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            prompt = f"Summarize main functions and TS typing hotspots:\n\n{text[:4000]}"
            data = {
                "model": os.getenv("AIO_OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": "You are a concise code reviewer."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 300,
                "temperature": 0.2,
            }
            r = requests.post(url, headers=headers, json=data, timeout=30)
            r.raise_for_status()
            out = r.json()
            content = (out.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
            return {"model": data["model"], "summary": content.strip(), "confidence": 0.7}
        except Exception:
            return _offline_review_summary(path)

    if tier == "Wow++":
        vendor = (os.getenv("AIO_LIVE_AI_VENDOR") or "").lower()
        try:
            import requests  # noqa
        except Exception:
            return _offline_review_summary(path)
        try:
            if vendor == "gemini" and os.getenv("GEMINI_API_KEY"):
                api_key = os.getenv("GEMINI_API_KEY")
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
                payload = {
                    "contents": [{"parts": [{"text": f"Advanced improvements for this code:\n\n{text[:4000]}"}]}]
                }
                r = requests.post(url, params={"key": api_key}, json=payload, timeout=30)
                r.raise_for_status()
                j = r.json()
                cand = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts", [{}])
                content = (cand[0].get("text") if cand else "") or ""
                return {"model": "gemini-1.5-flash", "summary": content.strip(), "confidence": 0.7}
            if vendor == "grok" and os.getenv("GROK_API_KEY"):
                api_key = os.getenv("GROK_API_KEY")
                url = "https://api.x.ai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                data = {
                    "model": os.getenv("AIO_GROK_MODEL", "grok-beta"),
                    "messages": [
                        {"role": "system", "content": "Expert frontend performance reviewer."},
                        {"role": "user", "content": f"Suggest non-trivial optimizations:\n\n{text[:4000]}"},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.2,
                }
                r = requests.post(url, headers=headers, json=data, timeout=30)
                r.raise_for_status()
                out = r.json()
                content = (out.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                return {"model": data["model"], "summary": content.strip(), "confidence": 0.7}
        except Exception:
            return _offline_review_summary(path)

    return _offline_review_summary(path)


def multi_ai_review_bundle(files: _IterableType[str], run_id: str) -> List[str]:
    """
    Produce tiered review JSONs:
      artifacts/reviews/<run_id>/<tier>/<rel>.json
    Uses ai_review_file(...) per tier, per file.
    """
    written: List[str] = []
    tiers = ("Free", "Premium", "Wow++")
    root = os.getenv("AIO_FRONTEND_ROOT") or os.getenv("AIO_FRONTEND_DIR") or os.getcwd()
    out_root = _ARTIFACTS / "reviews" / run_id

    for f in files:
        absf = os.path.abspath(f)
        root_abs = os.path.abspath(root)
        if absf.startswith(root_abs):
            rel = os.path.relpath(absf, root_abs)
        else:
            rel = os.path.basename(absf)

        for tier in tiers:
            payload = ai_review_file(absf, tier)
            outp = out_root / tier / (rel + ".json")
            outp.parent.mkdir(parents=True, exist_ok=True)
            outp.write_text(json.dumps({
                "file": rel,
                "tier": tier,
                "provider_hint": payload.get("model"),
                "summary": payload.get("summary"),
                "confidence": payload.get("confidence"),
                "ts": int(time.time()),
            }, indent=2), encoding="utf-8")
            written.append(str(outp))

    (_REPORTS / f"review_multi_{run_id}.json").write_text(json.dumps({"written": written}, indent=2), encoding="utf-8")
    return written

# ==== 13) AIO-OPS | ECOSYSTEM HELPERS - END ===================================
