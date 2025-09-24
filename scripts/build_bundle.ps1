param([string]$Stamp = $(Get-Date -Format yyyyMMdd_HHmmss))
$ErrorActionPreference = "Stop"
$bundle = "reports\debug\cod1_inventory_bundle_$Stamp.md"
$tgz    = "artifacts\cod1_inventory_bundle_$Stamp.tar.gz"

# Make sure dirs exist
New-Item -ItemType Directory -Force -Path "reports\debug","artifacts" | Out-Null

# Load samples
$extTop   = (Import-Csv "reports\inv_frontend_ext_summary.csv" | Select-Object -First 12 | ConvertTo-Csv -NoTypeInformation) -join "`n"
$dupeHead = (Import-Csv "reports\inv_frontend_dupes.csv"       | Select-Object -First 10 | ConvertTo-Csv -NoTypeInformation) -join "`n"
$orch     = Get-Content "reports\debug\inventory_orchestrator_summary.md" -Raw

# Compose bundle
@"
# Cod1 Inventory Bundle ($Stamp)

## Frontend Summary
- Files CSV: `reports/inv_frontend_files.csv`
- Ext Summary: `reports/inv_frontend_ext_summary.csv`
- Dupes (basename+size): `reports/inv_frontend_dupes.csv`
- Conversion candidates: `reports/conversion_candidates.txt`

### Top extensions (sample)

$extTop

### Duplicate groups (sample)

$dupeHead


## Orchestrator Snapshot
$orch

## Notes
- Paths are absolute for reproducibility.
- SHA1 is a quick partial hash for triage.
- Full CSVs are included alongside this file.
"@ | Set-Content -Encoding UTF8 $bundle

# Create tar.gz outside 'reports' to avoid “in-use” errors
# Git Bash tar works fine from PowerShell if available; fallback to .NET if needed
try {
  & tar -czf $tgz reports
} catch {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $tmpZip = "artifacts\cod1_inventory_bundle_$Stamp.zip"
  if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force }
  [System.IO.Compression.ZipFile]::CreateFromDirectory("reports", $tmpZip)
}

"$bundle`n$tgz"
