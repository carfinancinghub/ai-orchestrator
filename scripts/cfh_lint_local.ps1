<#  scripts\cfh_lint_local.ps1
    Local CFH lint (no GitHub calls): scans a given root (default C:\Backup_Projects\CFH\frontend),
    writes reports\cfh_lint_summary.json, and returns nonzero on hard violations.
#>
[CmdletBinding()]
param(
  [string]$Root = "C:\Backup_Projects\CFH\frontend"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName 'System.IO'

# Normalize paths
$rootPath  = [System.IO.Path]::GetFullPath($Root)
if (-not (Test-Path $rootPath)) { throw "Root not found: $rootPath" }

$reportDir = Join-Path $rootPath 'reports'
$summary   = Join-Path $reportDir 'cfh_lint_summary.json'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

# Exclusions (substring tokens, not regex)
$excludeTokens = @(
  '/node_modules/', '/dist/', '/build/', '/coverage/', '/.git/',
  '/zipped_batches/', '/conversion/', '/backend/',
  '/.tmp', '/.temp', '/.tmp_tests/', '/.cache', '/.output', '/.idea'
)

# File globs to include and test/dev files to ignore for hard rules
$includeExts = @('.ts', '.tsx')
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
  @{ name='Any';        rx='(?ms)\bany\b' },
  @{ name='TsIgnore';   rx='(?ms)@ts-ignore' }
)
$softPatterns = @(
  @{ name='TODO';       rx='(?ms)TODO|FIXME' },
  @{ name='LegacyJS';   rx='(?ms)\brequire\(' }
)

$violations   = New-Object System.Collections.Generic.List[object]
$observations = New-Object System.Collections.Generic.List[object]

foreach($full in $files){
  $rel = $full.Substring($rootPath.Length).TrimStart('\','/')
  $content = [System.IO.File]::ReadAllText($full)

  foreach($hp in $hardPatterns){
    if($content -match $hp.rx){
      # allow in testish files
      if (-not (IsTestish $rel)){
        $violations.Add([pscustomobject]@{ file=$rel; rule=$hp.name; rx=$hp.rx; type='hard' })
      }
    }
  }
  foreach($sp in $softPatterns){
    if($content -match $sp.rx){
      $observations.Add([pscustomobject]@{ file=$rel; rule=$sp.name; rx=$sp.rx; type='soft' })
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

# --- soft mode toggle via env var (0/1) ---
$soft = 0
try { $soft = [int]($env:CFH_LINT_SOFT) } catch { $soft = 0 }
if ($soft -ne 0) {
  Write-Host "CFH lint: SOFT MODE enabled (CFH_LINT_SOFT=$soft); not failing CI." -ForegroundColor Yellow
  $result.hard_fail = $false
}

($result | ConvertTo-Json -Depth 6) | Set-Content $summary -Encoding UTF8
Write-Host "CFH lint summary -> $summary" -ForegroundColor Green
if($result.hard_fail){ exit 2 } else { exit 0 }