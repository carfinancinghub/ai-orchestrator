from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()

class ConvertTreeReq(BaseModel):
    root: str = "src"
    dry_run: bool = True

@router.get("/providers/list", tags=["providers"], name="providers_list")
def providers_list() -> dict:
    return {"providers": ["openai", "gemini", "anthropic", "grok"]}

@router.get("/providers/selftest", tags=["providers"], name="providers_selftest")
def providers_selftest() -> dict:
    return {"ok": True}

@router.post("/convert/file", tags=["convert"], name="convert_file")
def convert_file() -> dict:
    return {"ok": True, "converted": 1, "skipped": 0}

@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(req: ConvertTreeReq) -> dict:
    root = Path(req.root)
    converted, skipped = [], []
    if root.exists() and root.is_dir():
        for p in list(root.rglob("*"))[:50]:
            (converted if p.is_file() else skipped).append(str(p).replace("\\", "/"))
    return {"ok": True, "root": str(root), "dry_run": req.dry_run,
            "converted": converted, "skipped": skipped}
