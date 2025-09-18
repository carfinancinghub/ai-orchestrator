function GetOrCreatePR {
  param(
    [string]$RepoSlug,   # e.g. carfinancinghub/cfh
    [string]$Head,       # e.g. ts-migration/20250913_064349
    [string]$Base,       # e.g. main
    [string]$Title,
    [string]$Body
  )

  # Try to view PR by branch name as positional arg (works across gh versions)
  try {
    $json = gh pr view --repo $RepoSlug $Head --json number,url,state,headRefName 2>$null | ConvertFrom-Json
    if ($json -and $json.url) { return $json }
  } catch {}

  # Fallback: list open PRs and match by headRefName
  try {
    $list = gh pr list --repo $RepoSlug --state open --json number,url,headRefName 2>$null | ConvertFrom-Json
    if ($list) {
      $match = $list | Where-Object { $_.headRefName -eq $Head } | Select-Object -First 1
      if ($match) { return $match }
    }
  } catch {}

  # Create PR (older gh supports --head here)
  $args = @(
    "pr","create","--repo",$RepoSlug,
    "--base",$Base,
    "--head",$Head,
    "--title",$Title
  )
  if ($Body -and $Body.Trim()) {
    $tmp = New-TemporaryFile
    Set-Content $tmp $Body -Encoding UTF8
    $args += @("--body-file",$tmp.FullName)
  } else {
    $args += "--fill"
  }

  gh @args | Out-Null

  # View again by branch
  return (gh pr view --repo $RepoSlug $Head --json number,url,state,headRefName | ConvertFrom-Json)
}

param(
  [switch]$RunGates = $true,
  [switch]$OpenInBrowser = $true,
  [string]$FrontBase = "main",
  [string]$OrchBase  = "main"
)

$ErrorActionPreference = "Stop"

# --- Config (adjust paths if yours differ)
$FrontLocal = "C:\Backup_Projects\CFH\frontend"
$OrchLocal  = "C:\c\ai-orchestrator"
$FrontRepo  = "carfinancinghub/cfh"
$OrchRepo   = "carfinancinghub/ai-orchestrator"
$OrchBranch = "fix/restore-report-docs"   # current working branch
function _git([string]$cwd, [string[]]$args) { git -C $cwd @args }
function _has([string]$exe) { $null -ne (Get-Command $exe -ErrorAction SilentlyContinue) }

# --- Preconditions
if (-not (_has "git")) { throw "git not found in PATH" }
if (-not (_has "gh"))  { throw "GitHub CLI (gh) not found. Install from https://cli.github.com/ then run: gh auth login" }

# --- 0) Resolve $stamp consistently across repos
function Get-Stamp {
  if ($script:stamp -and $script:stamp -match '^\d{8}_\d{6}$') { return $script:stamp }

  $frontStampFile = Join-Path $FrontLocal ".orchestrator\stamp.txt"
  $orchStampFile  = Join-Path $OrchLocal  ".orchestrator\stamp.txt"
  foreach ($p in @($frontStampFile,$orchStampFile)) {
    if (Test-Path $p) {
      $s = (Get-Content $p -Raw).Trim()
      if ($s -match '^\d{8}_\d{6}$') { return $s }
    }
  }

  # Try to infer from frontend branch name ts-migration/<stamp>
  try {
    $frontHead = _git $FrontLocal @("rev-parse","--abbrev-ref","HEAD")
    if ($frontHead -match 'ts-migration/(\d{8}_\d{6})') { return $Matches[1] }
  } catch {}

  return (Get-Date -Format "yyyyMMdd_HHmmss")
}
$stamp = Get-Stamp
$FrontBranch = "ts-migration/$stamp"

# --- 1) Persist stamp into both repos
foreach ($root in @($FrontLocal,$OrchLocal)) {
  $dir = Join-Path $root ".orchestrator"
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Set-Content (Join-Path $dir "stamp.txt") $stamp -Encoding UTF8
}

# --- 2) Ensure frontend branch exists and is pushed
function Ensure-Branch {
  param($RepoPath,$Branch,$Base)
  $existsLocal  = (_git $RepoPath @("rev-parse","--verify",$Branch)) 2>$null
  if (-not $existsLocal) {
    _git $RepoPath @("fetch","--all") | Out-Null
    $existsRemote = (_git $RepoPath @("ls-remote","--heads","origin",$Branch)) 2>$null
    if ($existsRemote) {
      _git $RepoPath @("checkout","-B",$Branch,"origin/$Branch") | Out-Null
    } else {
      _git $RepoPath @("checkout",$Base)            | Out-Null
      _git $RepoPath @("pull","--ff-only")          | Out-Null
      _git $RepoPath @("checkout","-b",$Branch)     | Out-Null
      _git $RepoPath @("push","-u","origin",$Branch)| Out-Null
    }
  } else {
    # Make sure we’re on it
    _git $RepoPath @("checkout",$Branch) | Out-Null
  }
}
Ensure-Branch -RepoPath $FrontLocal -Branch $FrontBranch -Base $FrontBase
Ensure-Branch -RepoPath $OrchLocal  -Branch $OrchBranch  -Base $OrchBase

