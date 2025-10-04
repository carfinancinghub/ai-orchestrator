# C:\c\ai-orchestrator\app\server.py

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

# --------------------------------------------------------------------------------------
# Repo location & import path
# --------------------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# --------------------------------------------------------------------------------------
# Optional: auto-load .env at startup (so you don't need --env-file each time)
# Requires: pip install python-dotenv
# --------------------------------------------------------------------------------------
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=False)
except Exception:
    # It's okay if python-dotenv isn't installed or .env is missing.
    pass

# --------------------------------------------------------------------------------------
# Import router (may fail at dev time; we surface error via /readyz)
# --------------------------------------------------------------------------------------
try:
    from api.routes import router
except Exception as e:  # pragma: no cover
    router = None  # type: ignore[assignment]
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

# --------------------------------------------------------------------------------------
# Environment / config
# --------------------------------------------------------------------------------------
SERVICE_NAME = "orchestrator"
DEFAULT_HOST = os.getenv("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("PORT", "8121"))
ALLOWED_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Provider hints we show in /readyz
PROVIDER_ENV_HINTS = [
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROK_API_KEY",
]

# Robust REPORTS_DIR resolution: make absolute even if a relative value is given
_env_reports = os.getenv("REPORTS_DIR")
if _env_reports:
    _reports_path = Path(_env_reports)
    if not _reports_path.is_absolute():
        _reports_path = (_REPO_ROOT / _reports_path).resolve()
else:
    _reports_path = (_REPO_ROOT / "reports").resolve()
REPORTS_DIR: Path = _reports_path

# --------------------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------------------
def create_app() -> FastAPI:
    _configure_logging()
    app = FastAPI(
        title="AI Orchestrator",
        version=os.getenv("ORCHESTRATOR_VERSION", "0.1.0"),
    )

    # CORS: honor the env list (comma-separated). Use ["*"] during prototyping if needed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if router is not None:
        app.include_router(router)

    _register_health_endpoints(app)
    _register_error_handlers(app)
    return app

# --------------------------------------------------------------------------------------
# Meta / health endpoints
# --------------------------------------------------------------------------------------
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

        # --- Provider checks: require SDK import AND API key to be True ---
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

        # Back-compat flat flags (true only when both SDK+key are present)
        checks["sdk_openai"] = providers["openai"]["ok"]
        checks["sdk_gemini"] = providers["gemini"]["ok"]
        checks["sdk_grok_xai"] = providers["grok"]["ok"]
        checks["sdk_anthropic"] = providers["anthropic"]["ok"]

        # Provider env hint list (useful for quick setup)
        missing_envs = [k for k in PROVIDER_ENV_HINTS if not _has_key(k)]
        checks["provider_env_missing"] = missing_envs

        # CFH-specific probe (as requested)
        checks["cfh_root"] = os.path.exists(r"C:\CFH\frontend")

        # Overall ready flag (unchanged logic)
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
                methods = sorted(
                    m for m in (getattr(r, "methods", []) or []) if m != "HEAD"
                )
                name = getattr(r, "name", None)
                tags = getattr(r, "tags", None) or []
                items.append(
                    {"path": path, "methods": methods, "name": name, "tags": tags}
                )
            except Exception as e:
                items.append({"path": "<error>", "err": repr(e)})
        return {"count": len(items), "routes": items}

# --------------------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------------------
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

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
def _configure_logging() -> None:
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("uvicorn.access").setLevel(level)

# --------------------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------------------
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
