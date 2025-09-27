from __future__ import annotations
from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="AI Orchestrator")
app.include_router(router)

# --- helpers: orchestrator status + meta routes (for SG Man / bots) ---
try:
    app  # type: ignore[name-defined]
except NameError:
    app = FastAPI(title="AI Orchestrator")

@app.get("/orchestrator/status")
def orchestrator_status():
    return {"ok": True, "service": "orchestrator"}

@app.get("/_meta/routes")
def list_routes():
    return [getattr(r, "path", str(r)) for r in app.router.routes]
# --- end helpers ---