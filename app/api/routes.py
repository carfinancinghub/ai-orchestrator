"""
Path: app/api/routes.py
Minimal router: orchestrator + convert + debug.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from core.orchestrator import Orchestrator

router = APIRouter()
orc = Orchestrator()

# ---- helpers ----
def _latest_artifact(stage: str) -> Optional[Path]:
    base = orc.config.base_dir
    if not base.exists():
        return None
    files = sorted(base.glob(f"{stage}_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

# ---- orchestrator ----
@router.get("/orchestrator/status")
async def status() -> Dict[str, object]:
    return {"status": "ready", "completed": orc.get_completed_stages(), "run_id": orc.get_run_id()}

@router.post("/orchestrator/run-all")
async def run_all() -> Dict[str, object]:
    return orc.run_all()

@router.post("/orchestrator/run-stage/{stage}")
async def run_stage(stage: str) -> Dict[str, object]:
    try:
        return orc.run_stage(stage)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orchestrator/artifacts/{stage}")
async def artifact(stage: str) -> Dict[str, object]:
    p = _latest_artifact(stage)
    if not p:
        raise HTTPException(status_code=404, detail="No artifacts for this stage")
    return {"artifact_file": str(p), "content": p.read_text(encoding="utf-8")}

# ---- JS→TS ----
@router.get("/convert/discover")
async def convert_discover(root: str = Query(".", description="Project root")) -> Dict[str, object]:
    items = orc.discover_conversion(Path(root))
    return {"count": len(items), "items": items}

@router.post("/convert/file")
async def convert_file(path: str, write: bool = False, tests: bool = True, force: bool = False) -> Dict[str, object]:
    src = Path(path)
    if not src.exists():
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "missing"})
    res = orc.convert_file(src, write_to_repo=write, include_tests=tests, force_write=force)
    return dict(res)

# ---- debug ----
@router.get("/debug/settings")
async def debug_settings() -> Dict[str, object]:
    s = getattr(orc, "settings", {})
    return {"pid": os.getpid(), "settings": {
        "DRY_RUN": s.get("DRY_RUN"),
        "PROVIDER": s.get("PROVIDER"),
    }}

@router.get("/debug/fs/exists")
async def debug_fs_exists(path: str) -> Dict[str, object]:
    p = Path(path)
    return {"path": str(p.resolve()), "exists": p.exists(), "is_file": p.is_file()}
