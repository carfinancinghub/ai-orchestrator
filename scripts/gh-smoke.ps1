param([string]$ConfigPath = ".\configs\repos.json")
if (-not (Test-Path $ConfigPath)) { Write-Error "Config not found: $ConfigPath"; exit 1 }
$config = Get-Content $ConfigPath | ConvertFrom-Json
$owner = $config.owner; $repos = $config.repos
Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue
try { gh auth status | Out-Null } catch { Write-Host "gh not logged in. Run: gh auth login --web" -ForegroundColor Yellow; exit 1 }
function Invoke-CmdSafe($Cmd){ try{$o=Invoke-Expression $Cmd 2>&1; @{ok=$true;out=$o -join "`n";err=""}}catch{ @{ok=$false;out="";err=$_.Exception.Message} } }
Write-Host "=== GitHub Smoke Test (read-only) ===" -ForegroundColor Cyan
foreach($repo in $repos){
  $full="$owner/$repo"; Write-Host "`n== $full ==" -ForegroundColor Cyan
  $r1=Invoke-CmdSafe "gh repo view -R $full --json name,defaultBranchRef,viewerPermission | ConvertTo-Json"
  if($r1.ok){Write-Host "gh: repo view OK" -ForegroundColor Green}else{Write-Host "gh: repo view FAIL: $($r1.err)" -ForegroundColor Red}
  $r2=Invoke-CmdSafe "git ls-remote https://github.com/$full.git | Select-Object -First 1 | Out-String"
  if($r2.ok -and $r2.out.Trim().Length -gt 0){Write-Host "git: ls-remote OK" -ForegroundColor Green}else{Write-Host "git: ls-remote FAIL: $($r2.err)" -ForegroundColor Red}
}
