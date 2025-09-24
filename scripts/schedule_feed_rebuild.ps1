param(
[int]$Minutes = 30,
[switch]$RelaxHumanish
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj = Split-Path -Parent $root
function Invoke-FeedRebuild {
$lp = Join-Path $root "lists_plus_roots_to_candidates.ps1"
$zp = Join-Path $root "zips_to_candidates.ps1"
if(Test-Path $lp){ & $lp -Quiet:$true -RelaxHumanish:$RelaxHumanish }
if(Test-Path $zp){ & $zp -Quiet:$true -RelaxHumanish:$RelaxHumanish }
}
while($true){
try { Invoke-FeedRebuild } catch { Write-Host "Feed rebuild error: $($_.Exception.Message)" }
Start-Sleep -Seconds ([Math]::Max(60, $Minutes*60))
}
