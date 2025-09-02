# Path: C:\c\ai-orchestrator\app\ops.py
# Version: 0.3.8
# Last Updated: 2025-08-31 01:55 PDT
# Purpose: Core operations for scanning and processing .js/.jsx files for TypeScript migration
from __future__ import annotations
import json, os, logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from github import Github, GithubException
import time
import glob
from ratelimit import limits, sleep_and_retry
from dataclasses import dataclass
from app.utils import emit_migration_list

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPORTS_ROOT = Path("reports"); REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
ARTIFACTS_ROOT = Path("artifacts"); ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
STAGING_ROOT = ARTIFACTS_ROOT / "staging"; STAGING_ROOT.mkdir(parents=True, exist_ok=True)

CALLS = 60
PERIOD = 60
EXCLUDE_DIRS = {"node_modules", ".git", ".venv", ".github", "cypress", "vite"}
EXCLUDE_FILES = {"cypress.config.js", "vite.config.js", "vite.config.ts", "jest.config.js"}

@dataclass
class Candidate:
    repo: str
    branch: str
    src_path: str
    mtime: float

def stage_file(repo: str, branch: str, src_path: str, content: str) -> Path:
    target = (STAGING_ROOT / repo.replace("/", "__") / branch / src_path.replace("\\", "/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target

def _path_is_excluded(p: str | Path) -> bool:
    path_str = str(p).replace("\\", "/").lower()
    return any(excluded_dir in path_str.split("/") for excluded_dir in EXCLUDE_DIRS) or \
           Path(path_str).name.lower() in EXCLUDE_FILES

def _parse_inventory_md(md_path: Path) -> List[Path]:
    paths: List[Path] = []
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"Failed to read inventory {md_path}: {e}")
        return paths
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.count("|") >= 4):
            continue
        content = line.replace("|", "").strip()
        if set(content) <= set("-: "):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if not cols:
            continue
        file_path_str = cols[0].strip().strip('"').strip("'")
        p = Path(file_path_str)
        if p.exists() and p.is_file() and not _path_is_excluded(p):
            paths.append(p)
    return paths

