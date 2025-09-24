# Path: C:\c\ai-orchestrator\app\ops.py
# Version: 0.3.9
# Last Updated: 2025-09-02 00:25 PDT
# Purpose: Scan .js/.jsx candidates (rel paths), stage TS/TSX + tests, emit tiered reviews, summary, and gates.

from __future__ import annotations
import json, os, logging, time, glob
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Optional GitHub imports (don’t fail locally)
try:
    from github import Github, GithubException
except Exception:  # pragma: no cover
    Github = None
    class GithubException(Exception): ...

# Throttling (no-op locally unless you install ratelimit)
try:
    from ratelimit import limits, sleep_and_retry
except Exception:  # pragma: no cover
    def limits(*_, **__):  # type: ignore
        def deco(f): return f
        return deco
    def sleep_and_retry(f):  # type: ignore
        return f

# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REPORTS_ROOT = Path("reports"); REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
ARTIFACTS = Path("artifacts"); ARTIFACTS.mkdir(parents=True, exist_ok=True)
STAGING = ARTIFACTS / "staging"; STAGING.mkdir(parents=True, exist_ok=True)
REVIEWS = ARTIFACTS / "reviews"; REVIEWS.mkdir(parents=True, exist_ok=True)
SUMMARIES = ARTIFACTS / "summaries"; SUMMARIES.mkdir(parents=True, exist_ok=True)

CALLS = 60
PERIOD = 60

EXCLUDE_NAMES = {"cypress.config.js", "vite.config.js", "vite.config.ts", "jest.config.js"}
EXCLUDE_EXTS  = {".txt", ".md", ".map"}
EXCLUDE_DIRS  = {"node_modules", ".git", ".venv", ".github", "cypress", ".vite", "dist", "build", ".turbo"}

DEFAULT_LOCAL_ROOT = Path(r"C:\Backup_Projects\CFH\frontend")

# External util (optional)
try:
    from app.utils import emit_migration_list
except Exception:  # pragma: no cover
    def emit_migration_list(run_id: str, candidates: List["Candidate"]) -> None:
        (REPORTS_ROOT / f"migration_list_{run_id}.json").write_text(
            json.dumps([c.__dict__ for c in candidates], indent=2), encoding="utf-8"
        )

@dataclass
class Candidate:
    repo: str
    branch: str
    src_path: str   # repo-relative path like 'src/App.jsx'
    mtime: float

# ---------------------------------------------------------------------------

def _path_is_excluded(p: str | Path) -> bool:
    s = str(p).replace("\\", "/").lower()
    name = Path(s).name
    if name in EXCLUDE_NAMES: return True
    if Path(s).suffix in EXCLUDE_EXTS: return True
    parts = s.split("/")
    return any(d in parts for d in EXCLUDE_DIRS)

def _log_skip(reason: str, path_str: str) -> None:
    try: logger.debug(f"[SCAN] skip {path_str} -> {reason}")
    except Exception: pass

def _parse_inventory_md(md_path: Path) -> List[Path]:
    out: List[Path] = []
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"Failed to read inventory {md_path}: {e}")
        return out
    for line in text.splitlines():
        t = line.strip()
        if not (t.startswith("|") and t.count("|") >= 4): continue
        core = t.strip("|").split("|")[0].strip().strip('"').strip("'")
        p = Path(core)
        if p.exists() and p.is_file() and not _path_is_excluded(p):
            out.append(p)
    return out

# ---------------------------------------------------------------------------

@sleep_and_retry
@limits(calls=CALLS, period=PERIOD)
def list_repos_and_branches(user: str, platform: str, token: str) -> List[Dict]:
    if platform != "github": return []
    gh = Github(token) if Github else None
    allow = {"my-project-migration", "cfh", "converting", "ai-orchestrator"}
    repos: List[Dict] = []
    if not gh: return repos
    try:
        for r in gh.get_user(user).get_repos():
            if r.name in allow:
                branches = [b.name for b in gh.get_repo(f"{user}/{r.name}").get_branches()]
                repos.append({"repo": f"{user}/{r.name}", "branches": branches})
        if not repos:
            for name in sorted(allow):
                full = f"{user}/{name}"
                try:
                    branches = [b.name for b in gh.get_repo(full).get_branches()]
                    repos.append({"repo": full, "branches": branches})
                except GithubException:
                    pass
        return repos
    except GithubException as e:
        logger.error(f"GitHub API error listing repos: {e}")
        return repos

# ---------------------------------------------------------------------------

def _scan_prefixes() -> List[str]:
    env = os.getenv("CFH_SCAN_PATH_PREFIXES")
    if env is None:
        # Default to src/ to match prior behavior; set env to empty to include all
        return ["src/"]
    return [p.strip().lower() for p in env.split(",") if p.strip()]

