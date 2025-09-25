Param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# -------- config --------
$HARD = ($env:CFH_LINT_SOFT -ne "1")  # default hard
$SummaryPath = Join-Path (Resolve-Path ".") "reports\cfh_lint_summary.json"
New-Item -ItemType Directory -Force -Path (Split-Path $SummaryPath) | Out-Null

$results = [ordered]@{
  mode     = if ($HARD) { "hard" } else { "soft" }
  eslint   = "skipped"
  tsc      = "skipped"
  prettier = "skipped"
}

function Has-File([string]$glob) {
  return @(Get-ChildItem -Path $glob -File -ErrorAction Ignore).Count -gt 0
}

function Run {
  param([string]$Name, [string]$Cmd, [string[]]$Args)

  Write-Host "• $Name → $Cmd $($Args -join ' ')" -ForegroundColor Cyan
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName  = $Cmd
  $psi.Arguments = ($Args -join " ")
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.UseShellExecute = $false
  $p = [System.Diagnostics.Process]::Start($psi)
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()

  return [pscustomobject]@{
    code   = $p.ExitCode
    out    = $stdout.Trim()
    err    = $stderr.Trim()
  }
}

$fail = $false

# -------- ESLint --------
$eslintConfig = @(".eslintrc","*.eslintrc.*","eslint.config.*") | ForEach-Object { Get-ChildItem $_ -ErrorAction Ignore } | Select-Object -First 1
if ($null -ne $eslintConfig) {
  try {
    $r = Run -Name "eslint" -Cmd "npx" -Args @("--yes","eslint",".","--ext",".ts,.tsx")
    if ($r.code -eq 0) { $results.eslint = "pass" } else { $results.eslint = "fail"; $fail = $true; Write-Host $r.err -ForegroundColor Red }
  } catch { $results.eslint = "error"; $fail = $true; Write-Host $_ -ForegroundColor Red }
}

# -------- TSC (typecheck) --------
if (Has-File "tsconfig.json") {
  try {
    $r = Run -Name "tsc" -Cmd "npx" -Args @("--yes","tsc","-p",".","--noEmit")
    if ($r.code -eq 0) { $results.tsc = "pass" } else { $results.tsc = "fail"; $fail = $true; Write-Host $r.err -ForegroundColor Red }
  } catch { $results.tsc = "error"; $fail = $true; Write-Host $_ -ForegroundColor Red }
}

# -------- Prettier (format check) --------
$prettierSignal = @(".prettierrc*","prettier.config.*") | ForEach-Object { Get-ChildItem $_ -ErrorAction Ignore } | Select-Object -First 1
if ($null -ne $prettierSignal) {
  try {
    $r = Run -Name "prettier" -Cmd "npx" -Args @("--yes","prettier","-c",".")
    if ($r.code -eq 0) { $results.prettier = "pass" } else { $results.prettier = "fail"; $fail = $true; Write-Host $r.err -ForegroundColor Red }
  } catch { $results.prettier = "error"; $fail = $true; Write-Host $_ -ForegroundColor Red }
}

# -------- write summary --------
($results | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 $SummaryPath
Write-Host "Summary → $SummaryPath"

if ($HARD -and $fail) {
  Write-Error "CFH lint gate failed (hard mode)."
  exit 1
} elseif ($fail) {
  Write-Warning "CFH lint gate had failures (soft mode)."
}

Write-Host "CFH lint gate complete."
