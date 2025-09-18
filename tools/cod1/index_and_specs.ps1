param(
  [string]$AIO        = "C:\c\ai-orchestrator",
  [string]$Frontend   = "C:\Backup_Projects\CFH\frontend",
  [string]$Repo       = "carfinancinghub/cfh",
  [string]$BaseBranch = "main",
  [string]$HeadBranch = "ts-migration/rolling",
  [int]$TopN          = 500
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

# --- paths & outputs ---
$ts        = Get-Date -Format yyyyMMdd_HHmmss
$reports   = Join-Path $AIO "reports"
$debug     = Join-Path $reports "debug"
$specDir   = Join-Path $AIO "docs\specs"
$funcDir   = Join-Path $reports "functions"
New-Item -ItemType Directory -Force -Path $reports,$debug,$specDir,$funcDir | Out-Null

$invCsv    = Join-Path $reports ("inv_index_{0}.csv" -f $ts)
$invJson   = Join-Path $reports ("inv_index_{0}.json" -f $ts)
$dupsCsv   = Join-Path $reports ("duplicates_need_review_{0}.csv" -f $ts)
$candsList = Join-Path $reports "conversion_candidates.txt"
$md        = Join-Path $debug   ("inv_index_{0}.md" -f $ts)

function GhUrl($Repo,$Branch,$Rel){
  if([string]::IsNullOrWhiteSpace($Branch)) { "" } else { "https://github.com/$Repo/blob/$Branch/$Rel" }
}

function Get-SHA1([string]$Path) {
  try {
    $sha=[System.Security.Cryptography.SHA1]::Create()
    $fs=[System.IO.File]::OpenRead($Path)
    try { [BitConverter]::ToString($sha.ComputeHash($fs)).Replace('-','').ToLower() }
    finally { $fs.Dispose(); $sha.Dispose() }
  } catch { "" }
}

# Regex-based symbol finder (simple/top-level)
function Get-FunctionSymbols([string]$Path) {
  $out = New-Object System.Collections.Generic.List[object]
  try {
    $t = Get-Content -LiteralPath $Path -Raw -Encoding UTF8

    # export function foo(a,b)
    foreach($m in [regex]::Matches($t,'(?m)^\s*(export\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')) {
      $exp = [bool]$m.Groups[1].Value
      $name= $m.Groups[2].Value
      $sig = "(" + $m.Groups[3].Value + ")"
      $obj = [pscustomobject]@{ kind="function"; name=$name; exported=$exp; signature=$sig }
      $out.Add($obj) | Out-Null
    }

    # export const Foo = (props)=> or any const (...) => 
    foreach($m in [regex]::Matches($t,'(?m)^\s*(export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*\(([^)]*)\)\s*=>')) {
      $exp = [bool]$m.Groups[1].Value
      $name= $m.Groups[2].Value
      $sig = "(" + $m.Groups[3].Value + ") =>"
      $isComponent = $false
      if ($name -and $name.Substring(0,1) -cmatch '[A-Z]') { $isComponent = $true }
      $kind = if ($isComponent) { "component" } else { "arrow" }
      $obj = [pscustomobject]@{ kind=$kind; name=$name; exported=$exp; signature=$sig }
      $out.Add($obj) | Out-Null
    }

    # export default function Name(...) or anonymous default
    foreach($m in [regex]::Matches($t,'(?m)^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)?\s*\(([^)]*)\)')) {
      $nm = if($m.Groups[1].Success){ $m.Groups[1].Value } else { "<default>" }
      $sig= "(" + $m.Groups[2].Value + ")"
      $isComponent = $false
      if ($nm -ne "<default>" -and $nm.Substring(0,1) -cmatch '[A-Z]') { $isComponent = $true }
      $kind = if ($isComponent) { "component" } else { "function" }
      $obj = [pscustomobject]@{ kind=$kind; name=$nm; exported=$true; signature=$sig; isDefault=$true }
      $out.Add($obj) | Out-Null
    }
  } catch { }
  $out
}

# collect source files
$srcRoot = Join-Path $Frontend "src"
if (-not (Test-Path $srcRoot)) { throw "Missing $srcRoot" }

$srcFiles = Get-ChildItem $srcRoot -File -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -in @(".js",".jsx",".ts",".tsx") -and $_.FullName -notmatch '\\node_modules\\|\\dist\\' }

# group by filename for dedupe
$byName = @{}
foreach($f in $srcFiles){
  $k = $f.Name
  if(-not $byName.ContainsKey($k)){ $byName[$k] = New-Object System.Collections.Generic.List[System.IO.FileInfo] }
  $byName[$k].Add($f)
}

$rows = New-Object System.Collections.Generic.List[object]
$needReview = New-Object System.Collections.Generic.List[object]
$candidates = New-Object System.Collections.Generic.List[string]

