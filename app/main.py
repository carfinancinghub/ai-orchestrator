# Path: C:\c\ai-orchestrator\app\main.py
# Version: 0.2.1
# Last Updated: 2025-08-30 20:52 PDT
# Purpose: FastAPI application entry point for CFH AI-Orchestrator
from __future__ import annotations
from fastapi import FastAPI
from api.routes import router as api_router
from pathlib import Path
from typing import List
from datetime import datetime, timezone
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ARTIFACTS_ROOT = Path("artifacts")
ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="CFH AI-Orchestrator", version="0.2.1")
app.include_router(api_router)

@app.get("/", operation_id="root")
def root():
    return {"ok": True, "service": "cfh-ai-orchestrator", "version": "0.2.1"}

@app.get("/healthz", operation_id="healthz")
def healthz():
    return {
        "ok": True,
        "service": "cfh-ai-orchestrator",
        "version": "0.2.1",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts_dir": str(ARTIFACTS_ROOT.resolve()),
        "artifacts_ready": ARTIFACTS_ROOT.exists(),
        "env": {
            "CFH_SCAN_PATH_PREFIXES": os.getenv("CFH_SCAN_PATH_PREFIXES"),
        },
    }

def emit_migration_list(run_id: str, ts_tsx_candidates: List) -> None:
    migration_path = ARTIFACTS_ROOT / f"migration_list_{run_id}.csv"
    migration_path.parent.mkdir(parents=True, exist_ok=True)
    with migration_path.open("w", encoding="utf-8") as f:
        f.write("repo,branch,path\n")
        for c in ts_tsx_candidates:
            f.write(f"{c.repo},{c.branch},{c.src_path}\n")
    logger.info(f"Migration list written to {migration_path}")