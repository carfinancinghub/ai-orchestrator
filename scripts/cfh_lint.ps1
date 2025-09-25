# scripts/cfh_lint.ps1
# CFH lint gate — local-first runners, no npx, hard/soft via CFH_LINT_SOFT.
# Tools:
#   - TSC (--noEmit) if tsconfig present
#   - ESLint if eslint config present
#   - Prettier check if config present
# Output:
#   - reports/cfh_lint_summary.json
# Vendor/output dirs are ignored explicitly.

Param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$HARD = ($env:CFH_LINT_SOFT -ne "1")  # default hard
$Root = Resolve-Path "."
$SummaryPath = Join-Path $Root "reports\cfh_lint_summary.json"
New-Item -ItemType Directory -Force -Path (Split-Path $SummaryPath) | Out-Null

$results = [ordered]@{
  mode     = if ($HARD) { "hard" } else { "soft" }
  eslint   = "skipped"
  tsc      = "skipped"
  prettier = "skipped"
  notes    = @()
}

function Note([string]$msg) { $results.notes += $msg }

function Has-AnyFile([string[]]$globs) {
  foreach ($g in $globs) {
    $hit = Get-ChildItem -Path $g -File -ErrorAction Ignore | Select-Object -First 1
    if ($hit) { return $true }
  }
  return $false
}

$OnWindows = $IsWindows

function Resolve-Exe([string]$name) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Path }
  return $null
}

function Find-LocalBin([string]$tool) {
  $cands = @(
    "node_modules\.bin\$tool.cmd",
    "node_modules\.bin\$tool.ps1",
    "node_modules\.bin\$tool.exe",
    "node_modules\.bin\$tool"
  )
  foreach ($c in $cands) {
    $p = Join-Path $Root $c
    if (Test-Path $p) { return (Resolve-Path $p).Path }
  }
  return $null
}

function Exec([string]$exe, [string[]]$args) {
  # resolve unqualified
  if (-not ([IO.Path]::IsPathRooted($exe))) {
    $resolved = Resolve-Exe $exe
    if ($resolved) { $exe = $resolved }
  }
  $ext = ([IO.Path]::GetExtension($exe) ?? "").ToLowerInvariant()
  if ($ext -eq ".ps1") {
    Write-Host "• pwsh -NoProfile -ExecutionPolicy Bypass -File $exe $($args -join ' ')" -ForegroundColor Cyan
    & pwsh -NoProfile -ExecutionPolicy Bypass -File $exe @args
    $code = $LASTEXITCODE
    return [pscustomobject]@{ code=$code; out=""; err="" }
  } else {
    Write-Host "• $exe $($args -join ' ')" -ForegroundColor Cyan
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName  = $exe
    $psi.Arguments = ($args -join " ")
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute = $false
    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    return [pscustomobject]@{ code=$p.ExitCode; out=$stdout.Trim(); err=$stderr.Trim() }
  }
}

function Build-Runner([string]$tool, [string[]]$toolArgs) {
  # 1) local bin first (no PATH needed)
  $local = Find-LocalBin $tool
  if ($local) { return @{ exe=$local; args=$toolArgs; how="local" } }

  # 2) cross-platform runners (prefer npm exec on Windows)
  $order = if ($OnWindows) { @("npm","pnpm","yarn","bunx") } else { @("pnpm","npm","yarn","bunx") }
  $map = @{}
  foreach ($name in $order) { $p = Resolve-Exe $name; if ($p) { $map[$name] = $p } }

  if ($map.ContainsKey("npm"))  { return @{ exe=$map["npm"];  args=@("exec",$tool,"--")+$toolArgs; how="npm exec" } }
  if ($map.ContainsKey("pnpm")) { return @{ exe=$map["pnpm"]; args=@("exec",$tool)+$toolArgs;       how="pnpm exec" } }
  if ($map.ContainsKey("yarn")) { return @{ exe=$map["yarn"]; args=@($tool)+$toolArgs;             how="yarn" } }
  if ($map.ContainsKey("bunx")) { return @{ exe=$map["bunx"]; args=@($tool)+$toolArgs;             how="bunx" } }

  return $null
}

