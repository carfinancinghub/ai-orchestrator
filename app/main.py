from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    # Optional: routes may not exist yet during early scaffolding
    from app.api.routes import router as api_router
except Exception:
    api_router = None

def create_app() -> FastAPI:
    app = FastAPI(title="AI Orchestrator API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"ok": True}

    if api_router is not None:
        app.include_router(api_router)

    return app

app = create_app()
