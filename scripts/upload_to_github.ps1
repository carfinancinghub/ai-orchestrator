<#
Upload batch artifacts summary to a PR, with optional commit/push (same-repo only).

Examples:
  # Same-repo (ai-orchestrator) commit+push+comment
  pwsh -File scripts\upload_to_github.ps1 -PRNumber 4 -AttachReports

  # Cross-repo comment only (CFH PR #17), no git writes
  pwsh -File scripts\upload_to_github.ps1 -PRNumber 17 -Repo 'carfinancinghub/cfh' -AttachReports -CommentOnly
#>

param(
  [Parameter(Mandatory=$true)]
  [int]$PRNumber,

  [switch]$AttachReports,

  # Default to current repo (ai-orchestrator) unless cross-posting
  [string]$Repo = 'carfinancinghub/ai-orchestrator',

  # When set, do NOT git commit/push; just post comment + labels to the PR
  [switch]$CommentOnly
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg){ Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg){ Write-Host $msg -ForegroundColor Green }
function Write-Warn($msg){ Write-Host $msg -ForegroundColor Yellow }
function Write-Err($msg){ Write-Host $msg -ForegroundColor Red }
function _exists($p){ Test-Path $p -PathType Leaf -or Test-Path $p -PathType Container }

function Get-PrInfo([int]$Num, [string]$R){
  Write-Info ("Reading PR #{0} in repo {1}…" -f $Num, $R)
  try {
    $raw = gh pr view $Num --repo $R --json number,state,mergeable,headRefName,baseRefName,files
    if (-not $raw) { throw "Empty PR info" }
    $o = $raw | ConvertFrom-Json
    [pscustomobject]@{
      num       = $o.number
      state     = $o.state
      mergeable = $o.mergeable
      head      = $o.headRefName
      base      = $o.baseRefName
      files     = @($o.files | ForEach-Object { $_.path })
    }
  } catch {
    throw ("Unable to get PR info for {0} #{1}. {2}" -f $R, $Num, $_)
  }
}

function Ensure-Labels([string]$R, [string[]]$Labels){
  try {
    $have = gh label list --repo $R --json name --jq '.[].name' 2>$null
  } catch {
    Write-Warn ("Could not list labels for {0}: {1}" -f $R, $_)
    $have = @()
  }
  foreach($n in $Labels){
    if ($have -notcontains $n){
      try {
        gh label create $n --repo $R --color 5319e7 --description "auto-created by uploader" | Out-Null
      } catch {
        Write-Warn ("Could not create label '{0}' in {1}: {2}" -f $n, $R, $_)
      }
    }
  }
}

function Add-Labels([int]$Num, [string]$R, [string[]]$Labels){
  foreach($n in $Labels){
    try {
      gh pr edit $Num --repo $R --add-label $n | Out-Null
    } catch {
      Write-Warn ("Could not add label '{0}' to PR #{1}: {2}" -f $n, $Num, $_)
    }
  }
}

# -----------------------------
# collect run metadata (local)
# -----------------------------
$runIdPath = Join-Path 'reports' 'latest_run_id.txt'
$runId = (Get-Content $runIdPath -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $runId) { $runId = (Get-Date -Format 'yyyyMMdd_HHmmss') }

$reviewRoot = Join-Path 'artifacts\reviews' $runId
$reviewCount = 0
if (Test-Path $reviewRoot) {
  $reviewCount = (Get-ChildItem $reviewRoot -Recurse -File -Include *.json | Where-Object { $_.Length -gt 3 }).Count
}

$genRoot = 'artifacts\generated'
$genCount = (Test-Path $genRoot) ? ((Get-ChildItem $genRoot -Recurse -File -Include *.ts,*.tsx).Count) : 0

# -----------------------------
# PR info
# -----------------------------
$prInfo = Get-PrInfo -Num $PRNumber -R $Repo
$head   = $prInfo.head
Write-Host ("PR #{0}  state={1}  mergeable={2}  head={3}  base={4}" -f $prInfo.num,$prInfo.state,$prInfo.mergeable,$prInfo.head,$prInfo.base) -ForegroundColor Gray

# -----------------------------
# same-repo commit/push (optional)
# -----------------------------
if (-not $CommentOnly -and $Repo -eq 'carfinancinghub/ai-orchestrator') {
  Write-Info ("Same-repo mode: committing to {0} on branch {1}" -f $Repo, $head)
  try {
    git fetch origin $head | Out-Null
    git checkout $head 2>$null | Out-Null
  } catch {
    Write-Warn ("Could not checkout branch {0}: {1}" -f $head, $_)
  }

  $toAdd = @()
  if (Test-Path $genRoot) { $toAdd += $genRoot }
  if ($AttachReports) {
    $candSel = 'reports\selected_candidates_25.txt'
    $feedMd  = 'reports\feed_review_20250922.md'
    $gates   = Get-ChildItem 'reports' -File -Filter 'gates_*.json' -ErrorAction SilentlyContinue
    $debugs  = Get-ChildItem 'reports\debug' -File -Filter 'run_candidates_*.json' -ErrorAction SilentlyContinue
    foreach($p in @($candSel, $feedMd)) { if (_exists $p) { $toAdd += $p } }
    if ($gates)  { $toAdd += $gates.FullName }
    if ($debugs) { $toAdd += $debugs.FullName }
  }

  if ($toAdd.Count -gt 0) { git add -- $toAdd }
  $hasStaged = ((git diff --cached --name-only) | Measure-Object).Count -gt 0
  if ($hasStaged) {
    $msg = "chore(ts): add batch artifacts (run $runId) — $genCount files; $reviewCount reviews"
    git commit -m $msg | Out-Null
    Write-Ok ("Committed: {0}" -f $msg)
    git push origin $head | Out-Null
  } else {
    Write-Warn "No staged changes to commit."
  }
} else {
  Write-Warn ("Comment-only mode: no git writes. Target repo: {0}" -f $Repo)
}

# -----------------------------
# PR comment body + labels
# -----------------------------
New-Item -ItemType Directory -Force -Path 'reports\debug' | Out-Null
$tmp = New-Item -ItemType File -Path ("reports\debug\pr_comment_{0}.md" -f $runId) -Force

$labels = @('finalization','cfh-enhance','ts-batch-25')
$body = @"
**Cod1 Batch Upload** — run \`$runId\`

- Generated TS/TSX files: **$genCount**
- Review JSONs: **$reviewCount** (under \`artifacts/reviews/$runId/\`)
- Selected candidates: \`reports/selected_candidates_25.txt\` $((Test-Path 'reports\selected_candidates_25.txt') ? '' : '(missing)')
- Gate reports (if any): \`reports/gates_*.json\`

_Labels:_ \`$($labels -join '`, `')\`
"@
$body | Set-Content $tmp -Encoding UTF8

Ensure-Labels -R $Repo -Labels $labels
Add-Labels -Num $PRNumber -R $Repo -Labels $labels

try {
  gh pr comment $PRNumber --repo $Repo --body-file $tmp.FullName | Out-Null
  Write-Ok ("Posted PR comment + labels to {0} #{1}." -f $Repo, $PRNumber)
} catch {
  Write-Warn ("Could not post PR comment: {0}" -f $_)
}