function Exec-Tool([string]$tool, [string[]]$args, [string]$label) {
  $runner = Build-Runner $tool $args
  if ($null -eq $runner) {
    return [pscustomobject]@{ code=127; out=""; err="$($label): no runner/tool found" }
  }
  Write-Host "runner: $($runner.how)" -ForegroundColor DarkGray
  return Exec $runner.exe $runner.args
}

$fail = $false

# ===== ESLint (if config present) =====
$eslintHasConfig = Has-AnyFile @(".eslintrc", ".eslintrc.*", "eslint.config.*")
if ($eslintHasConfig) {
  try {
    $r = Exec-Tool "eslint" @(
      ".", "--ext", ".ts,.tsx",
      "--ignore-pattern","node_modules/**",
      "--ignore-pattern","artifacts/**",
      "--ignore-pattern","dist/**",
      "--ignore-pattern","build/**"
    ) "eslint"
    if ($r.code -eq 0) { $results.eslint = "pass" } else { $results.eslint = "fail"; $fail = $true; if ($r.err) { Note $r.err } else { Note $r.out } }
  } catch { $results.eslint = "error"; $fail = $true; Note $_.ToString() }
}

# ===== TSC (if tsconfig present) =====
$tscHasConfig = Has-AnyFile @("tsconfig.json","tsconfig.*.json")
if ($tscHasConfig) {
  $r = $null
  try {
    # Primary: local-first or exec runner
    $r = Exec-Tool "tsc" @("-p",".","--noEmit") "tsc"
    if ($r.code -eq 127 -or ($r.err -like "*no runner/tool found*")) {
      # Fallback: run node_modules/typescript/bin/tsc via node
      $tscJs = Join-Path $Root "node_modules\typescript\bin\tsc"
      if (Test-Path "$tscJs.ps1") { $r = Exec "$tscJs.ps1" @("-p",".","--noEmit") }
      elseif (Test-Path "$tscJs.cmd") { $r = Exec "$tscJs.cmd" @("-p",".","--noEmit") }
      elseif (Test-Path $tscJs) {
        $node = Resolve-Exe "node"
        if ($node) { $r = Exec $node @($tscJs,"-p",".","--noEmit") }
        else { $r = [pscustomobject]@{ code=127; out=""; err="node not found for local TypeScript fallback" } }
      } else {
        $r = [pscustomobject]@{ code=127; out=""; err="typescript not installed locally" }
      }
    }
    if ($r.code -eq 0) { $results.tsc = "pass" } else { $results.tsc = "fail"; $fail = $true; if ($r.err) { Note $r.err } else { Note $r.out } }
  } catch { $results.tsc = "error"; $fail = $true; Note $_.ToString() }
}

# ===== Prettier (if config present) =====
$prettierHasConfig = Has-AnyFile @(".prettierrc*", "prettier.config.*")
if ($prettierHasConfig) {
  try {
    $r = Exec-Tool "prettier" @("-c",".","--ignore-path",".gitignore") "prettier"
    if ($r.code -eq 0) { $results.prettier = "pass" } else { $results.prettier = "fail"; $fail = $true; if ($r.err) { Note $r.err } else { Note $r.out } }
  } catch { $results.prettier = "error"; $fail = $true; Note $_.ToString() }
}

# ===== Summary & exit policy =====
($results | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 $SummaryPath
Write-Host "Summary → $SummaryPath"

if ($HARD -and $fail) {
  Write-Error "CFH lint gate failed (hard mode)."
  exit 1
} elseif ($fail) {
  Write-Warning "CFH lint gate had failures (soft mode)."
}

Write-Host "CFH lint gate complete."
