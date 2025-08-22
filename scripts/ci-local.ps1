param([int]$Port=8000); $ErrorActionPreference='Stop'
Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'uvicorn .*app.server:app' } | % { Stop-Process -Id $_.ProcessId -Force } 2>$null
if (python - <<'PY') {import importlib,sys;sys.exit(0 if importlib.util.find_spec("pytest_cov") else 1) PY) {
  pytest -q --cov=core --cov=app --cov-report=term-missing --junitxml=pytest-report.xml
} else { pytest -q --junitxml=pytest-report.xml }
$env:AIO_PROVIDER='echo'; $env:AIO_DRY_RUN='false'
$py = Join-Path $env:VIRTUAL_ENV 'Scripts/python.exe'
$proc = Start-Process -PassThru $py -ArgumentList '-m','uvicorn','app.server:app','--log-level','warning','--port',$Port
$ok=$false;1..40|%{try{irm \"http://127.0.0.1:$Port/_debug/routes\" -TimeoutSec 1|Out-Null;$ok=$true;break}catch{Start-Sleep -Milliseconds 150}}; if(-not $ok){ throw \"Server did not start on :$Port\" }
irm -Method Post \"http://127.0.0.1:$Port/orchestrator/run-stage/generate\" | Out-Null
\"ECHO => \" + ((irm \"http://127.0.0.1:$Port/orchestrator/artifacts/generate\").content -split \"`n\")[0] | Write-Output
irm -Method Post \"http://127.0.0.1:$Port/debug/provider\" -ContentType 'application/json' -Body (@{provider='upper'}|ConvertTo-Json) | Out-Null
irm -Method Post \"http://127.0.0.1:$Port/orchestrator/run-stage/generate\" | Out-Null
\"UPPER => \" + ((irm \"http://127.0.0.1:$Port/orchestrator/artifacts/generate\").content -split \"`n\")[0] | Write-Output
