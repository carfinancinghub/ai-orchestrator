# --- api/routes.py -----------------------------------------------------------
# NOTE: This is a full replacement file. Paste it as-is.
# Major sections are marked with banner comments to make future edits easier.

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel

# Router instance (mounted by app.server:create_app)
router = APIRouter()

# =============================================================================
# Constants & Helpers
# =============================================================================

CODE_EXTS = {".ts", ".tsx", ".js", ".jsx"}
IGNORE_NAMES = {"desktop.ini", ".ds_store", "thumbs.db"}
IGNORE_SUFFIXES = (".bak", ".tmp", "~")
IGNORE_DIR_PARTS = {"/__mocks__/", "/tests/", "/node_modules/"}
TEST_NAME_RE = re.compile(r"\.(test|spec)\.[a-z0-9]+$", re.I)


def _is_noise(p: Path) -> bool:
    name_l = p.name.lower()
    if name_l in IGNORE_NAMES:
        return True
    if name_l.endswith(IGNORE_SUFFIXES):
        return True
    if TEST_NAME_RE.search(name_l):
        return True
    ppos = p.as_posix().lower()
    for part in IGNORE_DIR_PARTS:
        if part in ppos:
            return True
    return False


def _rel(p: Path, base: Optional[Path] = None) -> str:
    """
    Repo-relative (POSIX) path for consistent matching in git-diff filters.
    """
    base = base or Path.cwd()
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return p.as_posix()


def _git_changed_files(base_ref: str, cwd: Optional[Path] = None) -> List[str]:
    """
    Best-effort: return repo-relative file paths changed vs base_ref.
    Uses: git diff --name-only base_ref...HEAD
    """
    try:
        cwd = cwd or Path.cwd()
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        files = [ln.strip().replace("\\", "/") for ln in result.stdout.splitlines() if ln.strip()]
        return files
    except Exception:
        return []


def _preview_text(path_like: str, max_lines: int = 40) -> List[str]:
    """
    Best-effort head-of-file preview. Accepts repo-relative or absolute paths.
    """
    try:
        p = Path(path_like)
        if not p.exists():
            # fall back: try only the file name inside the provided root later
            return ["(snippet unavailable)"]
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()[:max_lines]
        return lines if lines else ["(empty file)"]
    except Exception:
        return ["(snippet unavailable)"]


