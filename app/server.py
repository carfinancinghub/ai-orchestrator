"""
Path: app/server.py
FastAPI app bootstrap + router inclusion + routes inspector.
Run: python -m uvicorn app.server:app
"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import FastAPI

app = FastAPI(title="AI Orchestrator API")

router_error: str | None = None
try:
    from app.api import routes as _routes
    app.include_router(_routes.router)
except Exception as e:
    router_error = f"router-import-failed: {e.__class__.__name__}: {e}"

@app.get("/")
async def root() -> Dict[str, Any]:
    return {"message": "AI Orchestrator is running!", "router_error": router_error}

@app.get("/_debug/routes")
async def debug_routes() -> Dict[str, Any]:
    paths: List[str] = sorted([r.path for r in app.router.routes])
    return {"count": len(paths), "paths": paths, "router_error": router_error}
