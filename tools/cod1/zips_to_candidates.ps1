param(
  [string]   $AIO       = (Get-Location).Path,
  [string[]] $ZipRoots  = @(),
  [string]   $StageDir  = ".\artifacts\zip_stage",
  [string]   $FeedPath  = ".\reports\conversion_candidates.txt",
  [switch]   $CleanStage
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Line($msg) { Write-Host $msg }

# Resolve base dir
$AIO = (Resolve-Path $AIO).Path

# Prepare StageDir (do NOT Resolve-Path before it exists)
$StageDirAbs = (Join-Path $AIO $StageDir)
if ($CleanStage -and (Test-Path $StageDirAbs)) {
  Remove-Item -Recurse -Force -LiteralPath $StageDirAbs
}
New-Item -ItemType Directory -Force -Path $StageDirAbs | Out-Null

# Prepare feed file (create if missing)
$FeedAbs = (Join-Path $AIO $FeedPath)
$feedDir = Split-Path $FeedAbs
New-Item -ItemType Directory -Force -Path $feedDir | Out-Null
if (-not (Test-Path $FeedAbs)) {
  New-Item -ItemType File -Force -Path $FeedAbs | Out-Null
}

# Gather zip files
$zips = @()
foreach ($zr in $ZipRoots) {
  if (-not $zr) { continue }
  if (-not (Test-Path $zr)) { continue }
  $zips += Get-ChildItem -Path $zr -Recurse -File -Include *.zip -ErrorAction SilentlyContinue
}

if (-not $zips -or $zips.Count -eq 0) {
  Write-Line "No zip files found under: $($ZipRoots -join ', ')"
  Write-Line ("stage dir         : {0}" -f $StageDirAbs)
  Write-Line ("feed path         : {0}" -f $FeedAbs)
  return
}

$extractedRoots = New-Object System.Collections.Generic.List[string]
$jsLike = New-Object System.Collections.Generic.List[string]

foreach ($zip in $zips) {
  try {
    $baseName = [IO.Path]::GetFileNameWithoutExtension($zip.Name)
    $safe     = ($baseName -replace '[^A-Za-z0-9._-]','_')
    $dest     = Join-Path $StageDirAbs $safe
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    Expand-Archive -Path $zip.FullName -DestinationPath $dest -Force
    $extractedRoots.Add($dest)

    $found = Get-ChildItem -Path $dest -Recurse -File -ErrorAction SilentlyContinue |
             Where-Object { $_.Extension -in '.js','.jsx','.ts','.tsx' } |
             Select-Object -ExpandProperty FullName
    foreach ($p in $found) { $jsLike.Add($p) }
  } catch {
    Write-Line "WARN: failed to extract '$($zip.FullName)': $($_.Exception.Message)"
  }
}

# Dedup by (Name|Size|SHA1)
function Get-SHA1([string]$p) {
  try { (Get-FileHash -Algorithm SHA1 -Path $p).Hash.ToLower() } catch { "" }
}

$seen   = @{}
$unique = New-Object System.Collections.Generic.List[string]
foreach ($p in $jsLike) {
  try {
    $fi = Get-Item $p -ErrorAction Stop
    $k  = '{0}|{1}|{2}' -f $fi.Name, $fi.Length, (Get-SHA1 $fi.FullName)
    if (-not $seen.ContainsKey($k)) {
      $seen[$k] = $true
      $unique.Add($fi.FullName)
    }
  } catch { }
}

# Merge with existing feed
$current = Get-Content -Path $FeedAbs -ErrorAction SilentlyContinue | Where-Object { $_ }
$all     = @($current + $unique) | Sort-Object -Unique
$all | Set-Content -Path $FeedAbs -Encoding UTF8

Write-Line "== zips_to_candidates summary =="
Write-Line ("zip roots         : {0}" -f ($ZipRoots -join ', '))
Write-Line ("zips discovered   : {0}" -f $zips.Count)
Write-Line ("stage dir         : {0}" -f $StageDirAbs)
Write-Line ("files found       : {0}" -f $jsLike.Count)
Write-Line ("unique (by N|S|H) : {0}" -f $unique.Count)
Write-Line ("feed path         : {0}" -f $FeedAbs)
Write-Line ("feed count (now)  : {0}" -f ((Get-Content $FeedAbs | ? { $_ }).Count))
