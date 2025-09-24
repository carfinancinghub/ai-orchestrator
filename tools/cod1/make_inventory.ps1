param(
  [string]$AIO        = "C:\c\ai-orchestrator",
  [string]$Frontend   = "C:\Backup_Projects\CFH\frontend",
  [string]$Repo       = "carfinancinghub/cfh",
  [string]$BaseBranch = "main",
  [string]$HeadBranch = "ts-migration/rolling",
  [switch]$WriteCandidateList,
  [int]$TopN = 250
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

$ts = Get-Date -Format yyyyMMdd_HHmmss
$reports = Join-Path $AIO "reports"
$debug   = Join-Path $reports "debug"
New-Item -ItemType Directory -Force -Path $reports,$debug | Out-Null
$csv  = Join-Path $reports ("inv_{0}.csv" -f $ts)
$json = Join-Path $reports ("inv_{0}.json" -f $ts)
$md   = Join-Path $debug   ("inv_{0}.md"  -f $ts)

function Get-SHA1([string]$Path) {
  try {
    $sha=[System.Security.Cryptography.SHA1]::Create()
    $fs=[System.IO.File]::OpenRead($Path)
    try { [BitConverter]::ToString($sha.ComputeHash($fs)).Replace('-','').ToLower() }
    finally { $fs.Dispose(); $sha.Dispose() }
  } catch { "" }
}

function Get-FuncCount([string]$Path) {
  try {
    $t = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    ([regex]::Matches($t,'function\s+[A-Za-z0-9_]+\s*\(').Count) +
    ([regex]::Matches($t,'=\s*\([^)]*\)\s*=>').Count)
  } catch { 0 }
}

function Get-WorthScore([string]$Ext,[double]$SizeKB,[int]$FnCount){
  $extw = switch ($Ext.ToLower()) { ".tsx" {1.0} ".ts" {0.9} ".jsx" {0.7} ".js" {0.6} default {0.3} }
  $sizePen = [Math]::Max(0, ($SizeKB - 50) / 200)
  $fnBonus = [Math]::Min(0.4, 0.04 * $FnCount)
  [Math]::Round($extw + $fnBonus - $sizePen, 4)
}

function RelFrom-FrontendSrc([System.IO.FileInfo]$F){
  $root = (Join-Path $Frontend "src") + [IO.Path]::DirectorySeparatorChar
  $full = $F.FullName
  if ($full.StartsWith($root, $true, [Globalization.CultureInfo]::InvariantCulture)) {
    return ($full.Substring($root.Length) -replace '\\','/')
  }
  return $F.Name
}

function GhUrl($Repo,$Branch,$RepoRel){ "https://github.com/$Repo/blob/$Branch/$RepoRel" }

function Find-Spec([string]$Stem){
  Test-Path (Join-Path "artifacts\specs" ("{0}_spec.md" -f $Stem))
}

function Find-Suggestion([string]$FileName){
  [bool](Get-ChildItem "artifacts\suggestions" -Recurse -File -Filter "$FileName.json" -ErrorAction SilentlyContinue |
    Select-Object -First 1)
}

function Find-GeneratedFor([string]$Stem,[string]$Ext){
  if ($Ext -ieq ".js") {
    return Test-Path (Join-Path "artifacts\generated" ($Stem + ".ts"))
  } elseif ($Ext -ieq ".jsx") {
    return Test-Path (Join-Path "artifacts\generated" ($Stem + ".tsx"))
  } else {
    return (Test-Path (Join-Path "artifacts\generated" ($Stem + ".ts"))) -or
           (Test-Path (Join-Path "artifacts\generated" ($Stem + ".tsx")))
  }
}

$rows = New-Object System.Collections.Generic.List[object]

# --- src inventory ---
$srcRoot = Join-Path $Frontend "src"
if (Test-Path $srcRoot) {
  $srcFiles = Get-ChildItem $srcRoot -File -Recurse -ErrorAction SilentlyContinue |
              Where-Object { $_.Extension -in @(".js",".jsx",".ts",".tsx") -and $_.FullName -notmatch '\\node_modules\\|\\dist\\' }

  foreach ($f in $srcFiles) {
    $rel     = RelFrom-FrontendSrc $f
    $repoRel = "src/$rel"
    $ext     = $f.Extension
    $size    = $f.Length
    $sha1    = Get-SHA1 $f.FullName
    $fnc     = Get-FuncCount $f.FullName
    $ws      = Get-WorthScore $ext ($size/1KB) $fnc
    $stem    = [IO.Path]::GetFileNameWithoutExtension($f.Name)
    $converted = Find-GeneratedFor $stem $ext
    $hasSpec   = Find-Spec $stem
    $hasSug    = Find-Suggestion $f.Name
    $ghMain    = GhUrl $Repo $BaseBranch $repoRel

    $ghHead = ""
    if (-not [string]::IsNullOrWhiteSpace($HeadBranch)) {
      $ghHead = GhUrl $Repo $HeadBranch $repoRel
    }

    $rows.Add([PSCustomObject]@{
      category            = "src"
      name                = $f.Name
      repo_rel            = $repoRel
      local_path          = $f.FullName
      ext                 = $ext
      size_bytes          = $size
      sha1                = $sha1
      fn_count            = $fnc
      worth_score         = $ws
      converted_generated = $converted
      spec_exists         = $hasSpec
      suggestion_exists   = $hasSug
      gh_main             = $ghMain
      gh_head             = $ghHead
    }) | Out-Null
  }
} else {
  Write-Warning "Missing $srcRoot"
}

# --- specs inventory ---
if (Test-Path "artifacts\specs") {
  Get-ChildItem "artifacts\specs" -File -Filter *_spec.md | ForEach-Object {
    $rows.Add([PSCustomObject]@{
      category            = "spec"
      name                = $_.Name
      repo_rel            = ""
      local_path          = $_.FullName
      ext                 = ".md"
      size_bytes          = $_.Length
      sha1                = Get-SHA1 $_.FullName
      fn_count            = 0
      worth_score         = 0
      converted_generated = $false
      spec_exists         = $true
      suggestion_exists   = $false
      gh_main             = ""
      gh_head             = ""
    }) | Out-Null
  }
}

# --- suggestions inventory ---
if (Test-Path "artifacts\suggestions") {
  Get-ChildItem "artifacts\suggestions" -File -Recurse -Filter *.json | ForEach-Object {
    $rows.Add([PSCustomObject]@{
      category            = "suggestion"
      name                = $_.Name
      repo_rel            = ""
      local_path          = $_.FullName
      ext                 = ".json"
      size_bytes          = $_.Length
      sha1                = Get-SHA1 $_.FullName
      fn_count            = 0
      worth_score         = 0
      converted_generated = $false
      spec_exists         = $false
      suggestion_exists   = $true
      gh_main             = ""
      gh_head             = ""
    }) | Out-Null
  }
}

# --- generated inventory ---
if (Test-Path "artifacts\generated") {
  Get-ChildItem "artifacts\generated" -File -Recurse -Include *.ts,*.tsx | ForEach-Object {
    $repoRel  = "generated/$($_.Name)"
    $ghMain   = GhUrl $Repo $BaseBranch $repoRel

    $ghHead = ""
    if (-not [string]::IsNullOrWhiteSpace($HeadBranch)) {
      $ghHead = GhUrl $Repo $HeadBranch $repoRel
    }

    $rows.Add([PSCustomObject]@{
      category            = "generated"
      name                = $_.Name
      repo_rel            = $repoRel
      local_path          = $_.FullName
      ext                 = $_.Extension
      size_bytes          = $_.Length
      sha1                = Get-SHA1 $_.FullName
      fn_count            = Get-FuncCount $_.FullName
      worth_score         = 0
      converted_generated = $true
      spec_exists         = $false
      suggestion_exists   = $false
      gh_main             = $ghMain
      gh_head             = $ghHead
    }) | Out-Null
  }
}

# --- write CSV/JSON ---
$rows | Sort-Object category,name | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8
$rows | ConvertTo-Json -Depth 6 | Set-Content -Path $json -Encoding UTF8

# --- optional candidate list for the pipeline ---
if ($WriteCandidateList) {
  $cands = $rows | Where-Object {
    $_.category -eq "src" -and (($_.ext -ieq ".js") -or ($_.ext -ieq ".jsx")) -and (-not $_.converted_generated)
  } | Sort-Object worth_score -Descending | Select-Object -First $TopN

  $outList = Join-Path $reports "conversion_candidates.txt"
  ($cands | ForEach-Object { $_.local_path }) -join "`r`n" | Set-Content -Path $outList -Encoding UTF8
  Write-Host "Wrote $outList (Top $TopN by worth_score, JS/JSX not yet converted)"
}

# --- overview markdown ---
$srcCount  = ($rows | Where-Object { $_.category -eq "src" }).Count
$genCount  = ($rows | Where-Object { $_.category -eq "generated" }).Count
$specCount = ($rows | Where-Object { $_.category -eq "spec" }).Count
$suggCount = ($rows | Where-Object { $_.category -eq "suggestion" }).Count

$top20 = $rows |
  Where-Object { $_.category -eq "src" } |
  Sort-Object worth_score -Descending |
  Select-Object -First 20 name, ext, worth_score, converted_generated, gh_head

$lines = @(
  "# Inventory $ts", "",
  "**Counts**", "",
  "- src: $srcCount",
  "- generated: $genCount",
  "- specs: $specCount",
  "- suggestions: $suggCount", "",
  "**Top 20 src by worth_score**", "",
  "| name | ext | worth | converted | gh (head) |",
  "|------|-----|-------|-----------|-----------|"
)
foreach ($t in $top20) {
  $lines += "| $($t.name) | $($t.ext) | $($t.worth_score) | $($t.converted_generated) | $($t.gh_head) |"
}
$lines -join "`r`n" | Set-Content -Path $md -Encoding UTF8

Write-Host "Inventory:"
Write-Host "  CSV : $csv"
Write-Host "  JSON: $json"
Write-Host "  MD  : $md"
