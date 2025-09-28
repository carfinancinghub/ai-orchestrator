# C:\c\ai-orchestrator\generate-cfh-discovery.ps1
# Discovery across CFH paths with heavy-folder excludes. Writes CSV + summary MD.
# Optional: -AutoCommitAndPush only stages the generated report files.

[CmdletBinding()]
param(
  [switch]$AutoCommitAndPush
)

$ErrorActionPreference = "Stop"

# ----- CONFIG -----
$RepoRoot = "C:\c\ai-orchestrator"

# Roots to scan
$Roots = @(
  "C:\c\ai-orchestrator",
  "C:\CFH",
  "C:\cfh",
  "C:\Users\Agasi5\Desktop\cfh",
  "M:\cfh"
)

# Exclusion regex (folders anywhere in path)
# NOTE: added \.mypy_cache and \logs (your request), plus the usual noisy dirs.
$ExcludePattern = '\\node_modules\\|\\\.venv\\|\\venv\\|\\dist\\|\\build\\|\\\.git\\|\\__pycache__\\|\\\.next\\|\\coverage\\|\\out\\|\\release\\|\\tmp\\|\\temp\\|\\\.mypy_cache\\|\\logs\\'

# What to inventory (extensions, case-insensitive)
$Exts = @(".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".yml", ".yaml", ".md", ".txt", ".html", ".css")

# Output
$Stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$OutDir = Join-Path $RepoRoot "reports\discovery\$Stamp"
$MasterCsv = Join-Path $OutDir "master_inventory.csv"
$DupCsv    = Join-Path $OutDir "duplicates.csv"
$SummaryMd = Join-Path $OutDir "summary.md"

# ----- HELPERS -----
function Ensure-Dir([string]$p) {
  if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}
function Hash-File([string]$path) {
  try { return (Get-FileHash -Algorithm SHA1 -LiteralPath $path -ErrorAction Stop).Hash }
  catch { return "" }
}
function Is-Excluded([string]$full) {
  return ($full -match $ExcludePattern)
}
function Should-Keep([System.IO.FileInfo]$f) {
  if (Is-Excluded $f.FullName) { return $false }
  return ($Exts -contains $f.Extension.ToLower())
}

# ----- RUN -----
Ensure-Dir $OutDir
Write-Host "Scanning CFH roots..." -ForegroundColor Cyan

$items = New-Object System.Collections.Generic.List[object]
foreach ($root in $Roots) {
  Write-Host "Scanning $root ..." -ForegroundColor Yellow
  if (-not (Test-Path -LiteralPath $root)) { continue }
  $files = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue
  foreach ($f in $files) {
    if (Should-Keep $f) {
      $rel = try { $f.FullName.Substring($root.Length).TrimStart('\') } catch { $f.Name }
      $items.Add([pscustomobject]@{
        Root          = $root
        RelativePath  = $rel
        FullPath      = $f.FullName
        Extension     = $f.Extension.ToLower()
        SizeBytes     = $f.Length
        LastWriteTime = $f.LastWriteTime
      })
    }
  }
}

# Write master CSV
$items | Sort-Object FullPath | Export-Csv -LiteralPath $MasterCsv -NoTypeInformation -Encoding UTF8

# Duplicate detection (by size + SHA1 for files <= 25MB)
$dups = $items |
  Group-Object SizeBytes |
  Where-Object { $_.Count -gt 1 } |
  ForEach-Object {
    foreach ($x in $_.Group) {
      $hash = if ($x.SizeBytes -le 25MB) { Hash-File $x.FullPath } else { "" }
      [pscustomobject]@{
        SizeBytes = $x.SizeBytes
        Hash      = $hash
        FullPath  = $x.FullPath
      }
    }
  } |
  Group-Object SizeBytes, Hash |
  Where-Object { $_.Count -gt 1 } |
  ForEach-Object {
    $_.Group
  }

if ($dups) {
  $dups | Export-Csv -LiteralPath $DupCsv -NoTypeInformation -Encoding UTF8
} else {
  # still create an empty file so the path exists
  "" | Out-File -LiteralPath $DupCsv -Encoding UTF8
}

# Summary
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Discovery Summary")
$lines.Add("")
$lines.Add("**Timestamp:** $Stamp  ")
$lines.Add("**Roots:**")
foreach ($r in $Roots) { $lines.Add("- $r") }
$lines.Add("")
$lines.Add("**Excludes (regex):**")
$lines.Add("")
$lines.Add("```regex")
$lines.Add($ExcludePattern)
$lines.Add("```")
$lines.Add("")
$lines.Add("## Totals by extension")
$items |
  Group-Object Extension |
  Sort-Object Name |
  ForEach-Object {
    $lines.Add( ("- {0} : {1}" -f $_.Name, $_.Count) )
  }

$lines.Add("")
$lines.Add("## Artifacts")
$lines.Add("")
$lines.Add("```text")
$lines.Add($MasterCsv)
$lines.Add($DupCsv)
$lines.Add("```")
$lines.Add("")
$lines.Add("_Note: duplicates grouped by (SizeBytes, SHA1 if <=25MB). Larger files skip hashing._")
$lines | Set-Content -LiteralPath $SummaryMd -Encoding UTF8

Write-Host "`n=== Artifacts ===" -ForegroundColor Green
Write-Host $MasterCsv
Write-Host $DupCsv
Write-Host $SummaryMd
Write-Host "================="

# Optional: commit & push ONLY the generated reports (to avoid staging JS/JSX)
if ($AutoCommitAndPush) {
  Push-Location $RepoRoot
  try {
    git add -- $MasterCsv $DupCsv $SummaryMd | Out-Null
    git commit -m "chore(discovery): reports $Stamp" | Out-Null
    # Try to push; if a pre-commit hook blocks, we still keep the files locally
    git push | Out-Null
    Write-Host "Pushed discovery reports." -ForegroundColor Green
  } catch {
    Write-Warning "Git push skipped/failed: $($_.Exception.Message)"
  }
  Pop-Location
}

Write-Host "`nDone. Reports in: $OutDir"
