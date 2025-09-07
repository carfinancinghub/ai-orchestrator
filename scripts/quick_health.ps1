param([string]$Root = "C:\c\ai-orchestrator")
$ErrorActionPreference = "Stop"

# Resolve & prepare paths
$Root    = (Resolve-Path $Root).Path
$Reports = Join-Path $Root "reports"
$QH      = Join-Path $Reports "quick_health.txt"
New-Item -ItemType Directory -Force -Path $Reports | Out-Null

function Append([string]$text) { $text | Tee-Object -FilePath $QH -Append | Out-Host }

Set-Location $Root
"== Quick Health (ai-orchestrator) ==" | Tee-Object -FilePath $QH
Append "root: $Root"
Append "when: $(Get-Date -Format o)"

Append "--- versions ---"
try { (& python --version) 2>&1 | Tee-Object -FilePath $QH -Append } catch {}
try { (& python -m pip --version) 2>&1 | Tee-Object -FilePath $QH -Append } catch {}
try { (& python -m ruff --version) 2>&1 | Tee-Object -FilePath $QH -Append } catch {}
try { (& python -m mypy --version) 2>&1 | Tee-Object -FilePath $QH -Append } catch {}
try { (& python -m pytest --version) 2>&1 | Tee-Object -FilePath $QH -Append } catch {}

Append "`n--- inventory_scan ---"
try {
  & python "$Root\tools\inventory_scan.py" --root "$Root" 2>&1 | Tee-Object -FilePath $QH -Append
} catch {
  Append "inventory_scan FAILED: $($_.Exception.Message)"
}

Append "`n--- ruff ---"
try {
  & python -m ruff check . 2>&1 | Tee-Object -FilePath $QH -Append
} catch {
  Append "ruff FAILED: $($_.Exception.Message)"
}

Append "`n--- mypy ---"
try {
  & python -m mypy app core tools 2>&1 | Tee-Object -FilePath $QH -Append
} catch {
  Append "mypy FAILED: $($_.Exception.Message)"
}

Append "`n--- pytest ---"
try {
  & python -m pytest -q 2>&1 | Tee-Object -FilePath $QH -Append
} catch {
  Append "pytest FAILED: $($_.Exception.Message)"
}

Append "`nWrote $QH"
