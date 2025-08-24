param(
  [Parameter(Mandatory=$true)][string]$PromptKey,
  [ValidateSet("free","premium","wow++")][string]$Tier = "premium",
  [Parameter(Mandatory=$true)][string]$Root,
  [int]$Port = 8020   # default to a less-likely-to-be-used port
)

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:$Port"

function Free-Port {
  param([int]$Port)
  try{
    $p = Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop |
         Select-Object -First 1 -ExpandProperty OwningProcess
    if($p){ Stop-Process -Id $p -Force; Start-Sleep -Milliseconds 300 }
  }catch{}
}

function Wait-Api {
  param([int]$Tries=20)
  for($i=0;$i -lt $Tries;$i++){
    try{
      $r = Invoke-RestMethod -Method GET -Uri "$base/health" -TimeoutSec 2 -ErrorAction Stop
      if($r.ok){ return $true }
    }catch{}
    Start-Sleep -Milliseconds 300
  }
  return $false
}

# ensure server up
$alive = $false
try { $alive = Wait-Api -Tries 1 } catch {}

if(-not $alive){
  Write-Host "[one-prompt] Ensuring uvicorn on :$Port ..." -ForegroundColor Cyan
  Free-Port -Port $Port
  $args = "-m uvicorn app.main:app --host 127.0.0.1 --port $Port"
  Start-Process -FilePath "python" -ArgumentList $args -WindowStyle Hidden | Out-Null
  if(-not (Wait-Api -Tries 50)){
    throw "API failed to come up on :$Port"
  }
}

# POST /run-one
$body = @{
  prompt_key = $PromptKey
  tier       = $Tier
  root       = $Root
  js         = @("src/**/*.js")
  jsx        = @("src/**/*.jsx")
  ts         = @("src/**/*.ts")
  tsx        = @("src/**/*.tsx")
} | ConvertTo-Json -Depth 5

Write-Host "[one-prompt] Triggering '$PromptKey' ($Tier) on $Root ..." -ForegroundColor Green
$resp = Invoke-RestMethod -Method POST -Uri "$base/run-one" -Body $body -ContentType "application/json"

$log = $resp.log_path
Write-Host "[one-prompt] in_root=$($resp.in_root) threshold=$($resp.threshold) stop=$($resp.stop)"
if(Test-Path $log){
  Write-Host "[one-prompt] Tail: $log" -ForegroundColor Yellow
  Get-Content $log -Tail 120
}else{
  Write-Warning "Log not found: $log"
}
