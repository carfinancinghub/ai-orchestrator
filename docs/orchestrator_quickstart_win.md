# AI Orchestrator — Windows Quickstart & Recovery

## 1) Make the FastAPI app resolvable
Create these files (or merge into your code):
- `app/main.py`  → see `fastapi_app_main.py` in this package
- `app/api/routes.py` → see `fastapi_app_api_routes.py`
Also ensure empty `__init__.py` in `app/` and `app/api/`.

Run locally:
```powershell
Set-Location C:\c\ai-orchestrator
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
# then check:  Invoke-WebRequest http://127.0.0.1:8010/health
```

## 2) Fix “server exited” & port issues
```powershell
$p = Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue | Select -First 1 -Expand OwningProcess
if ($p) { Stop-Process -Id $p -Force }
```

## 3) Agent lite run (use absolute globs)
The lite script may ignore relative globs. Prefer absolute ones:
```powershell
.\scripts\agent-run-lite.ps1 `
  -Root  'C:\Backup_Projects\CFH\frontend' `
  -JsList  'C:\Backup_Projects\CFH\frontend\src\**\*.js' `
  -JsxList 'C:\Backup_Projects\CFH\frontend\src\**\*.jsx' `
  -TsList  'C:\Backup_Projects\CFH\frontend\src\**\*.ts' `
  -TsxList 'C:\Backup_Projects\CFH\frontend\src\**\*.tsx'
```

If you still see `Below threshold (0 <= 1200)`, it means no files were matched.
Switch to the absolute patterns above or reduce the threshold inside the script temporarily.

## 4) One-prompt convenience
Copy `scripts_one-prompt.ps1` from this package to `scripts\one-prompt.ps1`, then:
```powershell
.\scripts\one-prompt.ps1 -PromptKey review -Tier premium -Root 'C:\Backup_Projects\CFH\frontend'
```

## 5) LLM smoke (optional)
- Copy `scripts_smoke_llms.py` to `scripts\smoke_llms.py`
- `pip install openai anthropic google-genai`
- Put keys in `.env`:
  ```
  OPENAI_API_KEY=sk-...
  ANTHROPIC_API_KEY=SK_DEMO_KEY-...
  GOOGLE_API_KEY=AIza...
  ```
- Run: `python .\scripts\smoke_llms.py`

## 6) Guardrails already in place
- `.gitattributes` normalizes EOLs
- `.git/hooks/pre-commit` blocks absolute Windows paths
