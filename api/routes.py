# api/routes.py
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

# ------------------------------- constants -----------------------------------
CODE_EXTS = {".ts", ".tsx", ".js", ".jsx"}
IGNORE_NAMES = {"desktop.ini", ".ds_store", "thumbs.db"}
IGNORE_SUFFIXES = (".bak", ".tmp", "~")
IGNORE_DIR_PARTS = {"/__mocks__/", "/tests/","/node_modules/"}
TEST_NAME_RE = re.compile(r"\.(test|spec)\.[a-z0-9]+$", re.I)


# --------------------------------- helpers -----------------------------------
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
    """Repo-relative POSIX path."""
    base = base or Path.cwd()
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return p.as_posix()


def _git_changed_files(base_ref: str, cwd: Optional[Path] = None) -> List[str]:
    """best-effort: git diff --name-only base_ref...HEAD"""
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


def _preview_text(rel: str, max_lines: int = 40) -> List[str]:
    """Read up to max_lines from a path; be forgiving about relative vs absolute."""
    try:
        p = Path(rel)
        if not p.exists():
            # last resort: treat as filename within provided root
            p = Path(rel.strip("`").strip())
        txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()[:max_lines]
        return txt
    except Exception:
        return ["(snippet unavailable)"]


# ------------------------------ request models --------------------------------
class ConvertTreeReq(BaseModel):
    root: str = "src"
    dry_run: bool = True
    batch_cap: int = 25
    # labeling & tiering
    label: Optional[str] = None
    review_tier: str = "free"           # free | premium | wow
    generate_mds: bool = False          # force batch .md even in dry_run
    git_diff_base: Optional[str] = None # e.g., "main" or a SHA
    md_first: bool = False              # when true, produce .mds then return early


class BuildTsReq(BaseModel):
    md_paths: List[str]
    apply_moves: bool = True
    label: Optional[str] = None


# --------------------------------- routes ------------------------------------
@router.get("/", tags=["meta"])
def root():
    return {"ok": True, "service": "ai-orchestrator", "hint": "see /docs"}


@router.get("/_health", tags=["meta"])
def health():
    return {"ok": True}


@router.get("/orchestrator/status", tags=["meta"])
def status():
    return {"ok": True, "ts": datetime.utcnow().isoformat() + "Z"}


@router.get("/_meta/routes", tags=["meta"])
def list_routes(request: Request):
    routes = []
    for r in request.app.routes:
        try:
            routes.append(
                {
                    "path": r.path,
                    "methods": sorted(list(getattr(r, "methods", []) or [])),
                    "name": getattr(r, "name", None),
                    "tags": getattr(r, "tags", []),
                }
            )
        except Exception:
            pass
    return {"count": len(routes), "routes": routes}


@router.get("/readyz", tags=["meta"])
def readyz():
    # light provider surface check (env presence & import)
    checks: Dict[str, Any] = {}
    checks["router_loaded"] = True
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    checks["reports_dir"] = reports_dir.as_posix()
    checks["reports_dir_writable"] = True
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        test = reports_dir / ".w"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
    except Exception:
        checks["reports_dir_writable"] = False

    def _has_env(k: str) -> bool:
        return bool(os.getenv(k))

    providers = {
        "openai": {"sdk": False, "key": _has_env("OPENAI_API_KEY"), "ok": False},
        "gemini": {"sdk": False, "key": _has_env("GOOGLE_API_KEY") or _has_env("GEMINI_API_KEY"), "ok": False},
        "grok":   {"sdk": False, "key": _has_env("XAI_API_KEY") or _has_env("GROK_API_KEY"), "ok": False},
        "anthropic": {"sdk": False, "key": _has_env("ANTHROPIC_API_KEY"), "ok": False},
    }
    try:
        import openai  # type: ignore
        providers["openai"]["sdk"] = True
    except Exception:
        pass
    try:
        import google.generativeai as genai  # type: ignore
        providers["gemini"]["sdk"] = True
    except Exception:
        pass
    try:
        import groq  # sometimes used for xAI/grok clients; tolerate absence
        providers["grok"]["sdk"] = True
    except Exception:
        # we only check env for grok/xai in this light probe
        pass
    try:
        import anthropic  # type: ignore
        providers["anthropic"]["sdk"] = True
    except Exception:
        pass

    # minimal ok
    for k, v in providers.items():
        v["ok"] = bool(v["key"] and v["sdk"])

    checks["providers"] = providers
    checks["sdk_openai"] = providers["openai"]["sdk"]
    checks["sdk_gemini"] = providers["gemini"]["sdk"]
    checks["sdk_grok_xai"] = providers["grok"]["sdk"]
    checks["sdk_anthropic"] = providers["anthropic"]["sdk"]
    missing = [k for k, v in providers.items() if not v["key"]]
    checks["provider_env_missing"] = [f"{m.upper()}_API_KEY" for m in missing]
    checks["providers_enabled"] = [k for k, v in providers.items() if v["ok"]]
    checks["cfh_root"] = True
    return {"ok": True, "checks": checks}


