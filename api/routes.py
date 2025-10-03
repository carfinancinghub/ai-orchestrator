from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

# --- providers ---
@router.get("/providers/list", tags=["providers"], name="providers_list")
def providers_list() -> dict:
    return {"providers": ["openai","gemini","anthropic","grok"]}

@router.get("/providers/selftest", tags=["providers"], name="providers_selftest")
def providers_selftest() -> dict:
    return {"ok": True}

# --- convert ---
@router.post("/convert/file", tags=["convert"], name="convert_file")
def convert_file() -> dict:
    # stub for smoke; replace with real logic
    return {"ok": True, "converted": 1, "skipped": 0}

@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(root: str = "src", dry_run: bool = True) -> dict:
    # stub for smoke; replace with real logic
    return {"ok": True, "root": root, "dry_run": dry_run, "converted": [], "skipped": []}