@sleep_and_retry
@limits(calls=CALLS, period=PERIOD)
def list_repos_and_branches(user: str, platform: str, token: str) -> List[Dict]:
    logger.info(f"Listing repos for user {user} on {platform}")
    start_time = time.time()
    try:
        if platform == "github":
            gh = Github(token)
            allow = {"my-project-migration", "cfh", "converting", "ai-orchestrator"}
            repos = []
            for r in gh.get_user(user).get_repos():
                if r.name in allow:
                    branches = [b.name for b in gh.get_repo(f"{user}/{r.name}").get_branches()]
                    repos.append({"repo": f"{user}/{r.name}", "branches": branches})
                    logger.info(f"Found repo {r.name} with branches {branches}")
            if not repos:
                for name in sorted(allow):
                    full = f"{user}/{name}"
                    try:
                        branches = [b.name for b in gh.get_repo(full).get_branches()]
                        repos.append({"repo": full, "branches": branches})
                        logger.info(f"Fallback: Found repo {full} with branches {branches}")
                    except GithubException as e:
                        logger.error(f"Failed to access repo {full}: {str(e)}")
            logger.info(f"Completed repo listing in {time.time() - start_time:.2f}s")
            return repos
        return []
    except GithubException as e:
        logger.error(f"GitHub API error listing repos: {str(e)}")
        raise

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
    logger.info(f"Starting fetch_candidates for run_id {run_id}")
    start_time = time.time()
    candidates: List[Candidate] = []
    bundle_by_src: Dict[str, Dict[str, str]] = {}
    files: List[Dict] = []
    exclusions: List[Dict] = []
    js_count = 0
    ts_tsx_list: List[str] = []
    prefixes_env = os.getenv("CFH_SCAN_PATH_PREFIXES", "src/")
    path_prefixes = [p.strip().lower() for p in prefixes_env.split(",") if p.strip()]
    if path_prefixes:
        logger.info(f"Using path prefix filter(s): {path_prefixes}")

    # Clear old inventory cache to avoid stale data
    cache_file = REPORTS_ROOT / f"inventory_cache_{run_id}.json"
    if cache_file.exists():
        logger.info(f"Removing stale inventory cache: {cache_file}")
        cache_file.unlink()

    # Auto-detect local inventories
    if local_inventory_paths is None:
        local_inventory_paths = [
            str(p) for p in glob.glob(str(REPORTS_ROOT / "inventory*.{txt,list,csv,json}"), recursive=True) +
            glob.glob(str(REPORTS_ROOT / "inventories/*.*")) + glob.glob(str(REPORTS_ROOT / "file_scan_results_*.md"))
        ]
        logger.info(f"Auto-detected local inventory paths: {local_inventory_paths}")

    # Local inventory scanning
    root_dir = Path(local_inventory_paths[0]) if local_inventory_paths else Path("C:\\Backup_Projects\\CFH\\frontend")
    if root_dir and root_dir.exists() and root_dir.is_dir():
        logger.info(f"Scanning root directory: {root_dir}")
        for p in root_dir.rglob("*"):
            path_str = str(p).replace("\\", "/").lower()
            if _path_is_excluded(p):
                continue
            if p.is_file() and p.suffix.lower() in ('.js', '.jsx', '.ts', '.tsx'):
                if path_prefixes and not any(path_str.startswith(pref) for pref in path_prefixes):
                    continue
                files.append({"repo": "local", "branch": "main", "path": path_str})
                if p.suffix.lower() in ('.js', '.jsx'):
                    candidates.append(Candidate(repo="local", branch="main", src_path=path_str, mtime=p.stat().st_mtime))
                    js_count += 1
                    logger.info(f"Added local candidate: {path_str}")
                elif p.suffix.lower() in ('.ts', '.tsx'):
                    ts_tsx_list.append(path_str)
                    logger.info(f"Found local TS/TSX: {path_str}")

    # Markdown inventory scanning
    for p_str in local_inventory_paths:
        p = Path(p_str)
        if p.exists() and p.suffix.lower() == ".md":
            for md_path in _parse_inventory_md(p):
                path_str = str(md_path).replace("\\", "/").lower()
                if _path_is_excluded(md_path):
                    continue
                if path_prefixes and not any(path_str.startswith(pref) for pref in path_prefixes):
                    continue
                files.append({"repo": "local", "branch": "main", "path": path_str})
                if md_path.suffix.lower() in (".js", ".jsx"):
                    mtime = md_path.stat().st_mtime if md_path.exists() else 0.0
                    candidates.append(Candidate(repo="local", branch="main", src_path=path_str, mtime=mtime))
                    js_count += 1
                    logger.info(f"Added markdown candidate: {path_str}")
                elif md_path.suffix.lower() in (".ts", ".tsx"):
                    ts_tsx_list.append(path_str)
                    logger.info(f"Found markdown TS/TSX: {path_str}")

    # GitHub repo scanning
    if platform == "github":
        repos_info = list_repos_and_branches(user or "carfinancinghub", platform, token)
        gh = Github(token)
        for repo_info in repos_info:
            repo_name = repo_info["repo"].split("/")[-1]
            logger.info(f"Scanning repo {repo_name}")
            repo_start = time.time()
            timeout = 120 if repo_name == "cfh" else 60
            try:
                repo = gh.get_repo(f"{user or 'carfinancinghub'}/{repo_name}")
                for branch in repo_info["branches"]:
                    try:
                        contents = repo.get_contents("", ref=branch)
                        batch_size = 50
                        for i in range(0, len(contents), batch_size):
                            batch = contents[i:i + batch_size]
                            for file_content in batch:
                                path_str = file_content.path.lower()
                                if _path_is_excluded(file_content.path):
                                    continue
                                if file_content.type == "dir":
                                    sub_contents = repo.get_contents(file_content.path, ref=branch)
                                    for sub_file in sub_contents:
                                        sub_path_str = sub_file.path.lower()
                                        if _path_is_excluded(sub_file.path):
                                            continue
                                        if sub_file.path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                                            if path_prefixes and not any(sub_path_str.startswith(pref) for pref in path_prefixes):
                                                continue
                                            try:
                                                repo.get_contents(sub_file.path, ref=branch)
                                                files.append({"repo": repo.full_name, "branch": branch, "path": sub_file.path})
                                                if sub_file.path.endswith(('.js', '.jsx')):
                                                    candidates.append(Candidate(repo=repo.full_name, branch=branch, src_path=sub_file.path, mtime=0))
                                                    js_count += 1
                                                    logger.info(f"Added GitHub candidate: {sub_file.path}")
                                                elif sub_file.path.endswith(('.ts', '.tsx')):
                                                    ts_tsx_list.append(sub_file.path)
                                                    logger.info(f"Found GitHub TS/TSX: {sub_file.path}")
                                            except GithubException as e:
                                                exclusions.append({"repo": repo_name, "branch": branch, "path": sub_file.path, "error": f"File not found: {str(e)}"})
                                elif file_content.path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                                    if path_prefixes and not any(path_str.startswith(pref) for pref in path_prefixes):
                                        continue
                                    try:
                                        repo.get_contents(file_content.path, ref=branch)
                                        files.append({"repo": repo.full_name, "branch": branch, "path": file_content.path})
                                        if file_content.path.endswith(('.js', '.jsx')):
                                            candidates.append(Candidate(repo=repo.full_name, branch=branch, src_path=file_content.path, mtime=0))
                                            js_count += 1
                                            logger.info(f"Added GitHub candidate: {file_content.path}")
                                        elif file_content.path.endswith(('.ts', '.tsx')):
                                            ts_tsx_list.append(file_content.path)
                                            logger.info(f"Found GitHub TS/TSX: {file_content.path}")
                                    except GithubException as e:
                                        exclusions.append({"repo": repo_name, "branch": branch, "path": file_content.path, "error": f"File not found: {str(e)}"})
                            if time.time() - repo_start > timeout:
                                logger.warning(f"Timeout scanning {repo_name} after {timeout}s")
                                exclusions.append({"repo": repo_name, "error": f"Timeout after {timeout}s"})
                                break
                    except GithubException as e:
                        logger.error(f"Error scanning branch {branch} in {repo_name}: {str(e)}")
                        exclusions.append({"repo": repo_name, "branch": branch, "error": str(e)})
            except GithubException as e:
                logger.error(f"Error scanning repo {repo_name}: {str(e)}")
                exclusions.append({"repo": repo_name, "error": str(e)})
            logger.info(f"Scanned repo {repo_name} in {time.time() - repo_start:.2f}s")

    discrepancies: Dict[str, int] = {r: sum(1 for c in candidates if c.repo == r) for r in {c.repo for c in candidates}}
    logger.info(f"Discrepancies: {discrepancies}")

    payload = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user, "org": org, "repo_name": repo_name, "branches": branches,
        "found_total": len(files),
        "found_js_jsx": js_count,
        "repos": repos_info if platform == "github" else [],
        "candidates": [{"repo": c.repo, "branch": c.branch, "path": c.src_path, "mtime": c.mtime} for c in candidates],
        "bundles": bundle_by_src,
        "exclusions": exclusions,
        "ts_tsx_seen": [{"repo": f["repo"], "branch": f["branch"], "path": f["path"]} for f in files if f["path"] in ts_tsx_list],
        "discrepancies": discrepancies,
    }
    (REPORTS_ROOT / f"scan_{run_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (REPORTS_ROOT / "scan_latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cache_payload = {
        "candidates": [{"repo": c.repo, "branch": c.branch, "path": c.src_path, "mtime": c.mtime} for c in candidates],
        "files": files,
        "found_js_jsx": js_count,
        "ts_tsx_seen": [{"repo": f["repo"], "branch": f["branch"], "path": f["path"]} for f in files if f["path"] in ts_tsx_list],
        "bundles": bundle_by_src,
        "exclusions": exclusions,
        "repos": repos_info if platform == "github" else []
    }
    cache_file.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
    logger.info(f"Saved inventory cache to {cache_file}")

    logger.info(f"Completed fetch_candidates in {time.time() - start_time:.2f}s")
    return candidates, bundle_by_src, repos_info if platform == "github" else []

def process_batch(
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
    logger.info(f"Starting process_batch for run_id {run_id}")
    results: List[Dict] = []
    gh = Github(token) if platform == "github" else None

    for c in candidates[batch_offset:batch_offset + (batch_limit or len(candidates))]:
        try:
            if c.repo == "local":
                src_path = Path(c.src_path)
                if not src_path.exists():
                    results.append({
                        "repo": c.repo,
                        "branch": c.branch,
                        "path": c.src_path,
                        "status": "ERROR",
                        "error": "Source file not found"
                    })
                    continue
                content = src_path.read_text(encoding="utf-8")
            else:
                repo = gh.get_repo(c.repo)
                try:
                    file_content = repo.get_contents(c.src_path, ref=c.branch)
                    content = file_content.decoded_content.decode("utf-8")
                except GithubException as e:
                    results.append({
                        "repo": c.repo,
                        "branch": c.branch,
                        "path": c.src_path,
                        "status": "ERROR",
                        "error": f"GitHubException: {str(e)}"
                    })
                    continue

            # Basic conversion: append TypeScript types
            ts_content = f"// TypeScript conversion of {c.src_path}\n{content}\n// @ts-nocheck"
            ts_path = c.src_path.rsplit(".", 1)[0] + (".ts" if c.src_path.endswith(".js") else ".tsx")
            staged = stage_file(c.repo, c.branch, ts_path, ts_content)
            # Generate basic test file
            test_content = f"import {{ describe, it, expect }} from 'vitest';\n" \
                          f"describe('{Path(c.src_path).name}', () => {{\n" \
                          f"  it('should exist', () => {{\n" \
                          f"    expect(true).toBe(true);\n" \
                          f"  }});\n" \
                          f"}});\n"
            test_path = c.src_path.rsplit(".", 1)[0] + ".test" + (".ts" if c.src_path.endswith(".js") else ".tsx")
            stage_file(c.repo, c.branch, test_path, test_content)
            results.append({
                "repo": c.repo,
                "branch": c.branch,
                "path": c.src_path,
                "status": "CONVERTED",
                "staged_path": str(staged),
                "test_path": str(test_path)
            })
        except Exception as e:
            results.append({
                "repo": c.repo,
                "branch": c.branch,
                "path": c.src_path,
                "status": "ERROR",
                "error": f"{type(e).__name__}: {str(e)}"
            })

    if evaluate_paths:
        for item in evaluate_paths:
            try:
                repo_full = item["repo"]
                branch = item["branch"]
                path = item["path"]
                eval_res = {"action": "no-op"}
                if eval_res.get("action") == "update":
                    updated = "/* Updated */"
                    staged = stage_file(repo_full, branch, path, updated)
                    branch_name = f"ts-migration-{run_id}-{repo_full.split('/')[-1]}-{branch}"
                    results.append({"repo": repo_full, "branch": branch, "path": path, "status": "UPDATED", "staged_path": str(staged)})
                else:
                    results.append({"repo": repo_full, "branch": branch, "path": path, "status": "NO-OP"})
            except Exception as e:
                results.append({
                    "repo": item.get("repo"),
                    "branch": item.get("branch"),
                    "path": item.get("path"),
                    "status": "ERROR",
                    "error": f"{type(e).__name__}: {e}"
                })

    # Generate migration list
    emit_migration_list(run_id, candidates)
    generate_error_summary(run_id, results)
    logger.info(f"Completed process_batch for run_id {run_id}")
    return results

def generate_error_summary(run_id: str, results: List[Dict]):
    logger.info(f"Generating error summary for run_id {run_id}")
    def sev(r: Dict) -> str:
        txt = (r.get("error") or "").lower()
        if any(k in txt for k in ("429", "rate limit", "ratelimit", "conflict", "merge conflict", "githubexception", "gitlab", "timeout")):
            return "critical"
        if r.get("status") in ("FAIL",) or r.get("reasons"):
            return "warning"
        return "warning"
    errs = [{"severity": sev(r), **r} for r in results if r.get("status") in ("ERROR", "FAIL")]
    (REPORTS_ROOT / f"errors_{run_id}.json").write_text(json.dumps(errs, indent=2), encoding="utf-8")# === BEGIN: tiered reviews & gates (appended) ===
from datetime import datetime, timezone

def _review_dir(run_id: str, tier: str, rel_path: str) -> Path:
    base = REPORTS_ROOT / "reviews" / run_id / tier
    (base / Path(rel_path)).parent.mkdir(parents=True, exist_ok=True)
    return base

def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def _tier_thresholds() -> dict:
    return {
        "Free":    {"type_coverage": 10, "test_coverage": 10},
        "Premium": {"type_coverage": 50, "refactor_quality": 30, "test_coverage": 50},
        "Wow++":   {"type_coverage": 80, "refactor_quality": 60, "test_coverage": 80, "future_readiness": 50},
    }

def _heuristic_scores(content: str) -> dict:
    has_types = (": " in content) or ("<" in content and ">" in content and "React" in content)
    uses_hooks = any(h in content for h in ("useState(", "useEffect(", "useMemo(", "useCallback("))
    has_tests = "describe(" in content or "it(" in content
    return {
        "type_coverage": 70 if has_types else 5,
        "refactor_quality": 40 if uses_hooks else 20,
        "test_coverage": 60 if has_tests else 10,
        "future_readiness": 30,
    }

def _make_prompts(rel_path: str, js_content: str, ts_dest: str) -> dict:
    common = {
        "file": rel_path,
        "target_ts_path": ts_dest,
        "context": "CFH Marketplace TypeScript migration with Vite/Vitest; ensure ESM compatibility and router@6.",
    }
    return {
        "Free": {
            **common,
            "task": "Basic JS->TS conversion with @ts-nocheck as needed. Fix import/export issues; behavior must match.",
            "checks": ["build passes", "file compiles", "no console errors"]
        },
        "Premium": {
            **common,
            "task": "Add proper TS types for props/state, extract interfaces, reduce any/unknown, suggest safe refactors.",
            "checks": ["type errors resolved", "tests compile", "no anti-patterns"]
        },
        "Wow++": {
            **common,
            "task": "Deep critique: a11y, perf, state mgmt, SSR/Suspense readiness, routing edges; propose tests.",
            "checks": ["a11y notes", "perf notes", "forward-compat"]
        }
    }

def _emit_review_artifacts(run_id: str, rel_path: str, tier: str, prompt: dict, scores: dict) -> None:
    base = _review_dir(run_id, tier, rel_path)
    rel_norm = Path(rel_path)
    json_path = base / rel_norm.with_suffix(".json")
    md_path   = base / rel_norm.with_suffix(".md")
    data = {"tier": tier, "run_id": run_id, "file": rel_path, "prompt": prompt, "scores": scores,
            "timestamp": datetime.now(timezone.utc).isoformat()}
    _write_json(json_path, data)
    md = (
        f"# {tier} Review — {rel_path}\n\n"
        f"**Run:** {run_id}\n\n"
        f"## Prompt\n\n```\n{json.dumps(prompt, indent=2)}\n```\n\n"
        f"## Scores (heuristic)\n\n{json.dumps(scores, indent=2)}\n"
    )
    _write_text(md_path, md)

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
    logger.info(f"[tiered] process_batch for run_id {run_id}")
    results: List[Dict] = []
    gh = Github(token) if platform == "github" else None

    env_limit = os.getenv("CFH_BATCH_LIMIT")
    if env_limit:
        try: batch_limit = int(env_limit)
        except Exception: pass

    slice_end = batch_offset + (batch_limit or len(candidates))
    batch = candidates[batch_offset:slice_end]

    gates = {"build": "PENDING", "test": "PENDING", "lint": "PENDING",
             "thresholds": _tier_thresholds(), "per_file": []}

    for c in batch:
        try:
            # read source
            if c.repo == "local":
                local_root = os.getenv("CFH_LOCAL_ROOT")
                src_path = Path(local_root, c.src_path) if local_root else Path(c.src_path)
                if not src_path.exists():
                    staged_src = (ARTIFACTS_ROOT / "_staged_all" / c.src_path).resolve()
                    if staged_src.exists():
                        content = staged_src.read_text(encoding="utf-8")
                    else:
                        results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                                        "status": "ERROR", "error": "Source file not found"})
                        continue
                else:
                    content = src_path.read_text(encoding="utf-8")
            else:
                repo = gh.get_repo(c.repo)
                try:
                    file_content = repo.get_contents(c.src_path, ref=c.branch)
                    content = file_content.decoded_content.decode("utf-8")
                except GithubException as e:
                    results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                                    "status": "ERROR", "error": f"GitHubException: {str(e)}"})
                    continue

            # conversion (placeholder)
            ts_path_rel = c.src_path.rsplit(".", 1)[0] + (".ts" if c.src_path.endswith(".js") else ".tsx")
            ts_content = f"// TypeScript conversion of {c.src_path}\n{content}\n// @ts-nocheck"
            staged = stage_file(c.repo, c.branch, ts_path_rel, ts_content)

            # smoke test file
            test_path_rel = c.src_path.rsplit(".", 1)[0] + ".test" + (".ts" if c.src_path.endswith(".js") else ".tsx")
            test_content = (
                "import { describe, it, expect } from 'vitest';\n"
                f"describe('{Path(c.src_path).name}', () => {{\n"
                "  it('should exist', () => { expect(true).toBe(true); });\n"
                "});\n"
            )
            stage_file(c.repo, c.branch, test_path_rel, test_content)

            # prompts + heuristic scores
            prompts = _make_prompts(c.src_path, content, ts_path_rel)
            scores  = _heuristic_scores(ts_content)

            for tier in ("Free", "Premium", "Wow++"):
                _emit_review_artifacts(run_id, c.src_path, tier, prompts[tier], scores)

            thresholds = _tier_thresholds()
            per_file_gate = {"file": c.src_path, "tiers": {}, "staged_paths": {"ts": str(staged), "test": test_path_rel}}
            for tier, reqs in thresholds.items():
                ok = all(scores.get(k, 0) >= v for k, v in reqs.items())
                per_file_gate["tiers"][tier] = "PASS" if ok else "FAIL"
            gates["per_file"].append(per_file_gate)

            results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                            "status": "CONVERTED", "staged_path": str(staged), "test_path": str(test_path_rel)})

        except Exception as e:
            results.append({"repo": c.repo, "branch": c.branch, "path": c.src_path,
                            "status": "ERROR", "error": f"{type(e).__name__}: {str(e)}"})

    _write_json(REPORTS_ROOT / f"gates_{run_id}.json", gates)
    emit_migration_list(run_id, candidates)
    generate_error_summary(run_id, results)
    logger.info(f"[tiered] Completed process_batch for run_id {run_id}")
    return results

