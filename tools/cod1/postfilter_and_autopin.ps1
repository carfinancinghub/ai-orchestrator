param(
  [string]$Feed      = 'reports\conversion_candidates.txt',
  [string]$Conflicts = 'reports\same_name_different_size_from_lists_and_roots.md',

  # Preferred roots in priority order
  [string[]]$PreferRoots = @(
    'C:\Backup_Projects\CFH\frontend',
    'C:\CFH\frontend',
    'C:\CFH\backend'
  ),

  # Stage dir for ZIP-extracted files
  [string]$StageDir = '.\artifacts\zip_stage',

  # Where to write pins
  [string]$PinsCsv = 'reports\conflict_pins.csv',

  # Keep staged ZIP entries
  [switch]$IncludeZippedBatches,

  # Keep tests/specs too
  [switch]$KeepTests,

  # Allow recovered/archival dirs (e.g. "allprojectfilename", "Manualy_Editing_Files")
  [switch]$AllowRecovered,

  # Relax human-ish rule (allow up to 4 digits)
  [switch]$RelaxHumanish
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoPath([string]$p) {
  if (Test-Path $p) { return (Resolve-Path $p).Path }
  $root = (Resolve-Path '.').Path
  $abs = Join-Path $root $p
  return $abs
}

$Feed      = Resolve-RepoPath $Feed
$Conflicts = Resolve-RepoPath $Conflicts
$PinsCsv   = Resolve-RepoPath $PinsCsv
$StageDir  = Resolve-RepoPath $StageDir

if (-not (Test-Path $Feed)) { throw "Feed not found: $Feed" }

function Test-HumanishFile([string]$path) {
  try {
    $leaf = Split-Path $path -Leaf
    $stem = [IO.Path]::GetFileNameWithoutExtension($leaf)
    if ($leaf.StartsWith('$')) { return $false }
    if ($stem -notmatch '[A-Za-z]') { return $false }
    $limit = ($(if ($RelaxHumanish) { 4 } else { 2 }))
    if ([regex]::Matches($stem, '\d').Count -gt $limit) { return $false }
    return $true
  } catch { return $false }
}

function In-AnyRoot([string]$p, [string[]]$roots) {
  foreach ($r in $roots) {
    if ([string]::IsNullOrWhiteSpace($r)) { continue }
    $r2 = $r.TrimEnd('\')
    if ($p -like ($r2 + '\*')) { return $true }
  }
  return $false
}

$raw = Get-Content $Feed | Where-Object { $_ }
$before = $raw.Count

# drop dirs (can be relaxed with flags)
$dropDirPatterns = @(
  '\\\$Recycle\.Bin\\',
  '\\AppData\\',
  '\\Cypress\\Cache\\',
  '\\node_modules\\',
  '\\dist\\',
  '\\build\\',
  '\\out\\'
)
if (-not $AllowRecovered) {
  $dropDirPatterns += '\\allprojectfilename\\'
  $dropDirPatterns += '\\Manualy_Editing_Files\\'
}
if (-not $IncludeZippedBatches) { $dropDirPatterns += '\\zipped_batches\\' }

# ---------- first pass: preferred roots (plus StageDir if allowed) ----------
$filteredPref = foreach ($p in $raw) {
  $ok = $true

  $keepRoots = $PreferRoots
  if ($IncludeZippedBatches -and (Test-Path $StageDir)) { $keepRoots = $PreferRoots + $StageDir }

  if (-not (In-AnyRoot $p $keepRoots)) { $ok = $false }

  if (-not $KeepTests) {
    if ($ok -and ($p -match '\\(tests?|__tests__|specs?)\\' -or $p -match '\.(test|spec)\.(jsx?|tsx?)$')) { $ok = $false }
  }

  if ($ok) {
    foreach ($re in $dropDirPatterns) { if ($p -match $re) { $ok = $false; break } }
  }

  if ($ok -and -not (Test-HumanishFile $p)) { $ok = $false }

  if ($ok) { $p }
}

# ---------- fallback: allow any root (still filtered) if first pass is too small ----------
$filtered = $filteredPref
if ($filtered.Count -lt 25) {
  $filtered = foreach ($p in $raw) {
    $ok = $true

    if (-not $IncludeZippedBatches -and $p -match '\\zipped_batches\\') { $ok = $false }

    if (-not $KeepTests) {
      if ($ok -and ($p -match '\\(tests?|__tests__|specs?)\\' -or $p -match '\.(test|spec)\.(jsx?|tsx?)$')) { $ok = $false }
    }

    if ($ok) {
      foreach ($re in $dropDirPatterns) { if ($p -match $re) { $ok = $false; break } }
    }

    if ($ok -and -not (Test-HumanishFile $p)) { $ok = $false }

    if ($ok) { $p }
  }
}

$after = $filtered.Count
$filtered | Set-Content -Path $Feed -Encoding UTF8

# ----- AUTO-PIN from conflicts -----
New-Item -ItemType File -Force -Path $PinsCsv | Out-Null
Add-Content $PinsCsv "# filename,absolute-path (auto-generated)"

if (Test-Path $Conflicts) {
  $curName = $null
  $best = $null

  foreach ($line in Get-Content $Conflicts) {
    if ($line -match '^\#\#\s+(.+)$') {
      if ($curName -and $best) { Add-Content $PinsCsv ("{0},{1}" -f $curName, $best.path) }
      $curName = $matches[1].Trim()
      $best = $null
      continue
    }

    if ($line -match '^\-\s+\d+\s+bytes\s+\-\s+(.+)$') {
      $cand = $matches[1].Trim()
      $score = 0
      $rootScore = 0
      for ($i=0; $i -lt $PreferRoots.Count; $i++) {
        if ($cand -like ($PreferRoots[$i].TrimEnd('\') + '\*')) {
          $rootScore = 100 - (10 * $i); break
        }
      }
      if ($IncludeZippedBatches -and (Test-Path $StageDir)) {
        if ($cand -like ($StageDir.TrimEnd('\') + '\*')) { $rootScore = [Math]::Max($rootScore, 60) }
      }

      $len = 0; $age = 0
      try {
        $fi = Get-Item $cand -EA Stop
        $len = [int64]$fi.Length
        $age = [int]((Get-Date) - $fi.LastWriteTime).TotalHours
      } catch {}
      $timeBonus = [Math]::Max(0, 50 - [Math]::Min($age, 50))
      $sizeBonus = [int][Math]::Min(($len / 2048), 50)
      $score = $rootScore + $timeBonus + $sizeBonus
      if (-not $best -or $score -gt $best.score) { $best = @{ path = $cand; score = $score } }
    }
  }
  if ($curName -and $best) { Add-Content $PinsCsv ("{0},{1}" -f $curName, $best.path) }
}

Write-Host ""
Write-Host "== postfilter_and_autopin summary =="
Write-Host ("feed before : {0}" -f $before)
Write-Host ("feed after  : {0}" -f $after)
Write-Host ("pins file   : {0}" -f $PinsCsv)
