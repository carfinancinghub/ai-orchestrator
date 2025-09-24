param(
  [string]$AIO       = "C:\c\ai-orchestrator",
  [string]$Frontend  = "C:\Backup_Projects\CFH\frontend",
  [string]$ListsDir  = ".\lists",
  [int]$TopRoots     = 10,
  [switch]$OnlyUnderFrontend  # keep only paths that live under $Frontend
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

# --- helpers ---
function Get-Paths-FromListFile([string]$path){
  $paths = New-Object System.Collections.Generic.List[string]
  $inCode = $false
  foreach($line in (Get-Content -LiteralPath $path)){
    $t = $line.Trim()
    if($t -like '```*'){ $inCode = -not $inCode; continue }
    if(-not $inCode){
      if($t -eq "" -or $t -like '<!*' -or $t -like '#*' -or $t -like '_*_' -or $t -like '*|*|*'){ continue }
      $t = $t -replace '^[\-\*\d\.\)\s]+',''
    }
    if($t -match '^[A-Za-z]:\\' -or $t -match '^(\/|\\)'){
      $paths.Add($t)
    }
  }
  return $paths
}

function Get-RootKey([string]$p){
  try{
    $full = [IO.Path]::GetFullPath($p)
    $drive = [IO.Path]::GetPathRoot($full)    # e.g. "C:\"
    $rest  = $full.Substring($drive.Length).TrimStart('\','/')
    if($rest -eq ""){ return $drive.TrimEnd('\') }
    $first = ($rest -split '[\\/]',2)[0]
    return (Join-Path $drive $first).TrimEnd('\')
  } catch { return $p }
}

function Is-Converted([string]$srcPath){
  $stem = [IO.Path]::GetFileNameWithoutExtension($srcPath)
  $ts   = Join-Path "artifacts\generated" ($stem + ".ts")
  $tsx  = Join-Path "artifacts\generated" ($stem + ".tsx")
  (Test-Path $ts) -or (Test-Path $tsx)
}

# --- collect list files ---
$listsDirAbs = (Resolve-Path -LiteralPath $ListsDir).Path
$listFiles = @()
$listFiles += Get-ChildItem -LiteralPath $listsDirAbs -File -Filter *.md  -ErrorAction SilentlyContinue
$listFiles += Get-ChildItem -LiteralPath $listsDirAbs -File -Filter *.txt -ErrorAction SilentlyContinue
if(-not $listFiles -or $listFiles.Count -eq 0){ throw "No .md/.txt files found in $listsDirAbs" }

# --- parse lists into absolute paths ---
$allPaths = New-Object System.Collections.Generic.List[string]
foreach($lf in $listFiles){
  $paths = Get-Paths-FromListFile $lf.FullName
  foreach($p in $paths){ $allPaths.Add($p) }
}

# optional scope under Frontend
if($OnlyUnderFrontend){
  $front = (Resolve-Path -LiteralPath $Frontend).Path.ToLower()
  $allPaths = [System.Collections.Generic.List[string]]($allPaths | Where-Object { $_.ToLower().StartsWith($front) })
}

# --- compute root frequencies ---
$roots = @{}   # key => count
$rootSamples = @{} # key => sample path
foreach($p in $allPaths){
  $k = Get-RootKey $p
  if(-not $roots.ContainsKey($k)){ $roots[$k] = 0; $rootSamples[$k] = $p }
  $roots[$k]++
}

$reports = Join-Path $AIO "reports"
$debug   = Join-Path $reports "debug"
New-Item -ItemType Directory -Force -Path $reports,$debug | Out-Null

$rootsMd   = Join-Path $reports ("lists_roots_summary.md")
$rootsJson = Join-Path $reports ("lists_roots_summary.json")

$rootRows = $roots.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object {
  [PSCustomObject]@{ root = $_.Key; count = $_.Value; sample = $rootSamples[$_.Key] }
}
$rootRows | ConvertTo-Json -Depth 4 | Set-Content -Path $rootsJson -Encoding UTF8

$lines = @("# Roots discovered from uploaded lists","","| root | count | sample |","|------|-------:|--------|")
foreach($r in ($rootRows | Select-Object -First $TopRoots)){
  $lines += ("| {0} | {1} | {2} |" -f $r.root, $r.count, $r.sample)
}
$lines -join "`r`n" | Set-Content -Path $rootsMd -Encoding UTF8

# --- choose main root (highest count) ---
if($rootRows.Count -eq 0){ throw "No usable paths parsed from lists." }
$mainRoot = ($rootRows | Sort-Object count -Descending | Select-Object -First 1).root

# --- scan main root for source files ---
$excludeRe = '\\(node_modules|dist|build|out|coverage|\.git|\.vscode|Windows|Program Files|ProgramData|AppData|Drivers)\\'
$scanned = Get-ChildItem -LiteralPath $mainRoot -Recurse -File -Include *.js,*.jsx,*.ts,*.tsx -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch $excludeRe }

# --- dedup by Name+Size, prepare candidates (js/jsx not converted) ---
$seenNameSize = @{}
$dedup = New-Object System.Collections.Generic.List[object]
foreach($f in $scanned){
  $key = "$($f.Name)|$($f.Length)"
  if(-not $seenNameSize.ContainsKey($key)){
    $seenNameSize[$key] = $true
    $dedup.Add($f)
  }
}

$candidateList = New-Object System.Collections.Generic.List[string]
$conflictsByName = @{}

foreach($f in $dedup){
  if($f.Extension -in @(".js",".jsx")){
    if(-not (Is-Converted $f.FullName)){
      $candidateList.Add($f.FullName)
    }
  }
  # track conflicts
  if(-not $conflictsByName.ContainsKey($f.Name)){ $conflictsByName[$f.Name] = New-Object System.Collections.Generic.List[object] }
  $conflictsByName[$f.Name].Add([PSCustomObject]@{ path=$f.FullName; size=$f.Length })
}

# --- outputs ---
$cands     = Join-Path $reports "conversion_candidates.txt"
$conflicts = Join-Path $reports "same_name_different_size_mainroot.md"
$invCsv    = Join-Path $reports ("scan_inventory_{0}.csv" -f (Get-Date -Format yyyyMMdd_HHmmss))
$summary   = Join-Path $reports "scan_summary.txt"

# write candidates
$candidateList | Set-Content -Path $cands -Encoding UTF8

# conflicts md
$lines = @("# Same-name different-size under main root","","Main root: $mainRoot","")
foreach($name in ($conflictsByName.Keys | Sort-Object)){
  $sizes = ($conflictsByName[$name] | Select-Object -ExpandProperty size | Sort-Object -Unique)
  if($sizes.Count -gt 1){
    $lines += "## $name"
    foreach($e in ($conflictsByName[$name] | Sort-Object size, path)){
      $lines += ("- {0} bytes - {1}" -f $e.size, $e.path)
    }
    $lines += ""
  }
}
$lines -join "`r`n" | Set-Content -Path $conflicts -Encoding UTF8

# inventory csv (a few columns)
$dedup |
  Select-Object Name, Extension, Length, FullName |
  Export-Csv -Path $invCsv -NoTypeInformation -Encoding UTF8

# summary
@(
  "Main root: $mainRoot"
  "Roots summary: $rootsMd"
  "Found files (scanned): $($scanned.Count)"
  "Deduped by name+size: $($dedup.Count)"
  "JS/JSX candidates (not yet converted): $($candidateList.Count)"
  "Candidates file: $cands"
  "Conflicts report: $conflicts"
  "Inventory CSV: $invCsv"
) | Set-Content -Path $summary -Encoding UTF8

Write-Host "Scan complete."
Write-Host "  Main root     : $mainRoot"
Write-Host "  Roots MD      : $rootsMd"
Write-Host "  Candidates    : $cands"
Write-Host "  Conflicts MD  : $conflicts"
Write-Host "  Inventory CSV : $invCsv"
Write-Host "  Summary       : $summary"
