from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

# --- sys.path wiring -----------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# --- main API router (optional if import fails) --------------------------------
try:
    from api.routes import router
except Exception as e:
    router = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

<<<<<<< HEAD
# --- optional redis health router (safe if missing) ----------------------------
=======




>>>>>>> origin/main
try:
    from app.routes.redis_health import router as redis_health_router

try:
    from app.routes.build_ts import router as build_ts_router
except Exception:
    build_ts_router = None
except Exception:
    redis_health_router = None
<<<<<<< HEAD

# --- settings ------------------------------------------------------------------
=======
>>>>>>> origin/main
SERVICE_NAME = "orchestrator"
DEFAULT_HOST = os.getenv("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("PORT", "8121"))
ALLOWED_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
PROVIDER_ENV_HINTS = ["OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GROK_API_KEY"]
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", _REPO_ROOT / "reports"))

# --- app factory ---------------------------------------------------------------
def create_app() -> FastAPI:
    _configure_logging()
    app = FastAPI(title="AI Orchestrator", version=os.getenv("ORCHESTRATOR_VERSION", "0.1.0"))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # swap with ALLOWED_ORIGINS if you need strict CORS
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

<<<<<<< HEAD
    # main router
    if router is not None:
        app.include_router(router)

    
    
    # optional build_ts router
    if "build_ts_router" in globals() and build_ts_router is not None:
        app.include_router(build_ts_router)
# optional build_ts router
    if "build_ts_router" in globals() and build_ts_router is not None:
        app.include_router(build_ts_router)

    _register_health_endpoints(app)
    _register_error_handlers(app)
    return app

# --- meta + readyz -------------------------------------------------------------
def _register_health_endpoints(app: FastAPI) -> None:
    @app.get("/", tags=["meta"])
    def root() -> Dict[str, Any]:
        return {
            "ok": True,
            "service": SERVICE_NAME,
            "version": app.version,
            "docs": "/docs",
            "routes": "/_meta/routes",
            "status": "/orchestrator/status",
            "readyz": "/readyz",
        }

    @app.get("/_health", tags=["meta"])
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.get("/orchestrator/status", tags=["meta"])
    def status() -> Dict[str, Any]:
        return {"ok": True, "service": SERVICE_NAME}

    @app.get("/readyz", tags=["meta"])
    def readyz() -> Dict[str, Any]:
        checks: Dict[str, Any] = {}

        # Router import status
        checks["router_loaded"] = router is not None
        if router is None and "_IMPORT_ERROR" in globals():
            checks["router_error"] = repr(_IMPORT_ERROR)

        # Reports directory availability & writability
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            writable = os.access(REPORTS_DIR, os.W_OK)
        except Exception as e:
            writable = False
            checks["reports_dir_error"] = repr(e)
        checks["reports_dir"] = str(REPORTS_DIR)
        checks["reports_dir_writable"] = bool(writable)

        # Provider checks
        import importlib

        def _has_sdk(*import_names: str) -> bool:
            for name in import_names:
                try:
                    importlib.import_module(name)
                    return True
                except Exception:
                    continue
            return False

        def _has_key(env_var: str) -> bool:
            v = os.getenv(env_var)
            return bool(v and v.strip())

        def _provider_status(import_names, env_var):
            sdk = _has_sdk(*import_names)
            key = _has_key(env_var)
            return {"sdk": sdk, "key": key, "ok": (sdk and key)}

        providers = {
            "openai": _provider_status(["openai"], "OPENAI_API_KEY"),
            "gemini": _provider_status(["google.generativeai"], "GEMINI_API_KEY"),
            "grok": _provider_status(["xai", "xai_sdk", "grok"], "GROK_API_KEY"),
            "anthropic": _provider_status(["anthropic"], "ANTHROPIC_API_KEY"),
        }
        checks["providers"] = providers

        # Back-compat flags (true only when SDK+key present)
        checks["sdk_openai"] = providers["openai"]["ok"]
        checks["sdk_gemini"] = providers["gemini"]["ok"]
        checks["sdk_grok_xai"] = providers["grok"]["ok"]
        checks["sdk_anthropic"] = providers["anthropic"]["ok"]

        # Missing env hints
        missing_envs = [k for k in PROVIDER_ENV_HINTS if not _has_key(k)]
        checks["provider_env_missing"] = missing_envs
        checks["providers_enabled"] = [name for name, st in providers.items() if st.get("ok")]

        # CFH-specific probe
        checks["cfh_root"] = os.path.exists(r"C:\CFH\frontend")

        ok = bool(checks["router_loaded"]) and bool(checks["reports_dir_writable"])
        return {"ok": ok, "checks": checks}

    @app.get("/_meta/routes", tags=["meta"])
    def list_routes() -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for r in app.router.routes:
            try:
                path = getattr(r, "path", None)
                if not path:
                    continue
                methods = sorted(m for m in (getattr(r, "methods", []) or []) if m != "HEAD")
                name = getattr(r, "name", None)
                tags = getattr(r, "tags", None) or []
                items.append({"path": path, "methods": methods, "name": name, "tags": tags})
            except Exception as e:
                items.append({"path": "<error>", "err": repr(e)})
        return {"count": len(items), "routes": items}

# --- error handlers ------------------------------------------------------------
def _register_error_handlers(app: FastAPI) -> None:
    logger = logging.getLogger("uvicorn.error")

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("validation_error: %s", exc)
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": "validation_error", "details": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def on_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "internal_error", "detail": repr(exc)},
        )

# --- logging -------------------------------------------------------------------
def _configure_logging() -> None:
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%%Y-%%m-%%d %%H:%%M:%%S",
    )
    logging.getLogger("uvicorn.access").setLevel(level)

# --- CLI entrypoint ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.server:create_app",
        factory=True,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        log_level=LOG_LEVEL.lower(),
        reload=bool(os.getenv("RELOAD", "0") == "1"),
    )