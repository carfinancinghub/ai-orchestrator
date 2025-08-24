<# 
  File: scripts/ref-governor.ps1
  Purpose: Enforce clean, capped reference lists (<= MaxPerSection) per extension, remove invalid/system paths,
           detect duplicate basenames, copy canonical files to a clean stash, and emit sanitized lists/overflow + reports.
  Usage:
    ./scripts/ref-governor.ps1 -Root "C:\Backup_Projects\CFH" -OutDir "C:\CFH\TruthSource" -MaxPerSection 2000 [-UseHash]
#>

param(
  [Parameter(Mandatory=$true)][string]$Root,
  [string]$OutDir = "C:\CFH\TruthSource",
  [int]$MaxPerSection = 2000,
  [string[]]$Extensions = @("js","jsx","ts","tsx"),
  [switch]$UseHash
)

$ErrorActionPreference = 'Stop'
function Stamp { param([string]$m) Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) }

function Is-ExcludedPath {
  param([string]$Path)
  $p = $Path.ToLowerInvariant()
  if ($p -match '\\windows(\\|$)') { return $true }
  if ($p -match '\\program files( \(x86\))?(\\|$)') { return $true }
  if ($p -match '\\programdata(\\|$)') { return $true }
  if ($p -match '\\users\\[^\\]+\\appdata(\\|$)') { return $true }
  if ($p -match '\\\$recycle\.bin(\\|$)') { return $true }
  if ($p -match 'system volume information') { return $true }
  if ($p -match '\\temp(\\|$)') { return $true }
  if ($p -match '\\node_modules(\\|$)') { return $true }
  if ($p -match '\\\.git(\\|$)') { return $true }
  if ($p -match '\\dist(\\|$)') { return $true }
  if ($p -match '\\build(\\|$)') { return $true }
  if ($p -match '\\coverage(\\|$)') { return $true }
  if ($p -match '\\logs?(\\|$)') { return $true }
  if ($p -match '\.log$') { return $true }
  if (-not ($p -like ($Root.ToLowerInvariant() + '\*'))) { return $true }
  return $false
}

function Get-CandidateFiles {
  param([string]$Ext)
  Stamp ("Scanning for *.{0} ..." -f $Ext)
  $glob = "*." + $Ext
  Get-ChildItem -Path $Root -Recurse -File -Filter $glob -ErrorAction SilentlyContinue |
    Where-Object { -not (Is-ExcludedPath $_.FullName) }
}

function Get-FileHashHex {
  param([string]$Path)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $fs = [System.IO.File]::OpenRead($Path)
  try { (-join ($sha.ComputeHash($fs) | ForEach-Object { $_.ToString("x2") })) }
  finally { $fs.Dispose(); $sha.Dispose() }
}

function Choose-Canonical {
  param([System.IO.FileInfo[]]$Files, [switch]$UseHash)
  if ($UseHash) {
    try {
      $groups = $Files | Group-Object { Get-FileHashHex $_.FullName }
      $best = $groups |
        Sort-Object @{Expression={ ($_.Group | Measure-Object Length -Sum).Sum }} -Descending |
        ForEach-Object {
          $_.Group | Sort-Object @{Expression='Length';Descending=$true}, @{Expression='LastWriteTime';Descending=$true} | Select-Object -First 1
        } |
        Select-Object -First 1
      if ($best) { return $best }
    } catch { }
  }
  return ($Files | Sort-Object @{Expression='Length';Descending=$true}, @{Expression='LastWriteTime';Descending=$true} | Select-Object -First 1)
}

# Outputs
$refDir       = Join-Path $OutDir "refs"
$cleanDir     = Join-Path $OutDir "clean"
$artifactsDir = Join-Path $OutDir "artifacts\ref"
$sanDir       = Join-Path $artifactsDir "sanitized"
$dubReport    = Join-Path $artifactsDir "duplicates_report.csv"
$manifestJl   = Join-Path $artifactsDir "manifest.jsonl"
$exclList     = Join-Path $artifactsDir "exclusions_removed.md"
$dirs = @($refDir,$cleanDir,$artifactsDir,$sanDir)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
"" | Set-Content -Path $dubReport -Encoding ASCII
"basename,count,chosen_path,chosen_size,chosen_mtime,group_paths" | Add-Content -Path $dubReport -Encoding ASCII
"" | Set-Content -Path $manifestJl -Encoding ASCII
"# Exclusions removed" | Set-Content -Path $exclList -Encoding ASCII

