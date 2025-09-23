param(
  [string]$AIO        = "C:\c\ai-orchestrator",
  [string]$Frontend   = "C:\Backup_Projects\CFH\frontend",
  [string]$ListsDir   = ".\lists",
  [string[]]$ExtraListDirs = @("C:\CFH"),    # will scan these dirs for *.md/*.txt (recursively)
  [switch]$RecurseListDirs = $true,

  # Optional: also scan these roots directly for real source files
  [switch]$ScanRootsEnable = $true,
  [string[]]$ScanRoots = @("C:\CFH\frontend","C:\CFH\backend"),

  # Preference when choosing among duplicates
  [string]$PreferRoot = "C:\Backup_Projects\CFH\frontend"
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

function Get-SHA1([string]$p){ try { (Get-FileHash -Path $p -Algorithm SHA1).Hash.ToLower() } catch { "" } }

# Reject junky filenames (hashy names, GUIDs, >2 digits, starts with $, etc.)
function Test-HumanishFile([string]$path){
  try {
    $full = [string]$path
    $nameNoExt = [IO.Path]::GetFileNameWithoutExtension($full)

    $badFragments = @('\allprojectfilename\', '\$Recycle.Bin\', '\Windows\', 'Program Files',
                      '\node_modules\', '\dist\', '\build\', '\coverage\', '\.git\')
    foreach($frag in $badFragments){ if($full -like "*$frag*"){ return $false } }

    if($nameNoExt -notmatch '[A-Za-z]'){ return $false }                     # must have a letter
    if($nameNoExt.StartsWith('$')){ return $false }                          # $Ixxxxx etc
    if(([regex]::Matches($nameNoExt,'\d').Count) -gt 2){ return $false }     # too many digits
    if($nameNoExt -match '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'){ return $false } # GUID
    if($nameNoExt -match '^[A-Z0-9]{7,}$'){ return $false }                  # long all-caps blob
    if(([regex]::Matches($nameNoExt,'[A-Za-z]').Count) -lt 2){ return $false }
    return $true
  } catch { return $false }
}

# ---------- 1) Gather list files (.\lists + extra dirs) ----------
$mdFiles = @()
# local lists folder (non-recursive)
$mdFiles += Get-ChildItem -File (Join-Path $ListsDir '*.md')  -ErrorAction SilentlyContinue
$mdFiles += Get-ChildItem -File (Join-Path $ListsDir '*.txt') -ErrorAction SilentlyContinue

# extra list dirs (recursive if requested)
foreach($dir in $ExtraListDirs){
  if(-not $dir){ continue }
  if(Test-Path $dir){
    if($RecurseListDirs){
      $mdFiles += Get-ChildItem -File (Join-Path $dir '*.md')  -Recurse -ErrorAction SilentlyContinue
      $mdFiles += Get-ChildItem -File (Join-Path $dir '*.txt') -Recurse -ErrorAction SilentlyContinue
    } else {
      $mdFiles += Get-ChildItem -File (Join-Path $dir '*.md')  -ErrorAction SilentlyContinue
      $mdFiles += Get-ChildItem -File (Join-Path $dir '*.txt') -ErrorAction SilentlyContinue
    }
  }
}
# unique by FullName
if($mdFiles){ $mdFiles = $mdFiles | Sort-Object FullName -Unique } else { $mdFiles = @() }

# ---------- 2) Extract absolute code paths from the .md/.txt ----------
$pat = '(?i)(?:\b[A-Za-z]:\\|\\\\)[^\s\|\)\]]+?\.(?:js|jsx|ts|tsx)\b'
$pathsFromLists = New-Object System.Collections.Generic.List[string]
foreach($f in $mdFiles){
  $mi = Select-String -Path $f.FullName -Pattern $pat -AllMatches -ErrorAction SilentlyContinue
  if($mi){
    foreach($m in $mi){
      foreach($mm in $m.Matches){ $pathsFromLists.Add($mm.Value) }
    }
  }
}
$pathsFromLists = $pathsFromLists | Sort-Object -Unique

# ---------- 3) (Optional) Directly scan roots for real files ----------
$pathsFromScan = @()
if($ScanRootsEnable){
  foreach($root in $ScanRoots){
    if(-not (Test-Path $root)){ continue }
    $hits = Get-ChildItem -Path $root -Recurse -File -Include *.js,*.jsx,*.ts,*.tsx -ErrorAction SilentlyContinue |
            Where-Object {
              $_.FullName -notlike "*\node_modules\*" -and
              $_.FullName -notlike "*\dist\*" -and
              $_.FullName -notlike "*\build\*" -and
              $_.FullName -notlike "*\.git\*" -and
              $_.FullName -notlike "*\coverage\*"
            } | ForEach-Object FullName
    if($hits){ $pathsFromScan += $hits }
  }
  if($pathsFromScan){ $pathsFromScan = $pathsFromScan | Sort-Object -Unique } else { $pathsFromScan = @() }
}

# ---------- 4) Merge sources ----------
$allPathsRaw = @()
$allPathsRaw += $pathsFromLists
$allPathsRaw += $pathsFromScan
$allPathsRaw = ($allPathsRaw | Sort-Object -Unique)

# keep only those that exist now
$existingAll = $allPathsRaw | Where-Object { Test-Path $_ }

# prefer main root if it has JS/JSX; otherwise use everything
$inPreferred = $existingAll | Where-Object { $_.ToLower().StartsWith(($PreferRoot + '\').ToLower()) }
$usePreferred = (($inPreferred | Where-Object { $_ -match '\.(js|jsx)$' }).Count -gt 0)
$existing = if($usePreferred){ $inPreferred } else { $existingAll }

# ---------- 5) Fast de-dup (Name+Size; hash only inside collisions) ----------
$records = foreach($p in $existing){
  $fi = Get-Item $p -ErrorAction SilentlyContinue
  if($fi){ [PSCustomObject]@{ Name=$fi.Name; Size=$fi.Length; Item=$fi } }
}
$groups = $records | Group-Object { '{0}|{1}' -f $_.Name,$_.Size }

$dedup = New-Object System.Collections.Generic.List[System.IO.FileInfo]
foreach($g in $groups){
  if($g.Count -eq 1){ $dedup.Add($g.Group[0].Item) | Out-Null }
  else{
    $seen = @{}
    foreach($it in $g.Group){
      $h = Get-SHA1 $it.Item.FullName
      $k = '{0}|{1}' -f $it.Name,$h
      if(-not $seen[$k]){ $seen[$k]=$true; $dedup.Add($it.Item) | Out-Null }
    }
  }
}

# ---------- 6) Conflict report: same filename, different sizes ----------
$confLines = @("# Same-name different-size (from lists+roots scan)","","Preferred root: $PreferRoot","")
$byName = $dedup | Group-Object Name
foreach($bn in $byName){
  $sizes = ($bn.Group | ForEach-Object Length | Sort-Object -Unique)
  if($sizes.Count -gt 1){
    $confLines += "## $($bn.Name)"
    foreach($f in ($bn.Group | Sort-Object Length, FullName)){
      $confLines += "- $($f.Length) bytes - $($f.FullName)"
    }
    $confLines += ""
  }
}

# ---------- 7) Pins: filename -> preferred absolute path ----------
$pins = @{}
$pinFile = (Join-Path (Join-Path $AIO 'reports') 'conflict_pins.csv')
if(Test-Path $pinFile){
  foreach($line in (Get-Content $pinFile | Where-Object { $_ -and $_ -notmatch '^\s*#' })){
    $parts = $line.Split(',',2)
    if($parts.Count -eq 2){ $pins[$parts[0].Trim()] = $parts[1].Trim() }
  }
}

# ---------- 8) Already-generated stems (recursive) ----------
$genStems = Get-ChildItem (Join-Path $AIO 'artifacts\generated') -Recurse -File -Include *.ts,*.tsx -ErrorAction SilentlyContinue |
  ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.Name) } |
  Sort-Object -Unique

# ---------- 9) Build candidates (JS/JSX not yet generated), humanish filter ----------
$jsItems  = $dedup | Where-Object { $_.Extension -in '.js','.jsx' }
$jsStems  = $jsItems | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.Name) } | Sort-Object -Unique
$needStems = $jsStems | Where-Object { $_ -notin $genStems }

$candidates = New-Object System.Collections.Generic.List[string]
foreach($stem in $needStems){
  $byStem = $jsItems | Where-Object { [IO.Path]::GetFileNameWithoutExtension($_.Name) -eq $stem }

  # (a) pin wins (if it matches one copy)
  $fname = ($byStem | Select-Object -First 1).Name
  if($fname -and $pins.ContainsKey($fname)){
    $pinned = $byStem | Where-Object { $_.FullName -ieq $pins[$fname] } | Select-Object -First 1
    if($pinned){ if(Test-HumanishFile $pinned.FullName){ $candidates.Add($pinned.FullName) | Out-Null }; continue }
  }

  # (b) prefer main root; else first
  $pick = $byStem | Where-Object { $_.FullName -like ($PreferRoot + '\*') } | Select-Object -First 1
  if(-not $pick){ $pick = $byStem | Select-Object -First 1 }
  if($pick -and (Test-HumanishFile $pick.FullName)){ $candidates.Add($pick.FullName) | Out-Null }
}

# ---------- 10) Write outputs ----------
$reports = Join-Path $AIO 'reports'; New-Item -ItemType Directory -Force -Path $reports | Out-Null
$rawOut   = Join-Path $reports 'conversion_candidates_from_lists_and_roots.txt'
$feedOut  = Join-Path $reports 'conversion_candidates.txt'   # pipeline feed file
$confOut  = Join-Path $reports 'same_name_different_size_from_lists_and_roots.md'
$summary  = Join-Path $reports 'lists_and_roots_summary.txt'

$existingAll | Set-Content -Path $rawOut -Encoding UTF8
$candidates  | Set-Content -Path $feedOut -Encoding UTF8
$confLines -join "`r`n" | Set-Content -Path $confOut -Encoding UTF8

@(
  "List files parsed (.\lists + extras): $($mdFiles.Count)",
  "Paths from lists                    : $($pathsFromLists.Count)",
  "Paths from direct scans             : $($pathsFromScan.Count)",
  "Total unique paths (exist now)      : $($existingAll.Count)",
  "Using preferred root                : $usePreferred",
  "Dedup unique files (Name+Size+SHA1) : $($dedup.Count)",
  "JS/JSX in dedup                     : $(( $jsItems ).Count)",
  "Generated stems found               : $($genStems.Count)",
  "JS/JSX stems                        : $($jsStems.Count)",
  "Stems needing conversion            : $($needStems.Count)",
  "Candidates after humanish filter    : $((Get-Content $feedOut | ? {$_}).Count)"
) | Set-Content -Path $summary -Encoding UTF8

Write-Host "Built from lists + roots:"
Write-Host "  Raw      : $rawOut"
Write-Host "  Feed     : $feedOut"
Write-Host "  Conflicts: $confOut"
Write-Host "  Summary  : $summary"
