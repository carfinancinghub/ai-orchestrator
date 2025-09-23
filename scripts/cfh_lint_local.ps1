# ==== CFH financing allow-list (Cod1) ====
$global:CFH_ALLOW_PATTERNS = @(
  'interface\s+LoanTerms\s*\{[^}]*\}',
  '\bPaymentSchedule\b',
  '\bAmortization(?:Table|Schedule)\b',
  '\bAPR\b',
  '\bPrincipal\b',
  '\bDownPayment\b',
  '\bBalloonPayment\b',
  '\bDealer(?:ID|Code)\b'
)

function Bypass-AllowedPattern($line){
  foreach($p in $global:CFH_ALLOW_PATTERNS){
    if($line -match $p){ return $true }
  }
  return $false
}
# ==== END allow-list ====

<#  scripts\cfh_lint_local.ps1
    Local CFH lint (no GitHub calls): scans a given root (default C:\Backup_Projects\CFH\frontend),
    writes a JSON summary, and returns nonzero on hard violations unless soft mode is set.
#>
[CmdletBinding()]
param(
  [string]$Root    = "C:\Backup_Projects\CFH\frontend",
  [string]$OutPath,                # optional explicit summary path
  [switch]$HardMode                # force hard mode (ignore CFH_LINT_SOFT)
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName 'System.IO'

# Normalize root
$rootPath  = [System.IO.Path]::GetFullPath($Root)
if (-not (Test-Path $rootPath)) { throw "Root not found: $rootPath" }

# Summary output path
if ([string]::IsNullOrWhiteSpace($OutPath)) {
  $reportDir = Join-Path $rootPath 'reports'
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
  $summary   = Join-Path $reportDir 'cfh_lint_summary.json'
} else {
  $summaryDir = Split-Path $OutPath -Parent
  if (-not (Test-Path $summaryDir)) { New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null }
  $summary = [System.IO.Path]::GetFullPath($OutPath)
}

# Exclusions (substring tokens, not regex)
$excludeTokens = @(
  '/node_modules/', '/dist/', '/build/', '/coverage/', '/.git/',
  '/zipped_batches/', '/conversion/', '/backend/',
  '/.tmp', '/.temp', '/.tmp_tests/', '/.cache', '/.output', '/.idea'
)

# File globs to include and test/dev files to ignore for hard rules
$includeExts   = @('.ts', '.tsx')
$ignoreForHard = @('/tests/', '.test.', '.spec.', '/__mocks__/', '/cypress/')

function Should-Exclude([string]$path){
  $pp = ($path -replace '\\','/').ToLowerInvariant()
  foreach($tok in $excludeTokens){ if ($pp.Contains($tok)) { return $true } }
  return $false
}
function IsTestish([string]$rel){
  $pp = ($rel -replace '\\','/').ToLowerInvariant()
  foreach($tok in $ignoreForHard){ if ($pp.Contains($tok)) { return $true } }
  return $false
}

# Fast enumeration
$files = New-Object System.Collections.Generic.List[string]
foreach($ext in $includeExts){
  foreach($f in [System.IO.Directory]::EnumerateFiles($rootPath, "*$ext", [System.IO.SearchOption]::AllDirectories)){
    if (Should-Exclude $f) { continue }
    $files.Add($f)
  }
}

# CFH rules
$hardPatterns = @(
  @{ name='Any';        rx='\bany\b' },
  @{ name='TsIgnore';   rx='@ts-ignore' }
)
$softPatterns = @(
  @{ name='TODO';       rx='TODO|FIXME' },
  @{ name='LegacyJS';   rx='\brequire\(' }
)

$violations   = New-Object System.Collections.Generic.List[object]
$observations = New-Object System.Collections.Generic.List[object]

foreach($full in $files){
  $rel = $full.Substring($rootPath.Length).TrimStart('\','/')
  $content = [System.IO.File]::ReadAllText($full)

  # per-line scan so we can apply the financing bypass precisely
  $lines = $content -split "`r?`n"
  for($i=0; $i -lt $lines.Count; $i++){
    $line = $lines[$i]

    foreach($hp in $hardPatterns){
      if($line -match $hp.rx){
        if (Bypass-AllowedPattern $line) { continue }                     # financing pattern -> skip
        if (-not (IsTestish $rel)){                                       # not a test file -> record hard violation
          $violations.Add([pscustomobject]@{
            file = $rel; rule = $hp.name; rx = $hp.rx; type = 'hard'; line = ($i+1)
          })
        }
      }
    }

    foreach($sp in $softPatterns){
      if($line -match $sp.rx){
        $observations.Add([pscustomobject]@{
          file = $rel; rule = $sp.name; rx = $sp.rx; type = 'soft'; line = ($i+1)
        })
      }
    }
  }
}

$result = [pscustomobject]@{
  root          = $rootPath
  files_scanned = $files.Count
  hard_fail     = ($violations.Count -gt 0)
  hard_count    = $violations.Count
  soft_count    = $observations.Count
  violations    = $violations
  observations  = $observations
  generated_at  = (Get-Date).ToString('s')
}

# Mode selection
if ($HardMode.IsPresent) {
  # Force hard mode (ignore env)
  $result.hard_fail = ($violations.Count -gt 0)
} else {
  # soft mode toggle via env var (0/1)
  $soft = 0
  try { $soft = [int]($env:CFH_LINT_SOFT) } catch { $soft = 0 }
  if ($soft -ne 0) {
    Write-Host "CFH lint: SOFT MODE enabled (CFH_LINT_SOFT=$soft); not failing CI." -ForegroundColor Yellow
    $result.hard_fail = $false
  }
}

($result | ConvertTo-Json -Depth 6) | Set-Content $summary -Encoding UTF8
Write-Host "CFH lint summary -> $summary" -ForegroundColor Green
if($result.hard_fail){ exit 2 } else { exit 0 }
