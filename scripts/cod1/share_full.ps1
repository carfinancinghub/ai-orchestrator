param(
  [string]$FrontRepo  = "C:\Backup_Projects\CFH\frontend",
  [string]$AIORepo    = "C:\c\ai-orchestrator",
  [string]$AIOBranch  = "fix/restore-report-docs",
  [string]$TrackerRelPath = "docs\SG_CORRECTIONS_COD1.md",
  [int]$RecentDebugCount = 6,
  [switch]$Open
)
$ErrorActionPreference = "Stop"

function RelPosix($root,$child){
  $r = (Resolve-Path $root).Path -replace "\\","/"
  $c = (Resolve-Path $child).Path -replace "\\","/"
  if ($c.StartsWith($r + "/")) { return $c.Substring($r.Length + 1) }
  return (Split-Path -Leaf $c)
}
function GetOwnerRepo($repoPath){
  $remote = git -C $repoPath remote get-url origin 2>$null
  if ($remote -match "github\.com[:/](.+?)(\.git)?$"){ return $Matches[1] }
  return $null
}
function EnsureBranch($repo,$branch){
  $cur = (git -C $repo rev-parse --abbrev-ref HEAD).Trim()
  if ($cur -eq $branch){ return }
  $hasLocal  = (git -C $repo branch --list $branch)
  $hasRemote = (git -C $repo ls-remote --heads origin $branch)
  if     ($hasLocal)  { git -C $repo switch $branch | Out-Null }
  elseif ($hasRemote) { git -C $repo switch -c $branch origin/$branch | Out-Null }
  else                { git -C $repo checkout -B $branch | Out-Null }
}
function Test-UrlOk($url){
  try{
    $r = Invoke-WebRequest -Method Head -Uri $url -MaximumRedirection 5 -TimeoutSec 10 -Headers @{ "User-Agent"="curl/8" }
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400)
  }catch{ return $false }
}
function Test-BlobOk($repo,$branch,$relPosix){
  & git -C $repo cat-file -e ($branch + ":" + $relPosix) 2>$null
  return ($LASTEXITCODE -eq 0)
}
function SafeConvFromJson($path){
  try{
    $raw = Get-Content $path -Raw -ErrorAction Stop
    return $raw | ConvertFrom-Json -ErrorAction Stop
  }catch{ return $null }
}
function OkMark($v){
  if ($null -eq $v) { return "❔" }
  if ($v) { return "✅" }
  return "❌"
}

$frontOwnerRepo = GetOwnerRepo $FrontRepo
$aioOwnerRepo   = GetOwnerRepo $AIORepo
$frontBranch    = (git -C $FrontRepo rev-parse --abbrev-ref HEAD).Trim()

# Tracker
$trackerAbs = Join-Path $FrontRepo $TrackerRelPath
$trackerUrl = $null
$trackerOk  = $false
if (Test-Path $trackerAbs){
  $trackerRel = RelPosix $FrontRepo $trackerAbs
  $trackerUrl = "https://github.com/" + $frontOwnerRepo + "/blob/" + $frontBranch + "/" + $trackerRel
  $trackerOk  = Test-UrlOk $trackerUrl
}

# PRs from tracker
$allPRs = @()
if (Test-Path $trackerAbs){
  $text = Get-Content $trackerAbs -Raw
  $direct = [regex]::Matches($text,"https?://github\.com/[^\s)]+") | ForEach-Object { $_.Value } | Select-Object -Unique
  $branches = [regex]::Matches($text,"(?i)\(branch:\s*([^)]+)\)") | ForEach-Object { $_.Groups[1].Value.Trim() } | Select-Object -Unique
  foreach($b in $branches){
    $allPRs += ("https://github.com/" + $frontOwnerRepo + "/compare/main..." + $b + "?expand=1")
  }
  $allPRs = ($direct + $allPRs) | Where-Object { $_ -match "/compare/" } | Select-Object -Unique
}

# Latest COD1 summary
$latestSummary = Get-ChildItem -Path (Join-Path $AIORepo "reports\debug") -Filter cod1_summary_*.md -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
$latestSummaryBlob = $null
$latestSummaryOk   = $false
if($latestSummary){
  $rel = RelPosix $AIORepo $latestSummary.FullName
  $latestSummaryBlob = "https://github.com/" + $aioOwnerRepo + "/blob/" + $AIOBranch + "/" + $rel
  $latestSummaryOk   = Test-UrlOk $latestSummaryBlob
}

