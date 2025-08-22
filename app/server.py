"""Path: app/server.py"""

from __future__ import annotations
from typing import Any, Dict, List
from pathlib import Path
import os
from fastapi import FastAPI

app = FastAPI(title="AI Orchestrator API")

router_error: str | None = None
try:
    from app.api import routes as _routes  # type: ignore
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
from typing import Any, Dict

@app.get("/_debug/modules")
async def _debug_modules() -> Dict[str, Any]:
    import sys, app.api.routes as routes_mod, core.orchestrator as orch_mod  # type: ignore
    return {
        "pid": os.getpid(),
        "routes_file": getattr(routes_mod, "__file__", None),
        "orchestrator_file": getattr(orch_mod, "__file__", None),
        "env": {"AIO_PROVIDER": os.getenv("AIO_PROVIDER"), "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN")},
    }

@app.get("/__peek")
async def __peek() -> Dict[str, Any]:
    from app.api import routes as r  # type: ignore
    prov = getattr(r, "orc", None)
    p = getattr(prov, "provider", None) if prov else None
    return {
        "provider_loaded": p is not None,
        "provider_class": (p.__class__.__name__ if p else None),
        "settings": getattr(prov, "settings", {}),
        "env": {"AIO_PROVIDER": os.getenv("AIO_PROVIDER"), "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN")},
    }