# --- 3) Optionally run gates + commit the stamped log in frontend
$frontLogRel = "reports\debug\frontend_build_test_lint_$stamp.md"
$frontLogAbs = Join-Path $FrontLocal $frontLogRel
if ($RunGates) {
  New-Item -ItemType Directory -Force -Path (Split-Path $frontLogAbs) | Out-Null
  # Use your stable runners
  & npm --prefix $FrontLocal run build   *>> $frontLogAbs
  & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $FrontLocal "scripts\run-vitest.ps1") *>> $frontLogAbs
  & npm --prefix $FrontLocal run lint    *>> $frontLogAbs

  _git $FrontLocal @("add",$frontLogRel) | Out-Null
  try {
    _git $FrontLocal @("commit","-m","chore(frontend): gates log [$stamp]") | Out-Null
  } catch {}
  _git $FrontLocal @("push") | Out-Null
}

# --- 4) Create or reuse FRONTEND PR
function GetOrCreatePR_OLD {
  param(
    [string]$RepoSlug,   # e.g. carfinancinghub/cfh
    [string]$Head,       # e.g. ts-migration/20250913_064349
    [string]$Base,       # e.g. main
    [string]$Title,
    [string]$Body
  )

  # Try: view by branch as positional arg (works on old/new gh)
  try {
    $json = gh pr view --repo $RepoSlug $Head --json number,url,state,headRefName 2>$null | ConvertFrom-Json
    if ($json -and $json.url) { return $json }
  } catch {}

  # Fallback: list open PRs and match by headRefName
  try {
    $list = gh pr list --repo $RepoSlug --state open --json number,url,headRefName 2>$null | ConvertFrom-Json
    if ($list) {
      $match = $list | Where-Object { param(
  [switch]$RunGates = $true,
  [switch]$OpenInBrowser = $true,
  [string]$FrontBase = "main",
  [string]$OrchBase  = "main"
)

$ErrorActionPreference = "Stop"

# --- Config (adjust paths if yours differ)
$FrontLocal = "C:\Backup_Projects\CFH\frontend"
$OrchLocal  = "C:\c\ai-orchestrator"
$FrontRepo  = "carfinancinghub/cfh"
$OrchRepo   = "carfinancinghub/ai-orchestrator"
$OrchBranch = "fix/restore-report-docs"   # current working branch
function _git([string]$cwd, [string[]]$args) { git -C $cwd @args }
function _has([string]$exe) { $null -ne (Get-Command $exe -ErrorAction SilentlyContinue) }

# --- Preconditions
if (-not (_has "git")) { throw "git not found in PATH" }
if (-not (_has "gh"))  { throw "GitHub CLI (gh) not found. Install from https://cli.github.com/ then run: gh auth login" }

# --- 0) Resolve $stamp consistently across repos
function Get-Stamp {
  if ($script:stamp -and $script:stamp -match '^\d{8}_\d{6}$') { return $script:stamp }

  $frontStampFile = Join-Path $FrontLocal ".orchestrator\stamp.txt"
  $orchStampFile  = Join-Path $OrchLocal  ".orchestrator\stamp.txt"
  foreach ($p in @($frontStampFile,$orchStampFile)) {
    if (Test-Path $p) {
      $s = (Get-Content $p -Raw).Trim()
      if ($s -match '^\d{8}_\d{6}$') { return $s }
    }
  }

  # Try to infer from frontend branch name ts-migration/<stamp>
  try {
    $frontHead = _git $FrontLocal @("rev-parse","--abbrev-ref","HEAD")
    if ($frontHead -match 'ts-migration/(\d{8}_\d{6})') { return $Matches[1] }
  } catch {}

  return (Get-Date -Format "yyyyMMdd_HHmmss")
}
$stamp = Get-Stamp
$FrontBranch = "ts-migration/$stamp"

# --- 1) Persist stamp into both repos
foreach ($root in @($FrontLocal,$OrchLocal)) {
  $dir = Join-Path $root ".orchestrator"
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Set-Content (Join-Path $dir "stamp.txt") $stamp -Encoding UTF8
}

# --- 2) Ensure frontend branch exists and is pushed
function Ensure-Branch {
  param($RepoPath,$Branch,$Base)
  $existsLocal  = (_git $RepoPath @("rev-parse","--verify",$Branch)) 2>$null
  if (-not $existsLocal) {
    _git $RepoPath @("fetch","--all") | Out-Null
    $existsRemote = (_git $RepoPath @("ls-remote","--heads","origin",$Branch)) 2>$null
    if ($existsRemote) {
      _git $RepoPath @("checkout","-B",$Branch,"origin/$Branch") | Out-Null
    } else {
      _git $RepoPath @("checkout",$Base)            | Out-Null
      _git $RepoPath @("pull","--ff-only")          | Out-Null
      _git $RepoPath @("checkout","-b",$Branch)     | Out-Null
      _git $RepoPath @("push","-u","origin",$Branch)| Out-Null
    }
  } else {
    # Make sure we’re on it
    _git $RepoPath @("checkout",$Branch) | Out-Null
  }
}
Ensure-Branch -RepoPath $FrontLocal -Branch $FrontBranch -Base $FrontBase
Ensure-Branch -RepoPath $OrchLocal  -Branch $OrchBranch  -Base $OrchBase

# --- 3) Optionally run gates + commit the stamped log in frontend
$frontLogRel = "reports\debug\frontend_build_test_lint_$stamp.md"
$frontLogAbs = Join-Path $FrontLocal $frontLogRel
if ($RunGates) {
  New-Item -ItemType Directory -Force -Path (Split-Path $frontLogAbs) | Out-Null
  # Use your stable runners
  & npm --prefix $FrontLocal run build   *>> $frontLogAbs
  & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $FrontLocal "scripts\run-vitest.ps1") *>> $frontLogAbs
  & npm --prefix $FrontLocal run lint    *>> $frontLogAbs

  _git $FrontLocal @("add",$frontLogRel) | Out-Null
  try {
    _git $FrontLocal @("commit","-m","chore(frontend): gates log [$stamp]") | Out-Null
  } catch {}
  _git $FrontLocal @("push") | Out-Null
}

# --- 4) Create or reuse FRONTEND PR
function GetOrCreatePR_OLD {
  param(
    [string]$RepoSlug,   # e.g. carfinancinghub/cfh
    [string]$Head,       # e.g. ts-migration/20250913_064349
    [string]$Base,       # e.g. main
    [string]$Title,
    [string]$Body
  )
  $json = gh pr view --repo $RepoSlug --json number,url,state,headRefName --head $Head 2>$null | ConvertFrom-Json
  if ($json -and $json.url) { return $json }

  # Create
  $created = gh pr create `
    --repo $RepoSlug `
    --base $Base `
    --head $Head `
    --title $Title `
    --body  $Body `
    --fill 2>$null

  # Fetch JSON after creation
  return (gh pr view --repo $RepoSlug --json number,url,state,headRefName --head $Head | ConvertFrom-Json)
}

$frontTitle = "TS migration ($stamp): gates + test harness"
$frontBody  = @"
- Stamp: **$stamp**
- Gates log: https://github.com/$FrontRepo/blob/$FrontBranch/$($frontLogRel -replace '\\','/')
- Node modules guard: pre-commit hook + .gitignore
"@
$frontPR = GetOrCreatePR -RepoSlug $FrontRepo -Head $FrontBranch -Base $FrontBase -Title $frontTitle -Body $frontBody
if (-not $frontPR -or -not $frontPR.url) { throw "Could not create/view frontend PR" }

# --- 5) Create or reuse ORCHESTRATOR PR
$orchTitle = "Restore report docs + links summary ($stamp)"
$orchBody  = @"
Companion to frontend PR for stamp **$stamp**.

- Summary file will include both PR links and front gates log
"@
$orchPR = GetOrCreatePR -RepoSlug $OrchRepo -Head $OrchBranch -Base $OrchBase -Title $orchTitle -Body $orchBody
if (-not $orchPR -or -not $orchPR.url) { throw "Could not create/view orchestrator PR" }

# --- 6) Write/Update the stamped summary in orchestrator
$summaryRel = "reports\debug\summary_links_$stamp.md"
$summaryAbs = Join-Path $OrchLocal $summaryRel
New-Item -ItemType Directory -Force -Path (Split-Path $summaryAbs) | Out-Null

$summary = @"
# CFH Orchestrator — Links Summary ($stamp)

## Frontend repo (cfh)
- **Branch:** `$FrontBranch`
- **Tree:** https://github.com/$FrontRepo/tree/$FrontBranch
- **Frontend gates log:** https://github.com/$FrontRepo/blob/$FrontBranch/$($frontLogRel -replace '\\','/')
- **PR:** $($frontPR.url)

## Orchestrator repo (ai-orchestrator)
- **Branch:** `$OrchBranch`
- **Tree:** https://github.com/$OrchRepo/tree/$OrchBranch
- **PR:** $($orchPR.url)
"@
Set-Content $summaryAbs $summary -Encoding UTF8

_git $OrchLocal @("add",$summaryRel) | Out-Null
try {
  _git $OrchLocal @("commit","-m","docs: links summary refresh [$stamp]") | Out-Null
} catch {}
_git $OrchLocal @("push") | Out-Null

$summaryUrl = "https://github.com/$OrchRepo/blob/$OrchBranch/$($summaryRel -replace '\\','/')"
Write-Host "`n=== DONE ==="
Write-Host "Frontend PR  : $($frontPR.url)"
Write-Host "Orchestrator PR: $($orchPR.url)"
Write-Host "Summary URL   : $summaryUrl`n"

if ($OpenInBrowser) {
  Start-Process $frontPR.url
  Start-Process $orchPR.url
  Start-Process $summaryUrl
}
.headRefName -eq $Head } | Select-Object -First 1
      if ($match) { return $match }
    }
  } catch {}

  # Create PR
  $args = @(
    "pr","create","--repo",$RepoSlug,
    "--base",$Base,
    "--head",$Head,
    "--title",$Title
  )
  if ($Body -and $Body.Trim()) {
    $tmp = New-TemporaryFile
    Set-Content $tmp $Body -Encoding UTF8
    $args += @("--body-file",$tmp.FullName)
  } else {
    $args += "--fill"
  }

  gh @args | Out-Null

  # View again by branch
  return (gh pr view --repo $RepoSlug $Head --json number,url,state,headRefName | ConvertFrom-Json)
}

  # Create
  $created = gh pr create `
    --repo $RepoSlug `
    --base $Base `
    --head $Head `
    --title $Title `
    --body  $Body `
    --fill 2>$null

  # Fetch JSON after creation
  return (gh pr view --repo $RepoSlug --json number,url,state,headRefName --head $Head | ConvertFrom-Json)
}

