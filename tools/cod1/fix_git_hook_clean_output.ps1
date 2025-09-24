param([string]$Repo = "C:\c\ai-orchestrator")
$ErrorActionPreference = "Stop"
Set-Location $Repo
$hookDir = Join-Path $Repo ".git\hooks"
if (-not (Test-Path $hookDir)) { throw "No hooks dir at $hookDir" }
Get-ChildItem $hookDir -File | ForEach-Object {
  $p = $_.FullName
  $txt = Get-Content $p -Raw
  $txt = $txt -replace '1>&2','' -replace '2>&1','' -replace 'Write-Error','Write-Host'
  Set-Content -Path $p -Value $txt -Encoding UTF8
}
Write-Host "Hooks normalized to stdout. Ensure success paths exit 0."