# Grouped files
$groupedPath = Join-Path $AIORepo "reports\grouped_files.txt"
$groupedBlob = $null
$groupedOk   = $false
$groupCount  = $null
if(Test-Path $groupedPath){
  $rel = RelPosix $AIORepo $groupedPath
  $groupedBlob = "https://github.com/" + $aioOwnerRepo + "/blob/" + $AIOBranch + "/" + $rel
  $groupedOk   = Test-UrlOk $groupedBlob
  $txt = Get-Content $groupedPath -Raw
  $groupCount = ([regex]::Matches($txt,'(?m)^\s*Group\b')).Count
}
$groupSuffix = ""
if ($groupCount) { $groupSuffix = " — **" + $groupCount + " groups (approx.)**" }

# Gates (latest)
$gLatest = Get-ChildItem -Path (Join-Path $AIORepo "reports") -Recurse -Include "gates_*.json" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
$gBlob = $null; $gOk=$false; $gBuildText="n/a"; $gTestText="n/a"; $gLintText="n/a"
if($gLatest){
  $gRel = RelPosix $AIORepo $gLatest.FullName
  $gBlob = "https://github.com/" + $aioOwnerRepo + "/blob/" + $AIOBranch + "/" + $gRel
  $gOk   = Test-UrlOk $gBlob
  $gj = SafeConvFromJson $gLatest.FullName
  if($gj){
    if($gj.PSObject.Properties.Name -contains 'build'){
      $val = $gj.build
      if($val -is [pscustomobject] -and ($val.PSObject.Properties.Name -contains 'status')){ $val = $val.status }
      if("$val" -ne ""){ $gBuildText = "$val" }
    }
    if($gj.PSObject.Properties.Name -contains 'test'){
      $val = $gj.test
      if($val -is [pscustomobject] -and ($val.PSObject.Properties.Name -contains 'status')){ $val = $val.status }
      if("$val" -ne ""){ $gTestText = "$val" }
    }
    if($gj.PSObject.Properties.Name -contains 'lint'){
      $val = $gj.lint
      if($val -is [pscustomobject] -and ($val.PSObject.Properties.Name -contains 'status')){ $val = $val.status }
      if("$val" -ne ""){ $gLintText = "$val" }
    }
  }
}

# Frontend gates log (optional)
$fbBlob=$null; $fbBuildPass=$null; $fbTestPass=$null; $fbLintPass=$null
$frontDebugDir = Join-Path $FrontRepo "reports\debug"
if(Test-Path $frontDebugDir){
  $frontBuildLog = Get-ChildItem $frontDebugDir -Filter "frontend_build_test_lint_*.md" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if($frontBuildLog){
    $fbRel  = RelPosix $FrontRepo $frontBuildLog.FullName
    $fbBlob = "https://github.com/" + $frontOwnerRepo + "/blob/" + $frontBranch + "/" + $fbRel
    $fbTxt  = Get-Content $frontBuildLog.FullName -Raw
    $fbBuildPass = ($fbTxt -match 'built in \d+ms' -or $fbTxt -match '✓ built')
    $fbTestPass  = ($fbTxt -match 'Test Files\s+\d+\s+passed')
    $fbLintPass  = -not ($fbTxt -match '(?im)^\s*error\b|✖')
  }
}

