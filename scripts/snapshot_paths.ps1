param([string]$Root = "C:\c\ai-orchestrator", [int]$MaxSampleBytes = 4096)
$ErrorActionPreference = "Stop"

# Resolve & prepare
$Root    = (Resolve-Path $Root).Path
$Reports = Join-Path $Root "reports"
New-Item -ItemType Directory -Force -Path $Reports | Out-Null

# 1) Run inventory (prunes node_modules, backups, etc.)
$env:CFH_SCAN_ROOT        = $Root
$env:CFH_REPORTS_DIR      = $Reports
$env:CFH_MAX_SAMPLE_BYTES = "$MaxSampleBytes"
python "$Root\tools\inventory_scan.py" --root "$Root" | Tee-Object -FilePath (Join-Path $Reports "snapshot_log.txt") -Append

# 2) Extract filesystem paths (robust for empty-key JSON via -AsHashTable)
$invPath   = Join-Path $Reports "inventory_index.json"
$pathsFs   = Join-Path $Reports "paths_fs.txt"
if (Test-Path $invPath) {
  $inv = Get-Content $invPath -Raw | ConvertFrom-Json -AsHashTable
  $inv['files'] | ForEach-Object { $_['path'] } | Sort-Object | Set-Content $pathsFs -Encoding UTF8
}

# 3) Git-tracked paths (if repo + git)
$pathsGit = Join-Path $Reports "paths_git.txt"
if (Get-Command git -ErrorAction SilentlyContinue) {
  try {
    git -C $Root rev-parse --is-inside-work-tree *> $null
    git -C $Root ls-files | Sort-Object | Set-Content $pathsGit -Encoding UTF8
  } catch {}
}

# 4) Combine snapshot
$pathsSnapshot = Join-Path $Reports "paths_snapshot.txt"
"### ai-orchestrator paths snapshot" | Set-Content $pathsSnapshot -Encoding UTF8
"root: $Root"                      | Add-Content $pathsSnapshot
"generated: $(Get-Date -Format o)" | Add-Content $pathsSnapshot
if (Test-Path $pathsFs)  { "`n-- filesystem (pruned) --" | Add-Content $pathsSnapshot; Get-Content $pathsFs  | Add-Content $pathsSnapshot }
if (Test-Path $pathsGit) { "`n-- git tracked --"         | Add-Content $pathsSnapshot; Get-Content $pathsGit | Add-Content $pathsSnapshot }

# 5) Create or update secret Gist with gh (one -a per file)
$files = @(
  $pathsSnapshot,
  (Join-Path $Reports "tree.txt"),
  (Join-Path $Reports "code_counts_by_ext.json"),
  $invPath
) | Where-Object { Test-Path $_ }

$gistIdPath = Join-Path $Reports ".gist_id.txt"
$gistUrlPath= Join-Path $Reports ".gist_url.txt"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  Write-Host "⚠️ GitHub CLI 'gh' not found. Skipping upload. Files written to $Reports"
  Write-Host "   Install: winget install GitHub.cli  then run: gh auth login"
  exit 0
}

# Ensure we have gist auth
try { gh auth status --show-token *> $null } catch {
  Write-Host "⚠️ Not authenticated for GitHub CLI. Run: gh auth login (allow 'gist' scope)"; exit 1
}

if (Test-Path $gistIdPath) {
  $id = (Get-Content $gistIdPath -Raw).Trim()
  foreach ($f in $files) {
    gh gist edit $id -a $f | Out-Null
  }
  $url = (Get-Content $gistUrlPath -Raw).Trim()
} else {
  $desc = "ai-orchestrator paths snapshot $(Get-Date -Format o)"
  $url  = (gh gist create $files -d $desc | Select-Object -Last 1).Trim()
  $id   = ($url -split "/")[-1]
  $url | Set-Content $gistUrlPath
  $id  | Set-Content $gistIdPath
}

if (Get-Command Set-Clipboard -ErrorAction SilentlyContinue) { Set-Clipboard -Value $url }
Write-Host "✅ Gist URL: $url"
Write-Host "   (also saved to $gistUrlPath ; id -> $gistIdPath)"