$frontTitle = "TS migration ($stamp): gates + test harness"
$frontBody  = @"
- Stamp: **$stamp**
- Gates log: https://github.com/$FrontRepo/blob/$FrontBranch/$($frontLogRel -replace '\\','/')
- Node modules guard: pre-commit hook + .gitignore
"@
$frontPR = GetOrCreatePR -RepoSlug $FrontRepo -Head $FrontBranch -Base $FrontBase -Title $frontTitle -Body $frontBody
if (-not $frontPR -or -not $frontPR.url) { throw "Could not create/view frontend PR" }

# --- 5) Create or reuse ORCHESTRATOR PR
$orchTitle = "Restore report docs + links summary ($stamp)"
$orchBody  = @"
Companion to frontend PR for stamp **$stamp**.

- Summary file will include both PR links and front gates log
"@
$orchPR = GetOrCreatePR -RepoSlug $OrchRepo -Head $OrchBranch -Base $OrchBase -Title $orchTitle -Body $orchBody
if (-not $orchPR -or -not $orchPR.url) { throw "Could not create/view orchestrator PR" }

# --- 6) Write/Update the stamped summary in orchestrator
$summaryRel = "reports\debug\summary_links_$stamp.md"
$summaryAbs = Join-Path $OrchLocal $summaryRel
New-Item -ItemType Directory -Force -Path (Split-Path $summaryAbs) | Out-Null

