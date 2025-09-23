<# 
Upload batch artifacts summary to a PR, with optional commit/push within the same repo.

Usage examples:
  # Same-repo (ai-orchestrator) commit+push+comment
  pwsh -File scripts\upload_to_github.ps1 -Pr 4 -AttachReports

  # Cross-repo comment only (CFH PR #17), no git operations
  pwsh -File scripts\upload_to_github.ps1 -Pr 17 -Repo 'carfinancinghub/cfh' -AttachReports -CommentOnly
#>

param(
  [Parameter(Mandatory=$true)]
  [int]$Pr,
  [switch]$AttachReports,
  [string]$Repo = 'carfinancinghub/ai-orchestrator',
  [switch]$CommentOnly
)

$ErrorActionPreference = 'Stop'
$repo = $Repo

function _exists($p) { Test-Path $p -PathType Leaf -or Test-Path $p -PathType Container }

Write-Host "Reading PR #$Pr in repo $repo…" -ForegroundColor Cyan
$prInfo = gh pr view $Pr --repo $repo --json number,state,mergeable,headRefName,baseRefName,headRepository,files `
  --jq '{num:.number,state:.state,mergeable:.mergeable,head:.headRefName,base:.baseRefName,files:[.files[].path]}' | ConvertFrom-Json

if (-not $prInfo) { throw "Unable to get PR info for $repo #$Pr" }

$head = $prInfo.head
Write-Host "PR #$($prInfo.num) state=$($prInfo.state) mergeable=$($prInfo.mergeable) head=$head base=$($prInfo.base)" -ForegroundColor Gray

# Collect run metadata from current workspace (ai-orchestrator)
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

if (-not $CommentOnly) {
  # Same-repo: do commit/push on PR head branch in the current repo
  Write-Host "Same-repo mode: committing to $repo on branch $head" -ForegroundColor Cyan
  git fetch origin $head | Out-Null
  git checkout $head 2>$null | Out-Null

  $toAdd = @()
  if (Test-Path $genRoot) { $toAdd += $genRoot }
  if ($AttachReports) {
    $candSel = 'reports\selected_candidates_25.txt'
    $gates   = Get-ChildItem 'reports' -File -Filter 'gates_*.json' -ErrorAction SilentlyContinue
    $debugs  = Get-ChildItem 'reports\debug' -File -Filter 'run_candidates_*.json' -ErrorAction SilentlyContinue
    $feedMd  = 'reports\feed_review_20250922.md'
    foreach($p in @($candSel, $feedMd)) { if (_exists $p) { $toAdd += $p } }
    if ($gates)  { $toAdd += $gates.FullName }
    if ($debugs) { $toAdd += $debugs.FullName }
  }

  if ($toAdd.Count -eq 0) {
    Write-Warning "Nothing to add. Skipping commit/push."
  } else {
    git add -- $toAdd
  }

  $hasStaged = (git diff --cached --name-only).Length -gt 0
  if ($hasStaged) {
    $msg = "chore(ts): add batch artifacts (run $runId) — $genCount files; $reviewCount reviews"
    git commit -m $msg
    Write-Host "Committed: $msg" -ForegroundColor Green
    git push origin $head | Out-Null
  } else {
    Write-Host "No staged changes to commit." -ForegroundColor Yellow
  }
} else {
  Write-Host "Comment-only mode: will not git commit/push (target repo $repo)." -ForegroundColor Yellow
}

# PR comment + labels (works cross-repo)
New-Item -ItemType Directory -Force -Path 'reports\debug' | Out-Null
$tmp = New-Item -ItemType File -Path ("reports\debug\pr_comment_{0}.md" -f $runId) -Force
@"
**Cod1 Batch Upload** — run \`$runId\`

- Generated TS/TSX files: **$genCount** (from ai-orchestrator workspace)
- Review JSONs: **$reviewCount** (under \`artifacts/reviews/$runId/\`)
- Selected candidates: \`reports/selected_candidates_25.txt\` $((Test-Path 'reports\selected_candidates_25.txt') ? '' : '(missing)')
- Gates reports (if any): \`reports/gates_*.json\`

_Labels:_ \`finalization\`, \`cfh-enhance\`, \`ts-batch-25\`
"@ | Set-Content $tmp -Encoding UTF8

gh pr comment $Pr --repo $repo --body-file $tmp.FullName
gh pr edit $Pr --repo $repo --add-label finalization
gh pr edit $Pr --repo $repo --add-label cfh-enhance
gh pr edit $Pr --repo $repo --add-label ts-batch-25

Write-Host "Posted PR comment + labels to $repo #$Pr." -ForegroundColor Green