def _providers_status() -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    Quick provider SDK/key checks used by /readyz.
    Returns (providers_map, enabled_list, missing_env_list)
    """
    providers = {}
    missing = []

    # OpenAI
    try:
        import openai  # noqa: F401
        have_key = bool(os.getenv("OPENAI_API_KEY"))
        providers["openai"] = {"sdk": True, "key": have_key, "ok": have_key}
        if not have_key:
            missing.append("OPENAI_API_KEY")
    except Exception:
        providers["openai"] = {"sdk": False, "key": False, "ok": False}

    # Gemini
    try:
        import google.generativeai as genai  # noqa: F401
        have_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
        providers["gemini"] = {"sdk": True, "key": have_key, "ok": have_key}
        if not have_key:
            missing.append("GOOGLE_API_KEY or GEMINI_API_KEY")
    except Exception:
        providers["gemini"] = {"sdk": False, "key": False, "ok": False}

    # Grok (xAI) – just environment check for now
    try:
        have_key = bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY"))
        providers["grok"] = {"sdk": True, "key": have_key, "ok": have_key}
        if not have_key:
            missing.append("XAI_API_KEY or GROK_API_KEY")
    except Exception:
        providers["grok"] = {"sdk": False, "key": False, "ok": False}

    # Anthropic (optional)
    try:
        import anthropic  # noqa: F401
        have_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        providers["anthropic"] = {"sdk": True, "key": have_key, "ok": have_key}
        if not have_key:
            missing.append("ANTHROPIC_API_KEY")
    except Exception:
        providers["anthropic"] = {"sdk": False, "key": False, "ok": False}

    enabled = [k for k, v in providers.items() if v.get("ok")]
    return providers, enabled, missing


def _list_routes_for_meta(req: Request) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in req.app.routes:  # FastAPI mounts our router on the app
        try:
            path = getattr(r, "path")
            methods = sorted(getattr(r, "methods", []))
            name = getattr(r, "name", "")
            tags = getattr(r, "tags", [])
            out.append({"path": path, "methods": methods, "name": name, "tags": tags})
        except Exception:
            # ignore non-APIRoute objects
            pass
    # stable order
    out.sort(key=lambda x: x["path"])
    return out


def _reports_latest_path(reports_dir: Path, label: Optional[str]) -> Optional[Path]:
    """
    Find the most-recent *.summary.md under reports_dir (optionally within label subdir).
    """
    base = reports_dir / (label or "")
    if not base.exists():
        return None
    candidates = list(base.glob("*.summary.md"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


# =============================================================================
# Pydantic Models (Requests)
# =============================================================================

class ConvertTreeReq(BaseModel):
    root: str = "src"
    dry_run: bool = True
    batch_cap: int = 25
    # Labeled artifacts / LLM routing
    label: Optional[str] = None
    review_tier: str = "free"            # free | premium | wow
    generate_mds: bool = False           # force batch .mds even when dry_run=True
    git_diff_base: Optional[str] = None  # e.g., "origin/main" or a SHA
    # PR22: md-first switch (if True, you could short-circuit to .md generation first)
    md_first: bool = False


class BuildTsReq(BaseModel):
    md_paths: List[str]
    apply_moves: bool = True
    label: Optional[str] = None


# =============================================================================
# Meta & Health Endpoints
# =============================================================================

@router.get("/", tags=["meta"], name="root")
def root() -> dict:
    return {"ok": True, "service": "ai-orchestrator", "hint": "See /docs for API."}


@router.get("/_health", tags=["meta"], name="health")
def health() -> dict:
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}


@router.get("/orchestrator/status", tags=["meta"], name="status")
def status() -> dict:
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    return {
        "ok": True,
        "reports_dir": str(reports_dir),
        "reports_dir_exists": reports_dir.exists(),
    }


@router.get("/readyz", tags=["meta"], name="readyz")
def readyz() -> dict:
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    providers, enabled, missing = _providers_status()
    checks = {
        "router_loaded": True,
        "reports_dir": str(reports_dir),
        "reports_dir_writable": True,
        "providers": providers,
        "sdk_openai": providers["openai"]["sdk"],
        "sdk_gemini": providers["gemini"]["sdk"],
        "sdk_grok_xai": providers["grok"]["sdk"],
        "sdk_anthropic": providers["anthropic"]["sdk"],
        "provider_env_missing": missing,
        "providers_enabled": enabled,
        "cfh_root": True,
    }
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        test = reports_dir / ".writable"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
    except Exception:
        checks["reports_dir_writable"] = False

    return {"ok": checks["reports_dir_writable"], "checks": checks}


@router.get("/_meta/routes", tags=["meta"], name="list_routes")
def list_routes(request: Request) -> dict:
    routes = _list_routes_for_meta(request)
    return {"count": len(routes), "routes": routes}


# =============================================================================
# Reports Utilities
# =============================================================================

@router.get("/reports/latest", tags=["meta"], name="reports_latest")
def reports_latest(label: Optional[str] = Query(None)) -> dict:
    """
    Return the latest *.summary.md path (optionally filtered by label subfolder),
    plus a small preview snippet.
    """
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    p = _reports_latest_path(reports_dir, label)
    if not p:
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        preview = "\n".join(p.read_text(encoding="utf-8", errors="ignore").splitlines()[:40])
    except Exception:
        preview = "(unavailable)"
    return {
        "ok": True,
        "path": p.as_posix(),
        "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        "preview": preview,
        "label": label or "",
    }


# =============================================================================
# Core: Convert Tree (collect, summarize, and optionally generate batch .md)
# =============================================================================

@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(req: ConvertTreeReq = Body(...)) -> dict:
    root = Path(req.root)
    converted: List[str] = []
    skipped: List[str] = []
    reviews: List[Dict[str, Any]] = []

    # 0) collect filesystem items
    if root.exists() and root.is_dir():
        all_items = list(root.rglob("*"))
        items: List[Path] = [p for p in all_items if not _is_noise(p)]

        # friendly listing (cap 200)
        for p in items[:200]:
            (converted if p.is_file() else skipped).append(p.as_posix())

        # candidate code files
        code_files = [p for p in items if p.is_file() and p.suffix.lower() in CODE_EXTS]

        # optional git-diff filter
        if req.git_diff_base:
            changed_rel = set(_git_changed_files(req.git_diff_base, cwd=Path.cwd()))
            if not changed_rel:
                try:
                    # optional fallback if present in reviewer.py
                    from app.ai.reviewer import get_changed_files  # type: ignore
                    changed_rel = set(get_changed_files(req.git_diff_base, cwd=Path.cwd()))
                except Exception:
                    changed_rel = set()
            if changed_rel:
                code_files = [p for p in code_files if _rel(p) in changed_rel]

        # legacy per-file mini review to keep response shape stable
        cap = max(0, int(req.batch_cap))
        try:
            from app.ai.reviewer import review_file  # type: ignore
        except Exception:
            review_file = None  # type: ignore

        for p in code_files[:cap]:
            if not review_file:
                break
            try:
                r = review_file(
                    str(p),
                    repo_root=os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"),
                )
                reviews.append(
                    {
                        "file": p.as_posix(),
                        "routing": r.get("routing", {}),
                        "markdown": r.get("markdown", ""),
                    }
                )
            except Exception as e:
                reviews.append(
                    {
                        "file": p.as_posix(),
                        "error": repr(e),
                        "routing": {"suggested_moves": []},
                        "markdown": "",
                    }
                )

    # response scaffold
    resp: Dict[str, Any] = {
        "ok": True,
        "root": str(root),
        "dry_run": req.dry_run,
        "converted": converted,
        "skipped": skipped,
        "reviews_count": len(reviews),
        "reviews": reviews,
        "artifacts": {},
        "label": req.label or "",
    }

    # persist JSON artifact
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = reports_dir / (req.label or "")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"convert_dryrun_{stamp}.json"
    try:
        out.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
        resp["artifact"] = out.as_posix()
    except Exception as e:
        resp["artifact_error"] = repr(e)

    # markdown summary
    try:
        summary_path = out.with_suffix(".summary.md")
        lines: List[str] = []
        lines.append(f"# Convert Dry-Run Summary — {stamp}\n")
        lines.append(f"- Root: `{resp['root']}`")
        lines.append(f"- Dry run: `{resp['dry_run']}`")
        if req.label:
            lines.append(f"- Label: `{req.label}`")
        if req.git_diff_base:
            lines.append(f"- Git diff base: `{req.git_diff_base}`")
        lines.append(f"- Reviews: `{resp['reviews_count']}`")
        lines.append(
            f"- Converted listed: `{len(resp['converted'])}`  • Skipped listed: `{len(resp['skipped'])}`\n"
        )

        TOP = min(10, len(reviews))
        if TOP:
            lines.append("## Top Reviewed Files\n")
            for r in reviews[:TOP]:
                file = r.get("file", "")
                moves = r.get("routing", {}).get("suggested_moves", [])
                if moves:
                    dest = moves[0].get("dest", "")
                    conf = moves[0].get("confidence", "")
                    lines.append(f"- `{file}` → `{dest}` (conf: {conf})")
                else:
                    lines.append(f"- `{file}` (no suggestion)")

        # optional: list changed files if we diff-filtered
        if req.git_diff_base:
            try:
                changed_rel = _git_changed_files(req.git_diff_base, cwd=Path.cwd())
                if changed_rel:
                    head = min(25, len(changed_rel))
                    lines.append("\n## Changed Files (git diff)\n")
                    for rel in changed_rel[:head]:
                        lines.append(f"- `{rel}`")
                    if len(changed_rel) > head:
                        lines.append(f"... and {len(changed_rel) - head} more")
            except Exception:
                pass

        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        resp["summary"] = summary_path.as_posix()
    except Exception as e:
        resp["summary_error"] = repr(e)

    # --- optional batch .md generation (Gemini/Grok/OpenAI) ------------------
    # IMPORTANT: This block belongs OUTSIDE the summary try/except (right here).
    try:
        should_batch = (not req.dry_run) or bool(req.generate_mds) or bool(req.md_first)
        if should_batch:
            # Prefer the real code_files set from above; fall back to 'converted'
            try:
                cand_paths = [p.as_posix() for p in code_files]  # from earlier in this function
            except Exception:
                cand_paths = [p for p in converted if p.endswith((".ts", ".tsx", ".js", ".jsx"))]

            # Cap to batch_cap
            cand_paths = cand_paths[:max(1, int(req.batch_cap))]

            # If no candidates, still emit a tiny fallback so CI has something to preview
            if not cand_paths:
                batch_path = (out.parent / f"batch_review_{stamp}.md")
                batch_path.write_text(
                    "# Batch Review — (no candidates)\n\n"
                    f"_Root:_ `{resp['root']}`  • _Label:_ `{req.label or ''}`\n\n"
                    "No code candidates detected for this batch.\n",
                    encoding="utf-8",
                )
                resp["artifacts"] = {"mds": [], "batch_md": batch_path.as_posix()}
            else:
                # Try LLM batch first (review_batch implemented in app.ai.reviewer)
                batch: Dict[str, Any] = {}
                try:
                    from app.ai.reviewer import review_batch  # type: ignore
                except Exception as e:
                    review_batch = None  # type: ignore
                    resp.setdefault("errors", []).append({"where": "batch_mds/import", "error": repr(e)})

                if review_batch:
                    try:
                        batch = review_batch(
                            cand_paths,
                            tier=req.review_tier,
                            label=req.label,
                            reports_dir=out.parent,
                        ) or {}
                    except Exception as e:
                        resp.setdefault("errors", []).append({"where": "batch_mds/run", "error": repr(e)})

                # If LLM path didn’t produce a batch_md, write a heuristic fallback
                batch_md = batch.get("batch_md")
                if not batch_md:
                    batch_path = (out.parent / f"batch_review_{stamp}.md")
                    lines = [
                        f"# Fallback Heuristic Batch Review — {req.review_tier}",
                        "",
                        f"_Root:_ `{resp['root']}`  • _Label:_ `{req.label or ''}`",
                        "",
                    ]
                    for rel in cand_paths:
                        lines.append(f"### File: `{rel}`")
                        lines.append("")
                        lines.append("```")
                        # best-effort preview head of file
                        head_lines = _preview_text(rel, max_lines=40)
                        lines.extend(head_lines)
                        lines.append("```")
                        lines.append("")
                    batch_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    batch_md = batch_path.as_posix()

                resp["artifacts"] = {
                    "mds": batch.get("per_file_mds", []),
                    "batch_md": batch_md,
                }

            # If md_first was requested, tell the caller the next step is build_ts
            if req.md_first:
                resp["next_step"] = "build_ts"
                return resp

    except Exception as e:
        resp.setdefault("errors", []).append({"where": "batch_mds/top", "error": repr(e)})

    return resp


# =============================================================================
# Build from .md (optional follow-up step for PR22 flow)
# =============================================================================

@router.post("/build_ts", tags=["convert"], name="build_ts")
def build_ts(req: BuildTsReq = Body(...)) -> dict:
    """
    Consume previously generated per-file .mds and (optionally) write .tsx files to
    suggested destinations. The actual builder lives in app.ai.reviewer.build_ts_from_md.
    """
    out_paths: List[str] = []
    errors: List[dict] = []

    try:
        from app.ai.reviewer import build_ts_from_md  # type: ignore
    except Exception as e:
        return {"ok": False, "code": "IMPORT_ERROR", "details": repr(e)}

    for md in req.md_paths:
        try:
            result = build_ts_from_md(md, apply_moves=req.apply_moves)
            out_paths.extend(result.get("written", []))
        except Exception as e:
            errors.append({"md": md, "error": repr(e)})

    return {
        "ok": len(errors) == 0,
        "written": out_paths,
        "errors": errors,
        "label": req.label or "",
    }

# --- end of file -------------------------------------------------------------
