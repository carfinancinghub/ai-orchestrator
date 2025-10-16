# Path: C:\c\ai-orchestrator\app\main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router

app = FastAPI(title="CFH Orchestrator", version="0.1.0")

# (optional CORS; harmless locally)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "app": "cfh-orchestrator"}

# <- this is the missing piece: include the API router with /run-one
app.include_router(api_router)

# --- redis health hook ---
try:
    from app.routes.redis_health import router as _redis_router
    app.include_router(_redis_router)
except Exception as _e:
    # non-fatal in environments without that module
    pass
