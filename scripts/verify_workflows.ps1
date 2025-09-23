param(
  [string]$RepoRoot = "C:\c\ai-orchestrator"
)

$ErrorActionPreference = 'Stop'
Set-Location $RepoRoot

$files = @(
  ".github/workflows/frontend-gates.yml",
  ".github/workflows/gates.yml"
)

foreach($f in $files){
  if(!(Test-Path $f)){ Write-Host "MISS $f"; continue }
  Write-Host "`n=== $f (committed) ==="
  # Show last committed content, not the working copy
  git show HEAD:$f 2>$null | Out-String | Write-Output
}

Write-Host "`nTip: If the above doesn't match your working files, commit & push, then run again."