@router.get("/reports/latest", tags=["meta"], name="reports_latest")
def reports_latest(label: Optional[str] = None):
    """Return the latest *.summary.md path (optionally within a label subfolder)."""
    base = Path(os.getenv("REPORTS_DIR", "reports"))
    if label:
        base = base / label
    if not base.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    latest: Optional[Path] = None
    for p in base.rglob("*.summary.md"):
        if (latest is None) or (p.stat().st_mtime > latest.stat().st_mtime):
            latest = p
    if not latest:
        raise HTTPException(status_code=404, detail="Not Found")
    preview = latest.read_text(encoding="utf-8", errors="ignore").splitlines()[:20]
    return {
        "ok": True,
        "path": latest.as_posix(),
        "modified": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
        "preview": "\n".join(preview),
        "label": label or "",
    }


# ------------------------------ convert entrypoint ----------------------------
@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(req: ConvertTreeReq = Body(...)) -> dict:
    root = Path(req.root)
    converted: List[str] = []
    skipped: List[str] = []
    reviews: List[Dict[str, Any]] = []

    # 1) Gather & filter
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
                    from app.ai.reviewer import get_changed_files  # type: ignore
                    changed_rel = set(get_changed_files(req.git_diff_base, cwd=Path.cwd()))
                except Exception:
                    changed_rel = set()
            if changed_rel:
                code_files = [p for p in code_files if _rel(p) in changed_rel]

        # legacy mini review (keep response stable; ignore if helper not present)
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

    # 2) response scaffold
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

    # 3) persist JSON
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

    # 4) summary markdown
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
        lines.append(f"- Converted listed: `{len(resp['converted'])}`  • Skipped listed: `{len(resp['skipped'])}`\n")

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

    # 5) optional batch .md generation (LLM + heuristic fallback)
    try:
        should_batch = (not req.dry_run) or bool(req.generate_mds) or bool(req.md_first)
        if should_batch:
            # prefer actual code_files; fallback to converted
            try:
                cand_paths = [p.as_posix() for p in code_files]  # type: ignore[name-defined]
            except Exception:
                cand_paths = [p for p in converted if p.endswith((".ts", ".tsx", ".js", ".jsx"))]
            cand_paths = cand_paths[:max(1, int(req.batch_cap))]

            if not cand_paths:
                # tiny fallback so CI has something to preview
                batch_path = (out_dir / f"batch_review_{stamp}.md")
                batch_path.write_text(
                    "# Batch Review — (no candidates)\n\n"
                    f"_Root:_ `{resp['root']}`  • _Label:_ `{req.label or ''}`\n\n"
                    "No code candidates detected for this batch.\n",
                    encoding="utf-8",
                )
                resp["artifacts"] = {"mds": [], "batch_md": batch_path.as_posix()}
            else:
                batch: Dict[str, Any] = {}
                try:
                    from app.ai.reviewer import review_batch  # type: ignore
                except Exception:
                    review_batch = None  # type: ignore

                if review_batch:
                    try:
                        # IMPORTANT: avoid label duplication — we already use out_dir
                        batch = review_batch(
                            cand_paths,
                            tier=req.review_tier,
                            label=None,
                            reports_dir=out_dir,
                        ) or {}
                    except Exception as e:
                        resp.setdefault("errors", []).append({"where": "batch_mds/run", "error": repr(e)})

                batch_md = batch.get("batch_md")
                if not batch_md:
                    batch_path = (out_dir / f"batch_review_{stamp}.md")
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
                        lines.extend(_preview_text(rel, max_lines=40))
                        lines.append("```")
                        lines.append("")
                    batch_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    batch_md = batch_path.as_posix()

                resp["artifacts"] = {
                    "mds": batch.get("per_file_mds", []),
                    "batch_md": batch_md,
                    "deps": batch.get("dependencies", {}),
                }

            if req.md_first:
                resp["next_step"] = "build_ts"
                return resp

    except Exception as e:
        resp.setdefault("errors", []).append({"where": "batch_mds/top", "error": repr(e)})

    return resp


@router.post("/build_ts", tags=["convert"], name="build_ts")
def build_ts(req: BuildTsReq = Body(...)) -> dict:
    """
    Consume previously generated per-file .mds and produce .tsx in suggested destinations.
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
