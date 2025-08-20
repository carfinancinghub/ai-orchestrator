# Path: scripts/quick-verify.ps1 
# Runs tests + prints first artifact line via API

python -m pytest -q
$env:AIO_PROVIDER='echo'; $env:AIO_DRY_RUN='false'
Stop-Process -Name uvicorn -ErrorAction SilentlyContinue
Start-Process -PassThru python -ArgumentList '-m','uvicorn','app.server:app','--log-level','warning' | Out-Null
Start-Sleep -Seconds 1
((irm http://127.0.0.1:8000/orchestrator/run-stage/generate -Method Post).status) | Out-Null
((irm http://127.0.0.1:8000/orchestrator/artifacts/generate).content -split "`n")[0]