$allSanitized = @{}
foreach ($ext in $Extensions) {
  $files = Get-CandidateFiles -Ext $ext
  $byName = $files | Group-Object { $_.BaseName.ToLowerInvariant() }

  $canonicals = New-Object System.Collections.Generic.List[string]
  foreach ($g in $byName) {
    $items = @($g.Group)
    if ($items.Count -eq 0) { continue }
    if ($items.Count -eq 1) {
      $chosen = $items[0]
      $canonicals.Add($chosen.FullName) | Out-Null
      (@{ src=$chosen.FullName; canonical=$chosen.FullName; copied_to=$null } | ConvertTo-Json -Compress) | Add-Content -Path $manifestJl -Encoding ASCII
      continue
    }
    $chosen = Choose-Canonical -Files $items -UseHash:$UseHash
    $groupPaths = ($items | ForEach-Object { $_.FullName }) -join ";"
    $line = '"{0}",{1},"{2}",{3},"{4}","{5}"' -f $g.Name, $items.Count, $chosen.FullName.Replace('"','""'), $chosen.Length, $chosen.LastWriteTime.ToString("s"), $groupPaths.Replace('"','""')
    Add-Content -Path $dubReport -Value $line -Encoding ASCII
    $canonicals.Add($chosen.FullName) | Out-Null
    (@{ src=$chosen.FullName; canonical=$chosen.FullName; copied_to=$null } | ConvertTo-Json -Compress) | Add-Content -Path $manifestJl -Encoding ASCII
  }

  $destExtDir = Join-Path $cleanDir $ext
  New-Item -ItemType Directory -Force -Path $destExtDir | Out-Null
  $nameCounts = @{}
  $copied = New-Object System.Collections.Generic.List[string]
  foreach ($src in $canonicals) {
    if (-not (Test-Path $src)) { continue }
    $bn = [System.IO.Path]::GetFileName($src)
    $dst = Join-Path $destExtDir $bn
    if (Test-Path $dst) {
      if (-not $nameCounts.ContainsKey($bn)) { $nameCounts[$bn] = 1 } else { $nameCounts[$bn]++ }
      $stem = [System.IO.Path]::GetFileNameWithoutExtension($bn)
      $extn = [System.IO.Path]::GetExtension($bn)
      $dst  = Join-Path $destExtDir ("{0}_{1}{2}" -f $stem, $nameCounts[$bn], $extn)
    }
    Copy-Item -Path $src -Destination $dst -Force
    $copied.Add($src) | Out-Null
    (@{ src=$src; canonical=$src; copied_to=$dst } | ConvertTo-Json -Compress) | Add-Content -Path $manifestJl -Encoding ASCII
  }

  $sanListPath = Join-Path $sanDir ("file_scan_results_{0}_sanitized.md" -f $ext)
  $ovfPath     = Join-Path $sanDir ("file_scan_results_{0}_overflow.md"   -f $ext)
  $sortedCanon = $canonicals | Sort-Object
  $canonStr    = $sortedCanon | Select-Object -First $MaxPerSection
  $overflow    = $sortedCanon | Select-Object -Skip  $MaxPerSection

  "# Sanitized {0} ({1} items, capped at {2})" -f $ext, $canonicals.Count, $MaxPerSection | Set-Content -Path $sanListPath -Encoding ASCII
  foreach ($p in $canonStr) { "- $p" | Add-Content -Path $sanListPath -Encoding ASCII }
  if ($overflow.Count -gt 0) {
    "# Overflow {0} ({1} items beyond cap)" -f $ext, $overflow.Count | Set-Content -Path $ovfPath -Encoding ASCII
    foreach ($p in $overflow) { "- $p" | Add-Content -Path $ovfPath -Encoding ASCII }
  }

  $allSanitized[$ext] = @{ sanitized=$sanListPath; overflow=($(if ($overflow.Count -gt 0) { $ovfPath } else { $null })); total=$canonicals.Count; copied=$copied.Count }
}

"# Paths under system/dev/log directories were excluded from all sections." | Add-Content -Path $exclList -Encoding ASCII

Stamp "Ref-governor summary:"
$allSanitized.GetEnumerator() | ForEach-Object {
  $ext = $_.Key; $info = $_.Value
  $ov = ($(if ($info.overflow) { " overflow=" + $info.overflow } else { "" }))
  Stamp ("{0}: total={1} copied={2} -> sanitized={3}{4}" -f $ext, $info.total, $info.copied, $info.sanitized, $ov)
}
Stamp ("Duplicates report: {0}" -f $dubReport)
Stamp ("Manifest jsonl   : {0}" -f $manifestJl)
Stamp ("Clean stash      : {0}" -f $cleanDir)
