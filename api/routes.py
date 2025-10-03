from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, Body

router = APIRouter()

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
    # stub for smoke; replace with real logic
    return {"ok": True, "converted": 1, "skipped": 0}


@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(
    root: str = Body("src", embed=True),        # expects {"root": "..."}
    dry_run: bool = Body(True, embed=True),     # expects {"dry_run": true}
) -> dict:
    p = Path(root)
    converted: list[str] = []
    skipped: list[str] = []

    if p.exists() and p.is_dir():
        # keep output small & deterministic
        for item in list(p.rglob("*"))[:50]:
            (converted if item.is_file() else skipped).append(str(item).replace("\\", "/"))

    return {
        "ok": True,
        "root": str(p),
        "dry_run": bool(dry_run),
        "converted": converted,
        "skipped": skipped,
    }
