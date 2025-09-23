param(
  [string]$FrontRepo,
  [string]$TrackerRelPath = "docs\SG_CORRECTIONS_COD1.md",
  [string]$AIORepo,
  [string]$AIOBranch = "fix/restore-report-docs",
  [int]$LogCount = 5,
  [switch]$Open
)
$ErrorActionPreference="Stop"
function To-Posix($p){ ($p -replace "\\","/") }
function Get-OwnerRepo($repoPath){ $remote=git -C $repoPath remote get-url origin 2>$null; if($remote -match "github\.com[:/](.+?)(\.git)?$"){ $Matches[1]} }
function Rel-Posix($root,$child){ $r=To-Posix (Resolve-Path $root); $c=To-Posix (Resolve-Path $child); if($c.StartsWith("$r/")){ return $c.Substring($r.Length+1) } (Split-Path -Leaf $c) }
function Extract-Section($name,$text){ if($text -match ("(?s)##\s+"+[regex]::Escape($name)+"\s*(.*?)(\r?\n##|\Z)")){ return $Matches[1].Trim() } "" }
function Ensure-Branch($repo,$branch){
  $current=(git -C $repo rev-parse --abbrev-ref HEAD).Trim()
  if($current -ne $branch){
    $hasLocal=(git -C $repo branch --list $branch)
    $hasRemote=(git -C $repo ls-remote --heads origin $branch)
    if($hasLocal){ git -C $repo switch $branch | Out-Null }
    elseif($hasRemote){ git -C $repo switch -c $branch origin/$branch | Out-Null }
    else{ git -C $repo checkout -B $branch | Out-Null }
  }
}
function Test-UrlOk($url){ try{ $r=Invoke-WebRequest -Method Head -Uri $url -MaximumRedirection 5 -TimeoutSec 10 -Headers @{ "User-Agent"="curl/8" }; ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) }catch{ $false } }
function Test-BlobOk($repo,$branch,$relPosix){ & git -C $repo cat-file -e ("{0}:{1}" -f $branch,$relPosix) 2>$null; ($LASTEXITCODE -eq 0) }
function Mark($ok){ if($ok){'✅'}else{'❌'} }

$frontRepo=(Resolve-Path $FrontRepo).Path
$trackerAbs=Join-Path $frontRepo $TrackerRelPath
if(-not (Test-Path $trackerAbs)){ throw "Tracker not found: $trackerAbs" }
$frontOwnerRepo=Get-OwnerRepo $frontRepo
$aioRepo=(Resolve-Path $AIORepo).Path
$aioOwnerRepo=Get-OwnerRepo $aioRepo
$frontBranch=(git -C $frontRepo rev-parse --abbrev-ref HEAD).Trim()

$trackerText=Get-Content $trackerAbs -Raw
$requested  =Extract-Section "Requested"   $trackerText
$inprogress =Extract-Section "In Progress" $trackerText
$done       =Extract-Section "Done"        $trackerText
$prs=[regex]::Matches($trackerText,"(?i)https?://github\.com/[^\s)]+") | ForEach-Object { $_.Value } | Select-Object -Unique
$branches=[regex]::Matches($trackerText,"(?i)\(branch:\s*([^)]+)\)") | ForEach-Object { $_.Groups[1].Value.Trim() } | Select-Object -Unique
$branchPRs=@(); foreach($b in $branches){ $branchPRs += ("https://github.com/{0}/compare/main...{1}?expand=1" -f $frontOwnerRepo,$b) }
$allPRs = ($prs + $branchPRs) | Where-Object { $_ } | Select-Object -Unique

$debugDir=Join-Path $aioRepo "reports\debug"
$lastLogs=@(); if(Test-Path $debugDir){ $lastLogs=Get-ChildItem $debugDir -Filter *.md | Sort-Object LastWriteTime -Descending | Select-Object -First 5 }

$outRel = "reports\debug\cod1_summary_{0:yyyyMMdd_HHmm}.md" -f (Get-Date)
$outAbs = Join-Path $aioRepo $outRel
$trackerRel = Rel-Posix $frontRepo $trackerAbs
$trackerBlob = "https://github.com/{0}/blob/{1}/{2}" -f $frontOwnerRepo, $frontBranch, $trackerRel
$trackerOk = (Test-BlobOk $frontRepo $frontBranch $trackerRel) -and (Test-UrlOk $trackerBlob)

$md = @()
$md += "# COD1 — Summary Report"
$md += ""
$md += "**Generated:** $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$md += ("**Tracker:** {0} {1}" -f (Mark $trackerOk), $trackerBlob)
$md += ""
if($allPRs.Count -gt 0){
  $md += "## PRs"
  foreach($u in $allPRs){ $md += ("- {0} {1}" -f (Mark (Test-UrlOk $u)), $u) }
  $md += ""
}
$md += "## Status"
$md += ""
$md += "### Requested"
$md += ($requested -ne "" ? $requested : "_(none)_")
$md += ""
$md += "### In Progress"
$md += ($inprogress -ne "" ? $inprogress : "_(none)_")
$md += ""
$md += "### Done"
$md += ($done -ne "" ? $done : "_(none)_")
$md += ""
if($lastLogs.Count -gt 0){
  $md += "## Recent debug logs"
  foreach($f in $lastLogs){
    $rel = Rel-Posix $aioRepo $f.FullName
    $blob = "https://github.com/{0}/blob/{1}/{2}" -f $aioOwnerRepo, $AIOBranch, $rel
    $ok = (Test-BlobOk $aioRepo $AIOBranch $rel) -and (Test-UrlOk $blob)
    $md += ("- {0} {1}" -f (Mark $ok), $blob)
  }
  $md += ""
}
$md -join "`r`n" | Set-Content -Path $outAbs -Encoding UTF8

git -C $aioRepo config commit.gpgsign false | Out-Null
if (-not (git -C $aioRepo config user.email)) { git -C $aioRepo config user.email "ci@local" | Out-Null }
if (-not (git -C $aioRepo config user.name))  { git -C $aioRepo config user.name  "Local CI" | Out-Null }
git -C $aioRepo fetch origin 2>$null | Out-Null
Ensure-Branch -repo $aioRepo -branch $AIOBranch
git -C $aioRepo add -- $outAbs
git -C $aioRepo commit --no-verify -m ("docs(COD1): summary report {0}" -f (Split-Path -Leaf $outRel)) | Out-Null
git -C $aioRepo push -u origin $AIOBranch | Out-Null

$blobRel = Rel-Posix $aioRepo $outAbs
$blobUrl = "https://github.com/{0}/blob/{1}/{2}" -f $aioOwnerRepo, $AIOBranch, $blobRel
"===> COD1 REPORT: $blobUrl"
if($Open){ Start-Process $blobUrl }