foreach($pair in $byName.GetEnumerator()){
  $name = $pair.Key
  $files= $pair.Value

  # detect size-based dup groups
  $groupsBySize = $files | Group-Object Length
  $allPaths = ($files | ForEach-Object FullName) -join '; '

  # choose canonical: prefer under Frontend\src, then largest size, then newest
  $canonical = $files |
    Sort-Object @{Expression = { $_.FullName -like "$($Frontend)\src*" } ; Descending=$true },
                 @{Expression = { $_.Length }                          ; Descending=$true },
                 @{Expression = { $_.LastWriteTimeUtc }                 ; Descending=$true } |
    Select-Object -First 1

  $sha1 = Get-SHA1 $canonical.FullName
  $repoRel = ("src\" + $canonical.FullName.Substring($srcRoot.Length+1)) -replace '\\','/'
  $ghMain  = GhUrl $Repo $BaseBranch $repoRel
  $ghHead  = GhUrl $Repo $HeadBranch $repoRel

  # extract symbols once (canonical)
  $funcs = Get-FunctionSymbols $canonical.FullName
  $stem  = [IO.Path]::GetFileNameWithoutExtension($name)
  $funcPath = Join-Path $funcDir ($stem + ".json")
  $funcs | ConvertTo-Json -Depth 6 | Set-Content -Path $funcPath -Encoding UTF8

  # spec stub if missing
  $specPath = Join-Path $specDir ($stem + "_spec.md")
  if (-not (Test-Path $specPath)) {
    $specLines = @(
      "# Spec: $name",
      "",
      "**Canonical source**",
      "",
      "- Path: ``$($canonical.FullName)``",
      "- GH (base): $ghMain",
      "- GH (head): $ghHead",
      "",
      "## Public API (detected)",
      ""
    )
    foreach($fn in $funcs){
      $exp = if($fn.exported) { "exported" } else { "local" }
      $def = ""
      if ($fn.PSObject.Properties.Name -contains "isDefault" -and $fn.isDefault) { $def = " default" }
      $specLines += ("- **{0}{1}** `{2}` {3} - {4}" -f $fn.kind, $def, $fn.name, $fn.signature, $exp)
    }
    $specLines += @(
      "",
      "## Behavior Notes",
      "- [ ] Fill expected behaviors, side effects, contracts.",
      "",
      "## Test Checklist",
      "- [ ] Unit tests covering the public API above.",
      "- [ ] Integration smoke if applicable."
    )
    $specLines -join "`r`n" | Set-Content -Path $specPath -Encoding UTF8
  }

  # inventory row
  $rows.Add([pscustomobject]@{
    name       = $name
    ext        = $canonical.Extension
    size_bytes = $canonical.Length
    sha1       = $sha1
    canonical  = $canonical.FullName
    all_paths  = $allPaths
    repo_rel   = $repoRel
    gh_main    = $ghMain
    gh_head    = $ghHead
  }) | Out-Null

  # mark dup groups where same name has different sizes (needs review)
  if ($groupsBySize.Count -gt 1) {
    foreach($g in $groupsBySize){
      $needReview.Add([pscustomobject]@{
        name = $name
        size_bytes = [int64]$g.Name
        paths = (($g.Group | ForEach-Object FullName) -join '; ')
      }) | Out-Null
    }
  }

  # conversion candidates: canonical JS/JSX that do not already have generated TS/TSX
  if ($canonical.Extension -in @(".js",".jsx")) {
    $genTs  = Join-Path "artifacts\generated" ($stem + ".ts")
    $genTsx = Join-Path "artifacts\generated" ($stem + ".tsx")
    if (-not (Test-Path $genTs) -and -not (Test-Path $genTsx)) {
      $candidates.Add($canonical.FullName) | Out-Null
    }
  }
}

# write artifacts
$rows | Sort-Object name | Export-Csv -Path $invCsv -NoTypeInformation -Encoding UTF8
$rows | ConvertTo-Json -Depth 7 | Set-Content -Path $invJson -Encoding UTF8

if ($needReview.Count -gt 0) {
  $needReview | Sort-Object name,size_bytes |
    Export-Csv -Path $dupsCsv -NoTypeInformation -Encoding UTF8
}

# top-N conversion candidates list (largest first)
$candidates = $candidates | Sort-Object { (Get-Item $_).Length } -Descending
$candidates | Select-Object -First $TopN | Set-Content -Path $candsList -Encoding UTF8

# Markdown overview
$lines = @(
  "# Inventory Index $ts",
  "",
  "**Counts**",
  "- indexed files: $($rows.Count)",
  "- duplicate groups needing review: $($needReview.Count)",
  "- conversion candidates (JS/JSX): $((Get-Content $candsList | Measure-Object -Line).Lines)",
  "",
  "**How to use**",
  "- See conversion_candidates.txt for the next conversion batch.",
  "- Specs in docs\\specs are stubs generated from detected public API.",
  "- Function JSON in reports\\functions for parity checks."
)
$lines -join "`r`n" | Set-Content -Path $md -Encoding UTF8

Write-Host "Index built:"
Write-Host "  CSV  : $invCsv"
Write-Host "  JSON : $invJson"
if (Test-Path $dupsCsv) { Write-Host "  DUPS : $dupsCsv" }
Write-Host "  CANDS: $candsList"
Write-Host "  MD   : $md"
Write-Host "  SPECS: $specDir"
Write-Host "  FUNCS: $funcDir"
