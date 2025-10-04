# api/routes.py
from __future__ import annotations

"""
Routes for AI Orchestrator:
- Providers info (placeholder)
- Convert endpoints (tree/file)
- Reports helper to fetch latest summary
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel

from app.ai.reviewer import review_file

router = APIRouter()

# ---------------------------
# Request Models
# ---------------------------

class ConvertTreeReq(BaseModel):
    root: str = "src"
    dry_run: bool = True
    batch_cap: int = 25  # how many files to review per call (safety)
    # Optional label to group artifacts under reports/<label>/...
    # e.g., "pr-16" or "nightly-2025-10-03"
    label: Optional[str] = None


# ---------------------------
# Constants / Filters
# ---------------------------

CODE_EXTS = {".ts", ".tsx", ".js", ".jsx"}

# file/dir noise filters
IGNORE_NAMES = {"desktop.ini", ".ds_store", "thumbs.db"}
IGNORE_SUFFIXES = (".bak", ".tmp", "~")
IGNORE_DIR_PARTS = {"/__mocks__/", "/tests/"}  # hide these directories from listings/reviews

# inline test name patterns (e.g., foo.test.tsx, bar.spec.js)
TEST_NAME_RE = re.compile(r"\.(test|spec)\.[a-z0-9]+$", re.I)


def _is_noise(p: Path) -> bool:
    """Return True for files/dirs we want to hide from listings/reviews."""
    name_l = p.name.lower()
    if name_l in IGNORE_NAMES:
        return True
    if name_l.endswith(IGNORE_SUFFIXES):
        return True
    if TEST_NAME_RE.search(name_l):  # inline tests like foo.test.tsx
        return True
    # path-based directory filters
    ppos = p.as_posix().lower()
    for part in IGNORE_DIR_PARTS:
        if part in ppos:
            return True
    return False


# ---------------------------
# Provider endpoints (placeholders)
# ---------------------------

@router.get("/providers/list", tags=["providers"], name="providers_list")
def providers_list() -> dict:
    return {"providers": ["openai", "gemini", "grok", "anthropic"]}


@router.get("/providers/selftest", tags=["providers"], name="providers_selftest")
def providers_selftest() -> dict:
    return {"ok": True}


# ---------------------------
# Convert endpoints
# ---------------------------

@router.post("/convert/file", tags=["convert"], name="convert_file")
def convert_file() -> dict:
    # Placeholder for single-file conversion
    return {"ok": True, "converted": 1, "skipped": 0}


@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(req: ConvertTreeReq = Body(...)) -> dict:
    """
    Walk the tree rooted at `req.root`, filter noise, return a capped list of items,
    and run lightweight "review" on up to `batch_cap` code files.
    Write artifacts into REPORTS_DIR (optionally under a `label` subfolder).
    """
    root = Path(req.root)
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": "root_not_found", "root": str(root)}

    converted: List[str] = []
    skipped: List[str] = []
    reviews: List[Dict[str, Any]] = []

    # Gather and filter once
    all_items = list(root.rglob("*"))
    items: List[Path] = []
    for p in all_items:
        if _is_noise(p):
            continue
        items.append(p)

    # Response-friendly listing (cap 200)
    for p in items[:200]:
        (converted if p.is_file() else skipped).append(str(p).replace("\\", "/"))

    # Review only code files (cap per request)
    cap = max(0, int(req.batch_cap))
    code_files = [p for p in items if p.is_file() and p.suffix.lower() in CODE_EXTS]
    for p in code_files[:cap]:
        try:
            r = review_file(
                str(p),
                repo_root=os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"),
            )
            reviews.append(
                {
                    "file": str(p).replace("\\", "/"),
                    "routing": r["routing"],
                    "markdown": r["markdown"],
                }
            )
        except Exception as e:
            reviews.append(
                {
                    "file": str(p).replace("\\", "/"),
                    "error": repr(e),
                    "routing": {"suggested_moves": []},
                    "markdown": "",
                }
            )

    resp: Dict[str, Any] = {
        "ok": True,
        "root": str(root),
        "dry_run": req.dry_run,
        "converted": converted,
        "skipped": skipped,
        "reviews_count": len(reviews),
        "reviews": reviews,
    }

    # Resolve reports dir, optionally under label (e.g., reports/pr-16)
    base_reports = Path(os.getenv("REPORTS_DIR", "reports"))
    reports_dir = (base_reports / req.label) if req.label else base_reports
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON artifact
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = reports_dir / f"convert_dryrun_{stamp}.json"
    try:
        out_json.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
        resp["artifact"] = str(out_json)
    except Exception as e:
        resp["artifact_error"] = repr(e)

    # Save Markdown summary (commit-friendly)
    try:
        out_md = reports_dir / f"convert_dryrun_{stamp}.summary.md"
        lines: List[str] = []
        lines.append(f"# Convert Dry-Run Summary — {stamp}\n")
        lines.append(f"- Root: `{resp['root']}`")
        lines.append(f"- Dry run: `{resp['dry_run']}`")
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

        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        resp["summary"] = str(out_md)
    except Exception as e:
        resp["summary_error"] = repr(e)

    return resp


# ---------------------------
# Reports helper
# ---------------------------

@router.get("/reports/latest", tags=["reports"], name="reports_latest")
def reports_latest(
    label: Optional[str] = Query(None, description="Optional label to scope lookup, e.g. pr-16"),
    limit_preview_chars: int = Query(1200, ge=0, le=100_000, description="Preview character cap"),
) -> Dict[str, Any]:
    """
    Return the newest convert_dryrun_*.summary.md with a short preview.
    If `label` is provided, search under reports/<label>/ only.
    """
    base_reports = Path(os.getenv("REPORTS_DIR", "reports")).resolve()
    reports_dir = (base_reports / label).resolve() if label else base_reports
    reports_dir.mkdir(parents=True, exist_ok=True)

    candidates = list(reports_dir.glob("convert_dryrun_*.summary.md"))
    if not candidates:
        return {"ok": False, "error": "no_summaries_found", "reports_dir": str(reports_dir)}

    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        text = newest.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": "read_failed", "path": str(newest), "detail": repr(e)}

    preview = text[:limit_preview_chars]
    mtime = datetime.fromtimestamp(newest.stat().st_mtime).isoformat(timespec="seconds")
    return {
        "ok": True,
        "path": str(newest),
        "modified": mtime,
        "preview": preview,
        "label": label,
    }