$summary = @"
# CFH Orchestrator — Links Summary ($stamp)

## Frontend repo (cfh)
- **Branch:** `$FrontBranch`
- **Tree:** https://github.com/$FrontRepo/tree/$FrontBranch
- **Frontend gates log:** https://github.com/$FrontRepo/blob/$FrontBranch/$($frontLogRel -replace '\\','/')
- **PR:** $($frontPR.url)

## Orchestrator repo (ai-orchestrator)
- **Branch:** `$OrchBranch`
- **Tree:** https://github.com/$OrchRepo/tree/$OrchBranch
- **PR:** $($orchPR.url)
"@
Set-Content $summaryAbs $summary -Encoding UTF8

_git $OrchLocal @("add",$summaryRel) | Out-Null
try {
  _git $OrchLocal @("commit","-m","docs: links summary refresh [$stamp]") | Out-Null
} catch {}
_git $OrchLocal @("push") | Out-Null

$summaryUrl = "https://github.com/$OrchRepo/blob/$OrchBranch/$($summaryRel -replace '\\','/')"
Write-Host "`n=== DONE ==="
Write-Host "Frontend PR  : $($frontPR.url)"
Write-Host "Orchestrator PR: $($orchPR.url)"
Write-Host "Summary URL   : $summaryUrl`n"

if ($OpenInBrowser) {
  Start-Process $frontPR.url
  Start-Process $orchPR.url
  Start-Process $summaryUrl
}




