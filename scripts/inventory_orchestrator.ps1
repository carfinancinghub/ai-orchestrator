param([string]$Root = "C:\c\ai-orchestrator")
$ErrorActionPreference="Stop"
$invDir="reports"; $dbgDir="reports\debug"
New-Item -ItemType Directory -Force -Path $invDir,$dbgDir | Out-Null

$origin = git -C $Root remote get-url origin
$branch = git -C $Root rev-parse --abbrev-ref HEAD
try{
  $counts = git -C $Root rev-list --left-right --count "origin/$branch...$branch" 2>$null
  $parts = $counts -split "\s+"
  $ahead = $parts[0]; $behind = $parts[-1]
}catch{$ahead="";$behind=""}

$patterns=@("app\*.py",".orchestrator\*.py","reports\*.json","reports\debug\*.md")
$files=foreach($pat in $patterns){ Get-ChildItem -Path (Join-Path $Root $pat) -File -Recurse -ErrorAction SilentlyContinue }

$rows=foreach($f in $files){
  [pscustomobject]@{
    rel=$f.FullName.Substring($Root.Length).TrimStart('\','/')
    size=$f.Length
    mtime=$f.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
  }
}
$csv="reports\inv_orchestrator_files.csv"
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $csv

$ops=Join-Path $Root "app\ops.py"
$opsStamp = if(Test-Path $ops){ (Get-Item $ops).LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ") } else { "missing" }

$summary=@'
Repo: `C:\c\ai-orchestrator`
Origin: `{0}`
Branch: `{1}` (ahead {2} / behind {3})
ops.py mtime (UTC): {4}
Files CSV: `inv_orchestrator_files.csv`
'@ -f $origin, $branch, $ahead, $behind, $opsStamp

$summary | Set-Content -Encoding UTF8 "reports\debug\inventory_orchestrator_summary.md"
"OK: wrote $csv and summary."
