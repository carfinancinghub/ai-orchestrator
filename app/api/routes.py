"""
Path: app/api/routes.py
Description: FastAPI routes incl. provider management.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.orchestrator import Orchestrator

router = APIRouter()
orc = Orchestrator()

# ---------- helpers ----------

def _latest_artifact(stage: str) -> Optional[Path]:
    base = orc.config.base_dir
    if not base.exists():
        return None
    files = sorted(base.glob(f"{stage}_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

# ---------- orchestrator endpoints ----------

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
    except Exception as e:  # minimal surface for client
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orchestrator/artifacts/{stage}")
async def artifact(stage: str) -> Dict[str, object]:
    p = _latest_artifact(stage)
    if not p:
        raise HTTPException(status_code=404, detail="No artifacts for this stage")
    return {"artifact_file": str(p), "content": p.read_text(encoding="utf-8")}

# ---------- debug endpoints ----------

@router.get("/debug/settings")
async def debug_settings() -> Dict[str, object]:
    s = getattr(orc, "settings", {})
    return {"pid": os.getpid(), "settings": {"DRY_RUN": s.get("DRY_RUN"), "PROVIDER": s.get("PROVIDER")}}

class ProviderUpdate(BaseModel):
    provider: str | None = None

@router.get("/debug/provider")
async def debug_provider_get() -> Dict[str, object]:
    orc._ensure_provider()
    prov = getattr(orc, "provider", None)
    return {
        "provider_loaded": prov is not None,
        "provider_class": (prov.__class__.__name__ if prov else None),
        "env": {"AIO_PROVIDER": os.getenv("AIO_PROVIDER"), "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN")},
        "settings": getattr(orc, "settings", {}),
    }

@router.post("/debug/provider")
async def debug_provider_set(update: ProviderUpdate) -> Dict[str, object]:
    if update.provider:
        os.environ["AIO_PROVIDER"] = update.provider
    else:
        os.environ.pop("AIO_PROVIDER", None)
    orc._ensure_provider()
    prov = getattr(orc, "provider", None)
    return {
        "provider_loaded": prov is not None,
        "provider_class": (prov.__class__.__name__ if prov else None),
        "env": {"AIO_PROVIDER": os.getenv("AIO_PROVIDER"), "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN")},
        "settings": getattr(orc, "settings", {}),
    }
