import os, sys, inspect
from pathlib import Path
# Force this repo to be import-first
sys.path.insert(0, str(Path.cwd()))
# Ensure env BEFORE importing routes/orchestrator
os.environ.setdefault("AIO_PROVIDER", "echo")
os.environ.setdefault("AIO_DRY_RUN", "false")

import app.server as srv
from fastapi import FastAPI
app: FastAPI = srv.app

# Introspect imports and routes
paths = sorted([r.path for r in app.router.routes])
print("SERVER_FILE:", srv.__file__)
import app.api.routes as r
print("ROUTES_FILE:", r.__file__)
print("HAS_DEBUG_PROVIDER:", "/debug/provider" in paths)
print("ENV:", {k: os.environ.get(k) for k in ["AIO_PROVIDER","AIO_DRY_RUN"]})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
