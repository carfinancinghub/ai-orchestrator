<# 
Upload batch artifacts summary to a PR, with optional commit/push (same-repo only).

Examples:
  # Same-repo (ai-orchestrator) commit+push+comment
  pwsh -File scripts\upload_to_github.ps1 -Pr 4 -AttachReports

  # Cross-repo comment only (CFH PR #17), no git writes
  pwsh -File scripts\upload_to_github.ps1 -Pr 17 -Repo 'carfinancinghub/cfh' -AttachReports -CommentOnly
#>

param(
  [Parameter(Mandatory=$true)]
  [int]$prInfo,

  [switch]$AttachReports,

  # Default to current repo (ai-orchestrator) unless cross-posting
  [string]$Repo = 'carfinancinghub/ai-orchestrator',

  # When set, do NOT git commit/push; just post comment + labels to the PR
  [switch]$CommentOnly
)

# -----------------------------
# helpers
# -----------------------------
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
$prInfo = Get-PrInfo -Num $Pr -R $Repo
$head   = $prInfo.head
Write-Host ("PR #{0}  state={1}  mergeable={2}  head={3}  base={4}" -f $prInfo.num,$prInfo.state,$prInfo.mergeable,$prInfo.head,$prInfo.base) -ForegroundColor Gray

