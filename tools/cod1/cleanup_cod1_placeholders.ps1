param([string]$AIO = "C:\c\ai-orchestrator")
$ErrorActionPreference = "Stop"
Set-Location $AIO
$targets = Get-ChildItem -Recurse "artifacts\generated" -File | Where-Object {
  (Get-Content $_.FullName -Raw) -match "export const PLACEHOLDER = true;"
}
$count = 0
foreach ($t in $targets) { Remove-Item $t.FullName -Force; $count++ }
Write-Host "Removed $count placeholder-generated files."