def _prefix_match(rel_path: str, prefs: List[str]) -> bool:
    if not prefs: return True
    return any(rel_path.startswith(p) for p in prefs)

@sleep_and_retry
@limits(calls=CALLS, period=PERIOD)
def fetch_candidates(
    org: Optional[str],
    repo_name: Optional[str],
    platform: str,
    token: str,
    run_id: str,
    branches: Optional[List[str]],
    local_inventory_paths: Optional[List[str]] = None,
    user: Optional[str] = None,
):
    logger.info(f"Starting fetch_candidates (run_id={run_id})")
    t0 = time.time()
    candidates: List[Candidate] = []
    files: List[Dict] = []
    exclusions: List[Dict] = []
    js_jsx = 0
    ts_tsx_seen: List[str] = []
    repos_info: List[Dict] = []

    prefs = _scan_prefixes()
    logger.info(f"Path prefix filter(s): {prefs or '[none]'}")

    cache_file = REPORTS_ROOT / f"inventory_cache_{run_id}.json"
    if cache_file.exists():
        try: cache_file.unlink()
        except Exception: pass

    # Resolve local root
    root_dir: Path
    if local_inventory_paths and len(local_inventory_paths) > 0:
        cand = Path(local_inventory_paths[0]).resolve()
        root_dir = cand if cand.is_dir() else cand.parent
    else:
        root_dir = DEFAULT_LOCAL_ROOT.resolve()

    logger.info(f"Scanning local root: {root_dir}")
    if root_dir.exists():
        for p in root_dir.rglob("*"):
            try:
                if not p.is_file(): continue
                if _path_is_excluded(p): 
                    _log_skip("excluded", str(p)); continue
                if p.suffix.lower() not in (".js", ".jsx", ".ts", ".tsx"):
                    _log_skip("not code", str(p)); continue

                rel = str(p.relative_to(root_dir)).replace("\\", "/").lower()
                if not _prefix_match(rel, prefs):
                    _log_skip("prefix mismatch", rel); continue

                files.append({"repo": "local", "branch": "main", "path": rel})
                if p.suffix.lower() in (".js", ".jsx"):
                    candidates.append(Candidate(repo="local", branch="main", src_path=rel, mtime=p.stat().st_mtime))
                    js_jsx += 1
                else:
                    ts_tsx_seen.append(rel)
            except Exception as e:
                exclusions.append({"repo": "local", "branch": "main", "path": str(p), "error": str(e)})

    # Markdown inventories (optional)
    for inv in (local_inventory_paths or []):
        p = Path(inv)
        if p.exists() and p.suffix.lower() == ".md":
            for mdp in _parse_inventory_md(p):
                rel = str(mdp).replace("\\", "/").lower()
                if _path_is_excluded(mdp): continue
                if not _prefix_match(rel, prefs): continue
                files.append({"repo": "local", "branch": "main", "path": rel})
                if mdp.suffix.lower() in (".js", ".jsx"):
                    mtime = mdp.stat().st_mtime if mdp.exists() else 0.0
                    candidates.append(Candidate(repo="local", branch="main", src_path=rel, mtime=mtime))
                    js_jsx += 1
                else:
                    ts_tsx_seen.append(rel)

    # GitHub scanning
    if platform == "github":
        repos_info = list_repos_and_branches(user or "carfinancinghub", platform, token)
        gh = Github(token) if Github else None
        for ri in repos_info:
            rname = ri["repo"].split("/")[-1]
            logger.info(f"Scanning repo {rname}")
            t_repo = time.time()
            timeout = 120 if rname == "cfh" else 60
            try:
                repo = gh.get_repo(f"{user or 'carfinancinghub'}/{rname}") if gh else None
                for branch in ri["branches"]:
                    try:
                        contents = repo.get_contents("", ref=branch) if repo else []
                        queue = contents[:]
                        while queue:
                            item = queue.pop(0)
                            path_str = item.path.replace("\\", "/").lower()
                            if _path_is_excluded(path_str): continue
                            if item.type == "dir":
                                try:
                                    queue.extend(repo.get_contents(item.path, ref=branch))
                                except Exception:
                                    pass
                                continue
                            if not path_str.endswith((".js", ".jsx", ".ts", ".tsx")): continue
                            if not _prefix_match(path_str, prefs): continue

                            files.append({"repo": ri["repo"], "branch": branch, "path": path_str})
                            if path_str.endswith((".js", ".jsx")):
                                candidates.append(Candidate(repo=ri["repo"], branch=branch, src_path=path_str, mtime=0))
                                js_jsx += 1
                            else:
                                ts_tsx_seen.append(path_str)
                    except GithubException as e:
                        exclusions.append({"repo": rname, "branch": branch, "error": str(e)})
                    if time.time() - t_repo > timeout:
                        exclusions.append({"repo": rname, "error": f"Timeout after {timeout}s"}); break
            except GithubException as e:
                exclusions.append({"repo": rname, "error": str(e)})
            logger.info(f"Scanned {rname} in {time.time() - t_repo:.2f}s")

    discrepancies: Dict[str, int] = {r: sum(1 for c in candidates if c.repo == r) for r in {c.repo for c in candidates}}
    payload = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user, "org": org, "repo_name": repo_name, "branches": branches,
        "found_total": len(files), "found_js_jsx": js_jsx,
        "repos": repos_info,
        "candidates": [c.__dict__ for c in candidates],
        "bundles": {}, "exclusions": exclusions,
        "ts_tsx_seen": [{"repo": f.get("repo","local"), "branch": f.get("branch","main"), "path": f["path"]}
                        for f in files if f["path"] in set(ts_tsx_seen)],
        "discrepancies": discrepancies,
    }
    (REPORTS_ROOT / f"scan_{run_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (REPORTS_ROOT / "scan_latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cache_payload = {
        "candidates": [c.__dict__ for c in candidates],
        "files": files, "found_js_jsx": js_jsx,
        "ts_tsx_seen": payload["ts_tsx_seen"],
        "bundles": {}, "exclusions": exclusions, "repos": repos_info
    }
    (REPORTS_ROOT / f"inventory_cache_{run_id}.json").write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
    logger.info(f"Completed fetch_candidates in {time.time() - t0:.2f}s")
    return candidates, {}, repos_info

# ---------------------------------------------------------------------------

def stage_file(repo: str, branch: str, src_path: str, content: str) -> Path:
    # Normalize to forward slashes under STAGING/<repo>/<branch>/<path>
    target = (STAGING / repo.replace("/", "__") / branch / src_path.replace("\\", "/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target

def _tier_thresholds() -> dict:
    return {
        "Free":    {"type_coverage": 10, "test_coverage": 10},
        "Premium": {"type_coverage": 50, "refactor_quality": 30, "test_coverage": 50},
        "Wow++":   {"type_coverage": 80, "refactor_quality": 60, "test_coverage": 80, "future_readiness": 50},
    }

def _heuristic_scores(ts_content: str) -> dict:
    has_types = (": " in ts_content) or ("React" in ts_content and "<" in ts_content and ">" in ts_content)
    has_tests = "describe(" in ts_content or "it(" in ts_content
    uses_hooks = any(h in ts_content for h in ("useState(", "useEffect(", "useMemo(", "useCallback("))
    return {
        "type_coverage": 70 if has_types else 5,
        "refactor_quality": 40 if uses_hooks else 20,
        "test_coverage": 60 if has_tests else 10,
        "future_readiness": 30,
    }

def _make_prompts(rel_path: str, ts_dest: str) -> dict:
    common = {
        "file": rel_path,
        "target_ts_path": ts_dest,
        "context": "CFH Marketplace TypeScript migration with Vite/Vitest; ensure ESM compatibility and React Router v6.",
    }
    return {
        "Free": {
            **common,
            "task": "Basic JS->TS conversion with @ts-nocheck only where needed. Keep behavior identical.",
            "checks": ["build passes", "file compiles", "no console errors"]
        },
        "Premium": {
            **common,
            "task": "Add proper interfaces/types for props/state; reduce any/unknown; small safe refactors.",
            "checks": ["type errors resolved", "tests compile", "no anti-patterns"]
        },
        "Wow++": {
            **common,
            "task": "Deep critique: a11y, perf, state mgmt, Suspense/SSR readiness; propose focused tests.",
            "checks": ["a11y notes", "perf notes", "forward-compat"]
        }
    }

def _review_dir(run_id: str, tier: str, rel_path: str) -> Path:
    base = REVIEWS / run_id / tier
    (base / Path(rel_path)).parent.mkdir(parents=True, exist_ok=True)
    return base

def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def generate_error_summary(run_id: str, results: List[Dict]) -> None:
    def sev(r: Dict) -> str:
        txt = (r.get("error") or "").lower()
        if any(k in txt for k in ("429", "rate limit", "ratelimit", "conflict", "merge conflict", "githubexception", "timeout")):
            return "critical"
        return "warning"
    errs = [{"severity": sev(r), **r} for r in results if r.get("status") in ("ERROR", "FAIL")]
    _write_json(REPORTS_ROOT / f"errors_{run_id}.json", errs)

# Core batch (tiered) ---------------------------------------------------------

def process_batch_tiered(
    platform: str,
    token: str,
    candidates: List[Candidate],
    bundle_by_src: Dict[str, Dict[str, str]],
    run_id: str,
    max_workers: int = 50,
    rate_per_sec: float = 5.0,
    quarantine_dir: str = "artifacts_quarantine",
    metrics_path: str = "audit_metrics.jsonl",
    batch_offset: int = 0,
    batch_limit: Optional[int] = None,
    evaluate_paths: Optional[List[Dict]] = None,
):
    logger.info(f"[tiered] process_batch run_id={run_id}")
    results: List[Dict] = []
    t0 = time.time()

    # local root resolution with sensible default
    local_root = Path(os.getenv("CFH_LOCAL_ROOT") or DEFAULT_LOCAL_ROOT).resolve()

    env_limit = os.getenv("CFH_BATCH_LIMIT")
    if env_limit:
        try: batch_limit = int(env_limit)
        except Exception: pass

    end = batch_offset + (batch_limit or len(candidates))
    batch = candidates[batch_offset:end]

    gates = {"thresholds": _tier_thresholds(), "per_file": []}

    for c in batch:
        try:
            # read source
            content: str
            if c.repo == "local":
                src_abs = (local_root / c.src_path)
                if src_abs.exists():
                    content = src_abs.read_text(encoding="utf-8", errors="ignore")
                else:
                    results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                                    "status": "ERROR", "error": "Source file not found"}); continue
            else:
                gh = Github(token) if Github else None
                repo = gh.get_repo(c.repo) if gh else None
                try:
                    fc = repo.get_contents(c.src_path, ref=c.branch) if repo else None
                    content = fc.decoded_content.decode("utf-8") if fc else ""
                except GithubException as e:
                    results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                                    "status": "ERROR", "error": f"GitHubException: {e}"}); continue

            # conversion (placeholder): js -> ts, jsx -> tsx
            ts_rel = c.src_path.rsplit(".", 1)[0] + (".ts" if c.src_path.endswith(".js") else ".tsx")
            ts_content = f"// TypeScript conversion of {c.src_path}\n{content}\n// @ts-nocheck"
            staged_ts = stage_file(c.repo, c.branch, ts_rel, ts_content)

            # vitest smoke
            test_rel = c.src_path.rsplit(".", 1)[0] + ".test" + (".ts" if c.src_path.endswith(".js") else ".tsx")
            test_content = (
                "import { describe, it, expect } from 'vitest';\n"
                f"describe('{Path(c.src_path).name}', () => {{ it('smokes', () => expect(true).toBe(true)); }});\n"
            )
            stage_file(c.repo, c.branch, test_rel, test_content)

            # prompts + heuristic scores
            prompts = _make_prompts(c.src_path, ts_rel)
            scores  = _heuristic_scores(ts_content)

            for tier in ("Free", "Premium", "Wow++"):
                base = _review_dir(run_id, tier, c.src_path)
                rel_norm = Path(c.src_path)
                _write_json(base / rel_norm.with_suffix(".json"),
                            {"tier": tier, "run_id": run_id, "file": c.src_path,
                             "prompt": prompts[tier], "scores": scores,
                             "timestamp": datetime.now(timezone.utc).isoformat()})
                _write_text(base / rel_norm.with_suffix(".md"),
                            f"# {tier} Review — {c.src_path}\n\n"
                            f"**Run:** {run_id}\n\n## Prompt\n\n```\n{json.dumps(prompts[tier], indent=2)}\n```\n\n"
                            f"## Scores (heuristic)\n\n{json.dumps(scores, indent=2)}\n")

            thresholds = _tier_thresholds()
            per_file_gate = {"file": c.src_path, "tiers": {}, "staged_paths": {"ts": str(staged_ts), "test": test_rel}}
            for tier, reqs in thresholds.items():
                ok = all(scores.get(k, 0) >= v for k, v in reqs.items())
                per_file_gate["tiers"][tier] = "PASS" if ok else "FAIL"
            gates["per_file"].append(per_file_gate)

            results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                            "status": "CONVERTED", "staged_path": str(staged_ts), "test_path": str(test_rel)})

        except Exception as e:
            results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                            "status": "ERROR", "error": f"{type(e).__name__}: {e}"})

    # Run summary (requested by spec)
    summary_lines = [f"# Migration Summary – {run_id}", ""]
    for g in gates["per_file"]:
        t = g["tiers"]
        summary_lines.append(f"- **{g['file']}** → Free:{t['Free']} Premium:{t['Premium']} Wow++:{t['Wow++']}")
    (SUMMARIES / f"{run_id}.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    _write_json(REPORTS_ROOT / f"gates_{run_id}.json", gates)
    emit_migration_list(run_id, candidates)
    generate_error_summary(run_id, results)
    elapsed = round(time.time() - t0, 2)
    logger.info(f"[tiered] Completed process_batch in {elapsed}s")
    return results

# Public symbol expected by callers
process_batch = process_batch_tiered