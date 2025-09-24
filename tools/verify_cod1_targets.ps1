param(
  [string]$Branch = "main",
  [string]$OutDir = ".\reports\debug"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# 1) Repo + remote → URL base
$RepoRoot = (git rev-parse --show-toplevel).Trim()
$Remote   = (git config --get remote.origin.url)
if ($Remote -match 'github\.com[:/](.+?)/(.+?)(\.git)?$') {
  $Org = $Matches[1]; $RepoName = $Matches[2]
} else { throw "Remote URL not recognized as GitHub: $Remote" }
$BaseUrl = "https://github.com/$Org/$RepoName/blob/$Branch/"

# 2) Canonical list of files/folders to verify (root-relative, leading slash optional)
$Targets = @(
  ".gitattributes",
  ".gitignore",
  "scripts/check-no-js.ps1",
  "scripts/check-no-vendor.ps1",
  ".github/workflows/ci.yml",
  ".github/workflows/cfh-lint.yml",
  "scripts/cfh_lint.ps1",
  "scripts/cfh_lint_local.ps1",
  "scripts/run_candidates.ps1",
  "tools/gen_grouped_files.py",
  "tools/inventory_scan.py",
  "app/ops.py",
  "app/synthesize-ts.mjs",
  "reports/ai_review_20250923_084351.md",
  "reports/ai_reviews.md"
)

# 3) Evaluate
$rows = foreach ($rel in $Targets) {
  $rel = $rel.TrimStart("/\")
  $fsPath = Join-Path $RepoRoot $rel
  $exists = Test-Path $fsPath
  $isDir  = $false
  $size   = $null
  $sha1   = $null
  if ($exists) {
    $item = Get-Item $fsPath
    $isDir = $item.PSIsContainer
    if (-not $isDir) {
      $size = $item.Length
      $sha1 = (Get-FileHash -Algorithm SHA1 $fsPath).Hash
    }
  }
  $url = $BaseUrl + ($rel -replace '\\','/')
  [pscustomobject]@{
    Path   = $rel
    Exists = $exists
    IsDir  = $isDir
    Size   = $size
    SHA1   = $sha1
    URL    = $url
  }
}

# 4) Output: console + CSV + Markdown
$rows | Sort-Object Path | Format-Table -AutoSize

$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$csv   = Join-Path $OutDir "cod1_validation_results_$stamp.csv"
$md    = Join-Path $OutDir "cod1_validation_results_$stamp.md"

$rows | Sort-Object Path | Export-Csv -NoTypeInformation -Encoding UTF8 $csv

# Simple Markdown report with checkmarks and links
$mdBody = @("# Cod1 Validation Results — $stamp", "", "| Path | Exists | Size | SHA1 | Link |",
            "|---|:---:|---:|---|---|")
foreach ($r in ($rows | Sort-Object Path)) {
  $ok = if ($r.Exists) { "✅" } else { "❌" }
  $size = if ($r.IsDir) { "(dir)" } else { ($r.Size ?? "") }
  $sha  = $r.SHA1 ?? ""
  $link = "[open]($($r.URL))"
  $mdBody += "| `$($r.Path)` | $ok | $size | `$sha` | $link |"
}
$mdBody -join "`r`n" | Set-Content -Encoding UTF8 $md

"Saved: $csv"
"Saved: $md"
