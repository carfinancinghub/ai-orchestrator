# scripts\gh_tree_and_bootstrap.ps1
param(
  [string]$AIO = (Resolve-Path ".").Path,
  [string]$ScriptsDir = ".\scripts",
  [string]$SourceDir  = ".\tools\cod1",
  [switch]$BootstrapMissing,     # create only what's missing
  [switch]$Force,                # allow overwrite (default: no)
  [switch]$OpenReport            # open the generated tree report
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location $AIO

# --- expected layout -----------------------------------------------------------
$ExpectedDirs = @(
  "app",
  "scripts",
  "tools\cod1",
  "reports",
  "artifacts\generated",
  "artifacts\reviews"
)

$ExpectedScripts = @(
  "lists_plus_roots_to_candidates.ps1",
  "zips_to_candidates.ps1",
  "postfilter_and_autopin.ps1",
  "run_candidates.ps1",
  "prune.ps1",
  "check_missing.ps1",
  "check_remaining.ps1"
)

# --- helper: write file safely ------------------------------------------------
function Write-FileIfMissing {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Content,
    [switch]$Force
  )
  $dest = Resolve-Path -LiteralPath (Split-Path -Parent $Path) -EA SilentlyContinue
  if (-not $dest) { New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null }

  if ((Test-Path $Path) -and -not $Force) {
    Write-Host "skip (exists): $Path"
    return
  }
  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText((Resolve-Path (Split-Path -Parent $Path)).Path + "\" + (Split-Path -Leaf $Path), $Content, $enc)
  Write-Host "wrote: $Path"
}

# --- templates for helper scripts (only used if missing) ----------------------
$TemplatePrune = @'
param(
  [string]$AIO = (Resolve-Path ".").Path,
  [string]$FeedPath    = ".\reports\conversion_candidates.txt",
  [string]$GeneratedDir= ".\artifacts\generated"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location $AIO

$feed = @(Get-Content $FeedPath -EA SilentlyContinue | Where-Object { $_ })
$genStems = @()
if (Test-Path $GeneratedDir) {
  $genStems = Get-ChildItem $GeneratedDir -Recurse -File -Include *.ts,*.tsx -EA SilentlyContinue |
    ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.Name).ToLower() } |
    Sort-Object -Unique
}

$keep = foreach ($p in $feed) {
  if (-not (Test-Path $p)) { continue }
  $stem = [IO.Path]::GetFileNameWithoutExtension([IO.Path]::GetFileName($p)).ToLower()
  if ($stem -notin $genStems) { $p }
}

$keep | Set-Content $FeedPath -Encoding UTF8

"== prune summary =="
"feed before      : $($feed.Count)"
"generated stems  : $($genStems.Count)"
"feed after       : $($keep.Count)"
'@

$TemplateCheckMissing = @'
param(
  [string]$AIO = (Resolve-Path ".").Path,
  [string]$FeedPath = ".\reports\conversion_candidates.txt"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location $AIO

$feed    = @(Get-Content $FeedPath -EA SilentlyContinue | Where-Object { $_ })
$missing = $feed | Where-Object { -not (Test-Path $_) }

"feed count : $($feed.Count)"
"missing    : $($missing.Count)"
$missing | Select-Object -First 50
'@

$TemplateCheckRemaining = @'
param(
  [string]$AIO = (Resolve-Path ".").Path,
  [string]$FeedPath = ".\reports\conversion_candidates.txt",
  [string]$GeneratedDir = ".\artifacts\generated"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location $AIO

$feed = @(Get-Content $FeedPath -EA SilentlyContinue | Where-Object { $_ })
$genStems = @()
if (Test-Path $GeneratedDir) {
  $genStems = Get-ChildItem $GeneratedDir -Recurse -File -Include *.ts,*.tsx -EA SilentlyContinue |
    ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.Name).ToLower() } |
    Sort-Object -Unique
}

$need = foreach ($p in $feed) {
  if (-not (Test-Path $p)) { continue }
  $stem = [IO.Path]::GetFileNameWithoutExtension([IO.Path]::GetFileName($p)).ToLower()
  if ($stem -notin $genStems) { $p }
}

"feed total : $($feed.Count)"
"generated  : $($genStems.Count)"
"need       : $($need.Count)"
$need | Select-Object -First 50
'@

