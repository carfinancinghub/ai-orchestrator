param(
  [string]$FrontRepo   = "carfinancinghub/cfh",
  [string]$OrchRepo    = "carfinancinghub/ai-orchestrator",
  [string]$OrchBranch  = "fix/restore-report-docs",
  [string]$FrontBase   = "",
  [string]$OrchBase    = ""
)

function Get-DefaultBranch {
  param([string]$RepoSlug)
  try {
    $name = gh repo view --repo $RepoSlug --json defaultBranchRef -q ".defaultBranchRef.name" 2>$null
    if ($LASTEXITCODE -eq 0 -and $name) { return $name.Trim() }
  } catch {}
  return "main"
}

function GetOrCreate-PR {
  param(
    [string]$RepoSlug, [string]$Head, [string]$Base,
    [string]$Title, [string]$Body
  )
  # 1) Try view by branch (works on new/old gh)
  try {
    $j = gh pr view --repo $RepoSlug $Head --json number,url,state,headRefName 2>$null | ConvertFrom-Json
    if ($j -and $j.url) { return $j }
  } catch {}

  # 2) Fallback: list & match by headRefName
  try {
    $list = gh pr list --repo $RepoSlug --state open --json number,url,headRefName 2>$null | ConvertFrom-Json
    if ($list) {
      $m = $list | Where-Object { $_.headRefName -eq $Head } | Select-Object -First 1
      if ($m) { return $m }
    }
  } catch {}

  # 3) Create (ALWAYS provide title/body; never rely on --fill)
  if (-not $Title) { $Title = "Auto PR: $Head -> $Base" }
  if (-not $Body)  { $Body  = "Automated publish for **$Head** into **$Base**." }

  $tmp = New-TemporaryFile
  Set-Content $tmp $Body -Encoding UTF8

  $args = @(
    "pr","create",
    "--repo",$RepoSlug,
    "--base",$Base,
    "--head",$Head,
    "--title",$Title,
    "--body-file",$tmp.FullName
  )

  $null = gh @args 2>$null

  # 4) Read again
  try {
    return (gh pr view --repo $RepoSlug $Head --json number,url,state,headRefName 2>$null | ConvertFrom-Json)
  } catch {
    return $null
  }
}

# ----- derive $stamp -----
$stamp = if ($env:stamp) { $env:stamp } else {
  $candidates = @(
    ".orchestrator\stamp.txt",
    "C:\Backup_Projects\CFH\frontend\.orchestrator\stamp.txt"
  )
  $val = $null
  foreach ($p in $candidates) {
    if (Test-Path $p) {
      $val = (Get-Content $p -ErrorAction SilentlyContinue)
      if ($val) { break }
    }
  }
  if (-not $val) {
    try {
      $fb = git -C "C:\Backup_Projects\CFH\frontend" rev-parse --abbrev-ref HEAD 2>$null
      if ($fb -match 'ts-migration/(\d{8}_\d{6})') { $val = $Matches[1] }
    } catch {}
  }
  if (-not $val) { $val = Get-Date -Format yyyyMMdd_HHmmss }
  $val
}

$FrontHead = "ts-migration/$stamp"
$summaryPath = "reports\debug\summary_links_$stamp.md"

# Resolve default branches if not provided
if (-not $FrontBase -or $FrontBase.Trim() -eq "") { $FrontBase = Get-DefaultBranch $FrontRepo }
if (-not $OrchBase  -or $OrchBase.Trim()  -eq "") { $OrchBase  = Get-DefaultBranch $OrchRepo  }

# Ensure summary exists
if (-not (Test-Path $summaryPath)) {
  New-Item -ItemType Directory -Force -Path (Split-Path $summaryPath) | Out-Null
  @"
# CFH Orchestrator — Links Summary ($stamp)

## Frontend repo (cfh)
- **Branch:** `$FrontHead`
- **Tree:** https://github.com/$FrontRepo/tree/$FrontHead
- **Frontend gates log:** https://github.com/$FrontRepo/blob/$FrontHead/reports/debug/frontend_build_test_lint_$stamp.md
- **Open PR (create):** https://github.com/$FrontRepo/pull/new/$FrontHead

## Orchestrator repo (ai-orchestrator)
- **Branch:** `$OrchBranch`
- **Tree:** https://github.com/$OrchRepo/tree/$OrchBranch
- **Open PR (create):** https://github.com/$OrchRepo/pull/new/$OrchBranch
"@ | Set-Content $summaryPath -Encoding UTF8
}

# ----- Create/view PRs -----
$frontPR = GetOrCreate-PR -RepoSlug $FrontRepo -Head $FrontHead -Base $FrontBase -Title "TS migration: $stamp" -Body "Automated PR for TS migration batch $stamp."
$orchPR  = GetOrCreate-PR -RepoSlug $OrchRepo  -Head $OrchBranch -Base $OrchBase -Title "Orchestrator: restore report docs" -Body "Automated PR."

if (-not $frontPR -or -not $frontPR.url) { throw "Could not create/view frontend PR" }
if (-not $orchPR  -or -not $orchPR.url)  { throw "Could not create/view orchestrator PR" }

# ----- Stamp PR links into summary -----
$content = Get-Content $summaryPath -Raw
$content = $content -replace 'Open PR \(create\): https://github.com/carfinancinghub/cfh/pull/new/.+',
  ("PR: {0}" -f $frontPR.url)
$content = $content -replace 'Open PR \(create\): https://github.com/carfinancinghub/ai-orchestrator/pull/new/.+',
  ("PR: {0}" -f $orchPR.url)
Set-Content $summaryPath $content -Encoding UTF8

git add $summaryPath | Out-Null
git commit -m ("docs: add PR urls to summary [{0}]" -f $stamp) | Out-Null
git push | Out-Null

"Summary URL:"
"https://github.com/$OrchRepo/blob/$OrchBranch/$($summaryPath -replace '\\','/')"
