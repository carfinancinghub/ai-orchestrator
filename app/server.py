from __future__ import annotations

import os
from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="AI Orchestrator")
app.include_router(router)

# --- helpers: orchestrator status + meta routes (for SG Man / bots) ---
@app.get("/orchestrator/status")
def orchestrator_status():
    """Liveness probe: process is up and FastAPI is serving."""
    return {"ok": True, "service": "orchestrator"}

@app.get("/readyz")
def readyz():
    """Readiness probe: extend with dependency checks (providers, FS, etc.)."""
    checks = {
        "router_loaded": router is not None,
        "reports_dir_writable": os.access("reports/", os.W_OK) if os.path.exists("reports/") else False,
        # TODO: add provider/env checks (e.g., GEMINI_API_KEY in os.environ), cache reachability, etc.
    }
    return {"ok": all(checks.values()), "checks": checks}

@app.get("/_meta/routes")
def list_routes():
    """Return path, methods, tags, and name for auditing/automation."""
    out = []
    for r in app.router.routes:
        path = getattr(r, "path", None)
        methods = sorted([m for m in (getattr(r, "methods", []) or []) if m != "HEAD"])  # Filter noise
        name = getattr(r, "name", None)
        tags = getattr(r, "tags", None) or []
        if path:
            out.append({"path": path, "methods": methods, "name": name, "tags": tags})
    return out
# --- end helpers ---

# --- app factory for uvicorn --factory ---
def create_app():
    """Factory for `uvicorn --factory app.server:create_app`."""
    return app
# --- end factory ---
