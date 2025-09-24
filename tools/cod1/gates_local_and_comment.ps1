param(
  [string]$AIO       = "C:\c\ai-orchestrator",
  [string]$Frontend  = "C:\Backup_Projects\CFH\frontend",
  [string]$RunId     = ""    # optional; autodetects newest if empty
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

# --- helpers ---
function Get-LatestRunId {
  $candidates = @()
  if (Test-Path "artifacts\reviews")     { $candidates += (Get-ChildItem "artifacts\reviews" -Directory | Select-Object -ExpandProperty Name) }
  if (Test-Path "artifacts\suggestions") { $candidates += (Get-ChildItem "artifacts\suggestions" -Directory | Select-Object -ExpandProperty Name) }
  $candidates = $candidates | Where-Object { $_ -match '^\d{8}_\d{6}$' } | Sort-Object -Descending
  if ($candidates.Count -gt 0) { return $candidates[0] } else { return "" }
}

function Run-Step {
  param([string]$CmdLine, [string]$Cwd)
  try {
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = "powershell.exe"
    $pinfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command `"& { $CmdLine }`""
    $pinfo.WorkingDirectory = $Cwd
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardError = $true
    $pinfo.UseShellExecute = $false
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $pinfo
    [void]$proc.Start()
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    $exit = $proc.ExitCode
    if ($stdout.Length -gt 10000) { $stdout = $stdout.Substring($stdout.Length - 10000) }
    if ($stderr.Length -gt 10000) { $stderr = $stderr.Substring($stderr.Length - 10000) }
    return @{
      cmd   = $CmdLine
      exit  = $exit
      stdout= $stdout
      stderr= $stderr
      pass  = ($exit -eq 0)
    }
  } catch {
    return @{ cmd=$CmdLine; exit=1; stdout=""; stderr="$($_.Exception.Message)"; pass=$false }
  }
}

# --- pick run id ---
if (-not $RunId -or $RunId.Trim() -eq "") { $RunId = Get-LatestRunId }
if (-not $RunId) { throw "Could not resolve a RunId. Upload first so reports\upload_<run>.txt exists." }

# --- ensure reports dir ---
$reports = Join-Path $AIO "reports"
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$gatesPath = Join-Path $reports ("gates_{0}.json" -f $RunId)

# --- run gates locally (npm) ---
$npm = if ($env:AIO_NPM_BIN) { $env:AIO_NPM_BIN } else { "npm" }
$steps = @{}  # hashtable

# npm ci if node_modules missing
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
  $steps["ci"] = Run-Step -CmdLine "$npm ci --no-audit --no-fund" -Cwd $Frontend
}

$steps["build"] = Run-Step -CmdLine "$npm run build --silent" -Cwd $Frontend
$steps["test"]  = Run-Step -CmdLine "$npm run test --silent -- -r" -Cwd $Frontend
$steps["lint"]  = Run-Step -CmdLine "$npm run lint --silent" -Cwd $Frontend

# --- write gates json ---
$data = @{
  run_id   = $RunId
  frontend = $Frontend
  tooling  = @{ npm_bin = $npm }
  steps    = $steps
}
$data | ConvertTo-Json -Depth 8 | Set-Content -Path $gatesPath -Encoding UTF8

Write-Host "Wrote $gatesPath"

# --- find PR number from reports\upload_<run>.txt ---
$uploadTxt = Join-Path $reports ("upload_{0}.txt" -f $RunId)
if (-not (Test-Path $uploadTxt)) {
  throw "Missing $uploadTxt. Did you upload artifacts for this run?"
}
$prUrl = (Get-Content $uploadTxt -Raw).Trim()
if (-not $prUrl) { throw "Empty PR URL in $uploadTxt" }

# Extract PR number (last path segment)
try {
  $parts = $prUrl.TrimEnd("/").Split("/")
  $prNum = [int]$parts[-1]
} catch {
  throw "Cannot parse PR number from $prUrl"
}

# --- build comment body ---
$build = $steps["build"]; $test = $steps["test"]; $lint = $steps["lint"]

$body = @"
**Gates report $RunId**

- build: pass=$($build.pass) exit=$($build.exit)
- test : pass=$($test.pass) exit=$($test.exit)
- lint : pass=$($lint.pass) exit=$($lint.exit)

(Frontend: `$Frontend`; npm: `$npm`)
"@

# --- post comment via GitHub CLI ---
& gh pr comment $prNum --body $body | Out-Null
Write-Host "Commented gates summary on PR #$prNum"

# --- ensure labels (optional) ---
try {
  & gh pr edit $prNum --add-label "ts-migration" | Out-Null
  & gh pr edit $prNum --add-label "analysis"     | Out-Null
  Write-Host "Ensured labels on PR #$prNum"
} catch { Write-Warning "Label step skipped: $($_.Exception.Message)" }