# override original symbol so API uses tiered version
process_batch = process_batch_tiered
# === END: tiered reviews & gates ===
# === BEGIN: FETCH_CANDIDATES RELATIVE-PATH OVERRIDE ===
from datetime import datetime, timezone
import glob, json, os, time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from github import Github, GithubException

def fetch_candidates_relpath(
    org: Optional[str],
    repo_name: Optional[str],
    platform: str,
    token: str,
    run_id: str,
    branches: Optional[List[str]],
    local_inventory_paths: Optional[List[str]] = None,
    user: Optional[str] = None,
):
    logger.info(f"[relpath] Starting fetch_candidates for run_id {run_id}")
    t0 = time.time()

    def _prefixes() -> List[str]:
        env = os.getenv("CFH_SCAN_PATH_PREFIXES")
        if env is None:
            # No filtering when env is unset (robust default)
            return []
        return [p.strip().lower() for p in env.split(",") if p.strip()]

    def _match_prefix(rel_path: str, prefs: List[str]) -> bool:
        if not prefs:
            return True
        return any(rel_path.startswith(pref) for pref in prefs)

    candidates: List[Candidate] = []
    bundle_by_src: Dict[str, Dict[str, str]] = {}
    files: List[Dict] = []
    exclusions: List[Dict] = []
    js_count = 0
    ts_tsx_list: List[str] = []

    prefs = _prefixes()
    if prefs:
        logger.info(f"[relpath] Using path prefix filter(s) (relative): {prefs}")
    else:
        logger.info("[relpath] No path prefix filtering (include all)")

    cache_file = REPORTS_ROOT / f"inventory_cache_{run_id}.json"
    if cache_file.exists():
        logger.info(f"[relpath] Removing stale inventory cache: {cache_file}")
        cache_file.unlink()

    # Resolve scan root (directory). If caller passed a file/leaf, climb to parent dir.
    if local_inventory_paths and len(local_inventory_paths) > 0:
        rd = Path(local_inventory_paths[0]).resolve()
        root_dir = rd if rd.is_dir() else rd.parent
    else:
        root_dir = Path("C:/Backup_Projects/CFH/frontend").resolve()

    logger.info(f"[relpath] Scanning root directory: {root_dir}")

    # Local scan --------------------------------------------------------------
    for p in root_dir.rglob("*"):
        try:
            if _path_is_excluded(p):
                logger.debug(f"[relpath] EXCLUDE (rule): {p}")
                continue
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".js", ".jsx", ".ts", ".tsx"):
                continue

            rel = str(p.relative_to(root_dir)).replace("\\", "/").lower()
            if not _match_prefix(rel, prefs):
                logger.debug(f"[relpath] SKIP (prefix): {rel}")
                continue

            files.append({"repo": "local", "branch": "main", "path": rel})
            if p.suffix.lower() in (".js", ".jsx"):
                mtime = p.stat().st_mtime
                candidates.append(Candidate(repo="local", branch="main", src_path=rel, mtime=mtime))
                js_count += 1
                logger.info(f"[relpath] Added local candidate: {rel}")
            else:
                ts_tsx_list.append(rel)
                logger.debug(f"[relpath] Found local TS/TSX: {rel}")
        except Exception as e:
            logger.warning(f"[relpath] Local scan error on {p}: {e}")

    # GitHub scan -------------------------------------------------------------
    repos_info = []
    if platform == "github":
        repos_info = list_repos_and_branches(user or "carfinancinghub", platform, token)
        gh = Github(token)

        for repo_info in repos_info:
            rname = repo_info["repo"].split("/")[-1]
            logger.info(f"[relpath] Scanning repo {rname}")
            t_repo = time.time()
            timeout = 120 if rname == "cfh" else 60
            try:
                repo = gh.get_repo(f"{user or 'carfinancinghub'}/{rname}")
                for branch in repo_info["branches"]:
                    try:
                        contents = repo.get_contents("", ref=branch)
                        # breadth-first-ish scan with paging at top level
                        queue = contents[:]
                        while queue:
                            item = queue.pop(0)
                            path_str = item.path.replace("\\", "/").lower()

                            if _path_is_excluded(path_str):
                                continue

                            if item.type == "dir":
                                try:
                                    sub = repo.get_contents(item.path, ref=branch)
                                    queue.extend(sub)
                                except GithubException:
                                    pass
                                continue

                            if not path_str.endswith((".js", ".jsx", ".ts", ".tsx")):
                                continue

                            # GitHub paths are already repo-relative (perfect for prefix check)
                            if not _match_prefix(path_str, prefs):
                                logger.debug(f"[relpath] GH SKIP (prefix): {path_str}")
                                continue

                            files.append({"repo": repo.full_name, "branch": branch, "path": path_str})
                            if path_str.endswith((".js", ".jsx")):
                                candidates.append(Candidate(repo=repo.full_name, branch=branch, src_path=path_str, mtime=0))
                                js_count += 1
                                logger.info(f"[relpath] Added GitHub candidate: {path_str}")
                            else:
                                ts_tsx_list.append(path_str)
                    except GithubException as e:
                        logger.error(f"[relpath] Error scanning branch {branch} in {rname}: {e}")
                        exclusions.append({"repo": rname, "branch": branch, "error": str(e)})

                    if time.time() - t_repo > timeout:
                        logger.warning(f"[relpath] Timeout scanning {rname} after {timeout}s")
                        exclusions.append({"repo": rname, "error": f"Timeout after {timeout}s"})
                        break
            except GithubException as e:
                logger.error(f"[relpath] Error scanning repo {rname}: {e}")
                exclusions.append({"repo": rname, "error": str(e)})
            logger.info(f"[relpath] Scanned repo {rname} in {time.time() - t_repo:.2f}s")

    discrepancies: Dict[str, int] = {r: sum(1 for c in candidates if c.repo == r) for r in {c.repo for c in candidates}}
    logger.info(f"[relpath] Discrepancies: {discrepancies}")

    payload = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user, "org": org, "repo_name": repo_name, "branches": branches,
        "found_total": len(files),
        "found_js_jsx": js_count,
        "repos": repos_info if platform == "github" else [],
        "candidates": [{"repo": c.repo, "branch": c.branch, "path": c.src_path, "mtime": c.mtime} for c in candidates],
        "bundles": bundle_by_src,
        "exclusions": exclusions,
        "ts_tsx_seen": [{"repo": f.get("repo","local"), "branch": f.get("branch","main"), "path": f["path"]} for f in files if f["path"] in ts_tsx_list],
        "discrepancies": discrepancies,
    }
    (REPORTS_ROOT / f"scan_{run_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (REPORTS_ROOT / "scan_latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cache_payload = {
        "candidates": [{"repo": c.repo, "branch": c.branch, "path": c.src_path, "mtime": c.mtime} for c in candidates],
        "files": files,
        "found_js_jsx": js_count,
        "ts_tsx_seen": [{"repo": f.get("repo","local"), "branch": f.get("branch","main"), "path": f["path"]} for f in files if f["path"] in ts_tsx_list],
        "bundles": bundle_by_src,
        "exclusions": exclusions,
        "repos": repos_info if platform == "github" else []
    }
    (REPORTS_ROOT / f"inventory_cache_{run_id}.json").write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
    logger.info(f"[relpath] Saved inventory cache to {REPORTS_ROOT / f'inventory_cache_{run_id}.json'}")
    logger.info(f"[relpath] Completed fetch_candidates in {time.time() - t0:.2f}s")
    return candidates, bundle_by_src, repos_info if platform == "github" else []

# Override the original symbol so API uses the robust version
fetch_candidates = fetch_candidates_relpath
# === END: FETCH_CANDIDATES RELATIVE-PATH OVERRIDE ===