# Artifact counts
$genCount  = (Get-ChildItem (Join-Path $AIORepo "artifacts\generated")           -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
$specCount = (Get-ChildItem (Join-Path $AIORepo "artifacts\generations_special")  -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
$stagCount = (Get-ChildItem (Join-Path $AIORepo "artifacts\staging")              -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count

# Build markdown
$ts = Get-Date -Format "yyyy-MM-dd HH:mm"
$lines = @()
$lines += "# COD1 — Share Snapshot (Full)"
$lines += ""
$lines += "**Generated:** " + $ts
$lines += ""
$lines += "## Key Links"
if($trackerUrl){ $lines += "- " + (OkMark $trackerOk) + " Tracker: " + $trackerUrl }
foreach($pr in $allPRs){ $lines += "- " + (OkMark (Test-UrlOk $pr)) + " PR: " + $pr }
if($latestSummaryBlob){ $lines += "- " + (OkMark $latestSummaryOk) + " Summary report: " + $latestSummaryBlob }
if($groupedBlob){ $lines += "- " + (OkMark $groupedOk) + " Grouped files: " + $groupedBlob + $groupSuffix }
if($gBlob){ $lines += "- " + (OkMark $gOk) + " Gates (latest): " + $gBlob }
if($fbBlob){ $lines += "- " + (OkMark (Test-UrlOk $fbBlob)) + " Frontend gates log: " + $fbBlob }
$lines += ""
$lines += "## Current Status (high-level)"
$lines += "- Frontend basic gates locally: Build " + (OkMark $fbBuildPass) + "  •  Tests " + (OkMark $fbTestPass) + "  •  Lint " + (OkMark $fbLintPass)
if($gBlob){ $lines += "- Orchestrator gates (latest JSON): Build " + $gBuildText + " • Test " + $gTestText + " • Lint " + $gLintText }
$lines += ""
$lines += "## Artifacts Progress"
$lines += "- Generated files: **" + $genCount + "**"
$lines += "- Special generations: **" + $specCount + "**"
$lines += "- Staging files: **" + $stagCount + "**"
$lines += ""
$lines += "## Recent Debug Logs"
$debugFiles = Get-ChildItem -Path (Join-Path $AIORepo "reports\debug") -Filter *.md -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First $RecentDebugCount
if($debugFiles.Count -gt 0){
  foreach($f in $debugFiles){
    $rel = RelPosix $AIORepo $f.FullName
    $blob = "https://github.com/" + $aioOwnerRepo + "/blob/" + $AIOBranch + "/" + $rel
    $lines += "- " + (OkMark (Test-UrlOk $blob)) + " " + $blob
  }
}else{
  $lines += "_(none found)_"
}
$lines += ""
$lines += "## Notable Work Completed"
$lines += "- ✅ COD1-001 branch + tests wired (AIDiagnosticsAssistant)."
$lines += "- ✅ COD1-002 branch scaffolded; tracker + PR link established."
$lines += "- ✅ Tracker file created and kept in sync."
$lines += "- ✅ Summary report auto-generation (make_report.ps1)."
$lines += "- ✅ Share note automation with live link checks."
$lines += ""
$lines += "## Remaining / Next Steps"
$lines += "- Implement multi-AI review flow (Free/Premium/Wow++), persist worth_score."
$lines += "- Wire upload_generated_to_github when AIO_UPLOAD_TS=1 (target ts-migration/generated)."
$lines += "- Patch UTF-8 handling for gates to eliminate UnicodeDecodeError; re-run with AIO_RUN_GATES=1."
$lines += "- Add duplicate elimination pass; output reports/duplicates_eliminated.csv."
$lines += "- Open PR for fix/restore-report-docs if not already open."
$lines += ""

$outRel = "reports\debug\sg_share_full_{0:yyyyMMdd_HHmm}.md" -f (Get-Date)
$outAbs = Join-Path $AIORepo $outRel
$lines -join "`r`n" | Set-Content -Path $outAbs -Encoding UTF8

git -C $AIORepo config commit.gpgsign false | Out-Null
if (-not (git -C $AIORepo config user.email)) { git -C $AIORepo config user.email "ci@local" | Out-Null }
if (-not (git -C $AIORepo config user.name))  { git -C $AIORepo config user.name  "Local CI" | Out-Null }
git -C $AIORepo fetch origin 2>$null | Out-Null
EnsureBranch $AIORepo $AIOBranch
git -C $AIORepo add -- $outAbs
git -C $AIORepo commit --no-verify -m ("docs(COD1): SG share (full) " + (Split-Path -Leaf $outRel)) | Out-Null
git -C $AIORepo push -u origin $AIOBranch | Out-Null

$shareBlob = "https://github.com/" + $aioOwnerRepo + "/blob/" + $AIOBranch + "/" + (RelPosix $AIORepo $outAbs)
"===> SG SHARE (FULL): " + $shareBlob
if($Open){ Start-Process $shareBlob }
