\"\"\"Path: aio_app/server.py\"\"\"
from __future__ import annotations
from typing import Any, Dict, List
from pathlib import Path
import os
from fastapi import FastAPI

app = FastAPI(title="AI Orchestrator API")

router_error: str | None = None
try:
    from aio_app.api import routes as _routes  # type: ignore
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

@app.get("/_debug/modules")
async def debug_modules() -> Dict[str, Any]:
    import sys
    info: Dict[str, Any] = {
        "pid": os.getpid(),
        "cwd": str(Path.cwd()),
        "sys_path_head": sys.path[:6],
        "env": {"AIO_PROVIDER": os.getenv("AIO_PROVIDER"), "AIO_DRY_RUN": os.getenv("AIO_DRY_RUN")},
        "router_error": router_error,
    }
    try:
        import aio_app.api.routes as routes_mod  # type: ignore
        info["routes_file"] = getattr(routes_mod, "__file__", None)
    except Exception as e:
        info["routes_import_error"] = repr(e)
    try:
        import core.orchestrator as orch_mod
        info["orchestrator_file"] = getattr(orch_mod, "__file__", None)
    except Exception as e:
        info["orchestrator_import_error"] = repr(e)
    info["router_has_debug_provider"] = ("/debug/provider" in [r.path for r in app.router.routes])
    return info
