# AI Orchestrator

![CI](https://github.com/carfinancinghub/ai-orchestrator/actions/workflows/ci.yml/badge.svg)

FastAPI service with a minimal orchestrator pipeline and JS→TS helper.

## Quick start

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn app.server:app --reload
# Smoke:
irm http://127.0.0.1:8000/_debug/routes
irm -Method GET  http://127.0.0.1:8000/orchestrator/status
irm -Method POST http://127.0.0.1:8000/orchestrator/run-stage/generate
JS→TS demo
powershell
Copy
Edit
ni -Force .\src\some.js -Value "export const add=(a,b)=>a+b;"
irm -Method GET  "http://127.0.0.1:8000/convert/discover?root=."
$env:AIO_DRY_RUN = "false"
irm -Method POST "http://127.0.0.1:8000/convert/file?path=src/some.js&write=true&tests=true"
Testing
powershell
Copy
Edit
pytest -q
Endpoints
GET / – health/info

GET /_debug/routes – list registered paths; shows router import errors if any

GET /orchestrator/status

POST /orchestrator/run-all

POST /orchestrator/run-stage/{stage}

GET /orchestrator/artifacts/{stage}

GET /convert/discover?root=.

POST /convert/file?path=src/some.js&write=true&tests=true

GET /debug/settings

GET /debug/fs/exists?path=...