# --- build filtered tree ------------------------------------------------------
$Reports = Join-Path $AIO "reports"
New-Item -ItemType Directory -Force -Path $Reports | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$treeTxt = Join-Path $Reports "repo_tree_$stamp.txt"
$treeMd  = Join-Path $Reports "repo_tree_$stamp.md"

# Exclude these directories from the tree (regex over full Windows paths)
$ExcludeDirPatterns = '(?i)' + (@(
  '\\\.git(\\|$)'              # \.git\
  '\\node_modules(\\|$)'       # \node_modules\
  '\\\.venv(\\|$)'             # \.venv\
  '\\__pycache__(\\|$)'        # \__pycache__\
  '\\\.pytest_cache(\\|$)'     # \.pytest_cache\
  '\\\.mypy_cache(\\|$)'       # \.mypy_cache\
  '\\dist(\\|$)'               # \dist\
  '\\build(\\|$)'              # \build\
  '\\artifacts\\zip_stage(\\|$)' # \artifacts\zip_stage\
  '\\reports\\debug(\\|$)'     # \reports\debug\
) -join '|')

$rel = {
  param($p)
  $rp = $p.FullName.Substring($AIO.Length).TrimStart('\','/')
  if (-not $rp) { '.' } else { $rp -replace '\\','/' }
}

$items = Get-ChildItem -Recurse -Force -EA SilentlyContinue | Where-Object {
  $_.FullName -notmatch $ExcludeDirPatterns
}

$paths = $items | ForEach-Object { & $rel $_ } | Sort-Object -Unique
"Repo: $AIO" | Set-Content $treeTxt -Encoding UTF8
$paths | Add-Content $treeTxt -Encoding UTF8

@"
# Repo Tree ($stamp)

\`\`\`
$AIO
$($paths -join "`r`n")
\`\`\`
"@ | Set-Content $treeMd -Encoding UTF8

Write-Host "tree -> $treeTxt"
Write-Host "tree -> $treeMd"
if ($OpenReport) { Start-Process $treeMd | Out-Null }

# --- verify required dirs/files ----------------------------------------------
Write-Host "`n== audit: required folders ==" -ForegroundColor Cyan
foreach ($d in $ExpectedDirs) {
  if (Test-Path $d) { "ok   $d" } else { "MISS $d" }
}

Write-Host "`n== audit: required scripts in $ScriptsDir ==" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $ScriptsDir | Out-Null

$needCreate = @()
foreach ($s in $ExpectedScripts) {
  $dest = Join-Path $ScriptsDir $s
  if (Test-Path $dest) {
    "ok   $dest"
  } else {
    "MISS $dest"
    $needCreate += $s
  }
}

if ($BootstrapMissing -and $needCreate.Count -gt 0) {
  Write-Host "`n== bootstrap missing (no overwrite) ==" -ForegroundColor Yellow
  foreach ($s in $needCreate) {
    $dest = Join-Path $ScriptsDir $s
    $src  = Join-Path $SourceDir $s

    if (Test-Path $src) {
      if ((Test-Path $dest) -and -not $Force) {
        Write-Host "skip copy (exists): $dest"
      } else {
        Copy-Item $src $dest -Force:$Force
        Write-Host "copied $s -> $dest"
      }
    } else {
      # create templates for helper scripts only
      switch ($s) {
        "prune.ps1"           { Write-FileIfMissing -Path $dest -Content $TemplatePrune -Force:$Force }
        "check_missing.ps1"   { Write-FileIfMissing -Path $dest -Content $TemplateCheckMissing -Force:$Force }
        "check_remaining.ps1" { Write-FileIfMissing -Path $dest -Content $TemplateCheckRemaining -Force:$Force }
        default {
          Write-Host "WARN: no source for $s in $SourceDir and no template available."
        }
      }
    }
  }
}

# ensure app/__init__.py (so 'app' is a package)
if (-not (Test-Path ".\app\__init__.py")) {
  New-Item -ItemType Directory -Force -Path ".\app" | Out-Null
  New-Item -ItemType File -Force -Path ".\app\__init__.py" | Out-Null
  Write-Host "created app\__init__.py"
}

Write-Host "`n== done =="
