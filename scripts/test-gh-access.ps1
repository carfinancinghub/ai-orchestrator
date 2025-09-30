# scripts\test-gh-access.ps1
# End-to-end read+write access test across multiple GitHub repos
# - Clones each repo to a temp dir
# - Creates a temp branch
# - Writes a marker file
# - Forces add (bypasses .gitignore), commits, pushes, then deletes the remote branch
# - Emits CSV/JSON/MD reports under reports\local_checks\<timestamp>

param(
  [string]$ConfigPath = ".\configs\repos.json",
  [bool]$DoWriteTest = $true,
  [string]$OrchestratorRoot = "C:\c\ai-orchestrator"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $ConfigPath)) {
  Write-Error "Config not found: $ConfigPath"
  exit 1
}

$config = Get-Content $ConfigPath | ConvertFrom-Json
$owner  = $config.owner
$repos  = $config.repos

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $OrchestratorRoot "reports\local_checks\$ts"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

# Clear env tokens that confuse gh
Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue

# Ensure gh is logged in
try {
  gh auth status 1>$null 2>$null
} catch {
  Write-Host "gh not logged in. Please run: gh auth login --web" -ForegroundColor Yellow
  exit 1
}

function Invoke-CmdSafe([string]$Cmd) {
  try {
    $o = Invoke-Expression $Cmd 2>&1
    return @{ ok = $true; out = ($o -join "`n"); err = "" }
  } catch {
    return @{ ok = $false; out = ""; err = $_.Exception.Message }
  }
}

$results  = New-Object System.Collections.Generic.List[object]
$tempRoot = Join-Path $env:TEMP "gh-access-test"
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

foreach ($repo in $repos) {
  $full = "$owner/$repo"
  $row = [ordered]@{
    repo              = $full
    api_read_ok       = $false
    git_read_ok       = $false
    clone_ok          = $false
    push_ok           = $false
    delete_branch_ok  = $false
    branch_name       = ""
    errors            = @()
  }

  Write-Host "`n== $full ==" -ForegroundColor Cyan

  # API read
  $r = Invoke-CmdSafe "gh repo view -R $full --json name,defaultBranchRef,viewerPermission | ConvertTo-Json"
  if ($r.ok) { $row.api_read_ok = $true } else { $row.errors += "api_read: $($r.err)" }

  # Git read
  $r = Invoke-CmdSafe "git ls-remote https://github.com/$full.git | Select-Object -First 1 | Out-String"
  if ($r.ok -and $r.out.Trim().Length -gt 0) { $row.git_read_ok = $true } else { $row.errors += "git_read: $($r.err)" }

  if ($DoWriteTest) {
    $cloneDir = Join-Path $tempRoot $repo
    if (Test-Path $cloneDir) { Remove-Item -Recurse -Force $cloneDir }

    $r = Invoke-CmdSafe "git clone --depth 1 https://github.com/$full.git `"$cloneDir`""
    if ($r.ok) {
      $row.clone_ok = $true
      Push-Location $cloneDir
      try {
        $branch = "access-check/$($env:COMPUTERNAME)/$ts"
        $row.branch_name = $branch
        git checkout -b $branch | Out-Null

        # Create a unique marker file and force-add it (bypass .gitignore)
        $markerName = ".access_check_{0}.txt" -f (Get-Date -Format 'yyyyMMdd_HHmmss')
        $markerPath = Join-Path $cloneDir $markerName
        @(
          "repo: $full"
          "machine: $env:COMPUTERNAME"
          "user: $env:USERNAME"
          "time: $(Get-Date -Format 'u')"
        ) | Out-File $markerPath -Encoding utf8 -Force

        # Force add to bypass repo .gitignore rules
        $r = Invoke-CmdSafe "git add -f `"$markerPath`""
        if (-not $r.ok) { $row.errors += "add_marker: $($r.err)" }

        # Only commit if the marker is actually staged
        $statusOut = (git status --porcelain) -join "`n"
        if ($statusOut -match [regex]::Escape($markerName)) {
          git commit -m "chore(access-check): temp write test ($markerName)" | Out-Null
          $r = Invoke-CmdSafe "git push -u origin `"$branch`""
          if ($r.ok) {
            $row.push_ok = $true
            # Try remote delete
            $r = Invoke-CmdSafe "git push origin --delete `"$branch`""
            if ($r.ok) { $row.delete_branch_ok = $true } else { $row.errors += "delete_remote_branch: $($r.err)" }
          } else {
            $row.errors += "push: $($r.err)"
          }
        } else {
          $row.errors += "nothing_to_commit (likely blocked by local ignore or filters)"
        }
      } catch {
        $row.errors += "exception: $($_.Exception.Message)"
      } finally {
        Pop-Location
        try { Remove-Item -Recurse -Force $cloneDir } catch {}
      }
    } else {
      $row.errors += "clone: $($r.err)"
    }
  }

  $results.Add([pscustomobject]$row) | Out-Null
}

# Write reports
$csvPath  = Join-Path $outDir "github_access_report.csv"
$jsonPath = Join-Path $outDir "github_access_report.json"
$mdPath   = Join-Path $outDir "github_access_report.md"

$results | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
$results | ConvertTo-Json -Depth 5 | Out-File $jsonPath -Encoding UTF8

$headers = @("repo","api_read_ok","git_read_ok","clone_ok","push_ok","delete_branch_ok","branch_name","errors")
$lines = @(
  "| " + ($headers -join " | ") + " |",
  "| " + (($headers | ForEach-Object { "---" }) -join " | ") + " |"
)
foreach ($row in $results) {
  $vals = $headers | ForEach-Object {
    $v = $row.$_
    if ($v -is [System.Collections.IEnumerable] -and -not ($v -is [string])) { ($v -join "; ") } else { $v }
  }
  $lines += "| " + ($vals -join " | ") + " |"
}
$lines | Out-File $mdPath -Encoding UTF8

Write-Host "`nReport written to:" -ForegroundColor Green
Write-Host $csvPath
Write-Host $jsonPath
Write-Host $mdPath
