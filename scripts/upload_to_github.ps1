<# 
Upload batch artifacts summary to a PR, with optional commit/push in the same repo.

Usage examples:
  # Same-repo (ai-orchestrator) commit + push + comment
  pwsh -File scripts\upload_to_github.ps1 -Pr 4 -AttachReports

  # Cross-repo comment-only (CFH PR #17), no git operations
  pwsh -File scripts\upload_to_github.ps1 -Pr 17 -Repo 'carfinancinghub/cfh' -AttachReports -CommentOnly
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [int]$Pr,

  [switch]$AttachReports,

  # Target repository in "owner/name" form
  [string]$Repo = 'carfinancinghub/ai-orchestrator',

  # If set, skip any git checkout/add/commit/push. Only comment/labels will be posted.
  [switch]$CommentOnly
)

$ErrorActionPreference = 'Stop'

function Write-Info([string]$msg)  { Write-Host $msg -ForegroundColor Cyan }
function Write-Warn([string]$msg)  { Write-Warning $msg }
function Write-Good([string]$msg)  { Write-Host $msg -ForegroundColor Green }
function Path-Exists($p)           { Test-Path $p -PathType Leaf -or Test-Path $p -PathType Container }

# ---- 1) Read PR info ---------------------------------------------------------
Write-Info "Reading PR #$Pr in repo $Repo…"
try {
  $prInfo = gh pr view $Pr --repo $Repo --json number,state,mergeable,headRefName,baseRefName,headRepository,files `
    --jq '{num:.number,state:.state,mergeable:.mergeable,head:.headRefName,base:.baseRefName,files:[.files[].path]}'
  if (-not $prInfo) { throw "Empty PR info" }
  $pr = $prInfo | ConvertFrom-Json
} catch {
  throw "Unable to get PR info for $Repo #$Pr. $_"
}

$head = $pr.head
Write-Host ("PR #{0}  state={1}  mergeable={2}  head={3}  base={4}" -f $pr.num,$pr.state,$pr.mergeable,$pr.head,$pr.base) -ForegroundColor Gray

# ---- 2) Collect run metadata from current workspace (ai-orchestrator) --------
$runIdPath  = Join-Path 'reports' 'latest_run_id.txt'
$runId      = (Get-Content $runIdPath -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $runId) { $runId = (Get-Date -Format 'yyyyMMdd_HHmmss') }

$genRoot    = 'artifacts\generated'
$reviewRoot = Join-Path 'artifacts\reviews' $runId

$genCount   = (Path-Exists $genRoot)    ? ((Get-ChildItem $genRoot -Recurse -File -Include *.ts,*.tsx).Count) : 0
$reviewCount= (Path-Exists $reviewRoot) ? ((Get-ChildItem $reviewRoot -Recurse -File -Include *.json | Where-Object { $_.Length -gt 3 }).Count) : 0

# ---- 3) Same-repo commit/push (skipped in CommentOnly mode) ------------------
if (-not $CommentOnly) {
  Write-Info "Same-repo mode: committing to $Repo on branch $head"

  try {
    git fetch origin $head | Out-Null
    git checkout $head 2>$null | Out-Null
  } catch {
    Write-Warn "Unable to checkout branch '$head'. Continuing in comment-only mode."
    $CommentOnly = $true
  }

  if (-not $CommentOnly) {
    $toAdd = @()
    if (Path-Exists $genRoot) { $toAdd += $genRoot }

    if ($AttachReports) {
      $candSel = 'reports\selected_candidates_25.txt'
      $feedMd  = 'reports\feed_review_20250922.md'
      $gates   = Get-ChildItem 'reports' -File -Filter 'gates_*.json' -ErrorAction SilentlyContinue
      $debugs  = Get-ChildItem 'reports\debug' -File -Filter 'run_candidates_*.json' -ErrorAction SilentlyContinue

      foreach($p in @($candSel, $feedMd)) { if (Path-Exists $p) { $toAdd += $p } }
      if ($gates)  { $toAdd += $gates.FullName }
      if ($debugs) { $toAdd += $debugs.FullName }
    }

    if ($toAdd.Count -gt 0) { git add -- $toAdd } else { Write-Warn "Nothing to add. Skipping commit/push." }

    $hasStaged = ((git diff --cached --name-only) | Measure-Object).Count -gt 0
    if ($hasStaged) {
      $msg = "chore(ts): add batch artifacts (run $runId) — $genCount files; $reviewCount reviews"
      git commit -m $msg | Out-Null
      Write-Good "Committed: $msg"
      git push origin $head | Out-Null
      Write-Good "Pushed to origin/$head"
    } else {
      Write-Host "No staged changes to commit." -ForegroundColor Yellow
    }
  }
} else {
  Write-Host "Comment-only mode: will not git commit/push (target repo $Repo)." -ForegroundColor Yellow
}

# ---- 4) Post PR comment ------------------------------------------------------
New-Item -ItemType Directory -Force -Path 'reports\debug' | Out-Null
$tmp = "reports\debug\pr_comment_$runId.md"

@"
**Cod1 Batch Upload** — run `$runId`

- Generated TS/TSX files: **$genCount** (from ai-orchestrator workspace)
- Review JSONs: **$reviewCount** (under `artifacts/reviews/$runId/`)
- Selected candidates: `reports/selected_candidates_25.txt` $((Test-Path 'reports\selected_candidates_25.txt') ? '' : '(missing)')
- Gates reports (if any): `reports/gates_*.json`
"@ | Set-Content $tmp -Encoding UTF8

try {
  gh pr comment $Pr --repo $Repo --body-file $tmp | Out-Null
  Write-Good "Posted PR comment to $Repo #$Pr."
} catch {
  Write-Warn "Failed to post PR comment: $_"
}

# ---- 5) Ensure labels exist, then add them (idempotent) ----------------------
$desiredLabels = @(
  @{ name = 'finalization'; color = '2ea043'; desc = 'Ready for final polish/merge' },
  @{ name = 'cfh-enhance';  color = '0e8a16'; desc = 'CFH-specific enhancement'   },
  @{ name = 'ts-batch-25';  color = '5319e7'; desc = 'TS migration batch (≤25 files)' }
)

try {
  $have = gh label list --repo $Repo --json name --jq '.[].name'
} catch {
  $have = @()
  Write-Warn "Could not list labels for $Repo: $_"
}

foreach($lbl in $desiredLabels){
  $n = $lbl.name
  if ($have -notcontains $n) {
    try {
      gh label create $n --repo $Repo --color $lbl.color --description $lbl.desc 2>$null | Out-Null
      Write-Good "Created label '$n' in $Repo."
    } catch {
      Write-Warn "Could not create label '$n' (may already exist or insufficient perms): $_"
    }
  }
}

foreach($n in $desiredLabels.name){
  try {
    gh pr edit $Pr --repo $Repo --add-label $n | Out-Null
  } catch {
    Write-Warn "Could not add label '$n' to PR #$Pr: $_"
  }
}

Write-Good "Posted PR comment + labels to $Repo #$Pr."
