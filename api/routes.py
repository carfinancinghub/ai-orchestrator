# C:\c\ai-orchestrator\api\routes.py
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Body
from typing import Any, Dict, List
import os
import json
from datetime import datetime

router = APIRouter()

# Try to load a reviewer (rule-based or LLM-backed).
# If unavailable, we simply skip reviews.
try:
    from app.ai.reviewer import review_file  # optional module you can add later
except Exception:
    review_file = None  # type: ignore


# --- providers ---
@router.get("/providers/list", tags=["providers"], name="providers_list")
def providers_list() -> dict:
    return {"providers": ["openai", "gemini", "anthropic", "grok"]}


@router.get("/providers/selftest", tags=["providers"], name="providers_selftest")
def providers_selftest() -> dict:
    return {"ok": True}


# --- convert ---
@router.post("/convert/file", tags=["convert"], name="convert_file")
def convert_file() -> dict:
    # stub: replace with real logic when ready
    return {"ok": True, "converted": 1, "skipped": 0}


@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(
    root: str = Body("src", embed=True),         # expects {"root": "..."}
    dry_run: bool = Body(True, embed=True),      # expects {"dry_run": true}
    batch_cap: int = Body(25, embed=True),       # optional: cap files to review
) -> dict:
    """
    Walk `root`, list up to 50 paths to keep payload small.
    If a reviewer is available, review up to `batch_cap` code files (.ts/.tsx/.js/.jsx).
    Persist a JSON artifact under reports/ for post-processing (routing audit, docs mirror).
    """
    p = Path(root)
    converted: List[str] = []
    skipped: List[str] = []
    reviews: List[Dict[str, Any]] = []

    if p.exists() and p.is_dir():
        items = list(p.rglob("*"))
        # match previous behavior: cap at 50 for response size predictability
        for item in items[:50]:
            (converted if item.is_file() else skipped).append(str(item).replace("\\", "/"))

        # Optional reviews
        if review_file is not None:
            CODE_EXTS = {".ts", ".tsx", ".js", ".jsx"}
            code_files = [i for i in items if i.is_file() and i.suffix.lower() in CODE_EXTS]
            cap = max(0, int(batch_cap))
            for fp in code_files[:cap]:
                try:
                    r = review_file(
                        str(fp),
                        repo_root=os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend")
                    )
                    reviews.append({
                        "file": str(fp).replace("\\", "/"),
                        "routing": r.get("routing", {"suggested_moves": []}),
                        "markdown": r.get("markdown", ""),
                    })
                except Exception as e:
                    reviews.append({
                        "file": str(fp).replace("\\", "/"),
                        "error": repr(e),
                        "routing": {"suggested_moves": []},
                        "markdown": "",
                    })

    resp: Dict[str, Any] = {
        "ok": True,
        "root": str(p),
        "dry_run": bool(dry_run),
        "converted": converted,
        "skipped": skipped,
        "reviews_count": len(reviews),
        "reviews": reviews,
    }

    # Persist artifact for post-processing (routing audit, moves, docs mirror)
    try:
        reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
        reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = reports_dir / f"convert_dryrun_{stamp}.json"
        out.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
        resp["artifact"] = str(out)
    except Exception as e:
        resp["artifact_error"] = repr(e)

    return resp
