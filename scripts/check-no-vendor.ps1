Param()

$ErrorActionPreference = 'Stop'

# List tracked files and flag those under vendor/output dirs (any depth)
$tracked = git ls-files -- . 2>$null
$blocked = @(
  '^(?:|.*/)?node_modules/',
  '^(?:|.*/)?\.venv/',
  '^(?:|.*/)?artifacts/',
  '^(?:|.*/)?dist/',
  '^(?:|.*/)?build/'
)

$bad = @()
foreach ($p in $tracked) {
  foreach ($re in $blocked) {
    if ($p -match $re) { $bad += $p; break }
  }
}

if ($bad.Count -gt 0) {
  Write-Error ("Vendored/artefact paths are tracked:`n" + ($bad -join "`n"))
  exit 1
}

Write-Host "No tracked vendor/artefact files detected."
