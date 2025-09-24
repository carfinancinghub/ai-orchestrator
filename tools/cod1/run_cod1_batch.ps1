param(
  [string]$AIO = "C:\c\ai-orchestrator",
  [string]$CFH_FRONTEND = "C:\Backup_Projects\CFH\frontend",
  [string]$GhRepo = "carfinancinghub/cfh",
  [int]$Count = 10,
  [string]$RunId = $(Get-Date -Format yyyyMMdd_HHmmss)
)
$ErrorActionPreference = "Stop"
Set-Location $AIO

$files = Get-ChildItem $CFH_FRONTEND -Include *.jsx,*.js -File -Recurse |
         Select-Object -First $Count | ForEach-Object { $_.FullName }
$joined = [string]::Join("`n", $files)

$code = @'
from app.ops import process_batch_ext
import os
files = os.environ.get("FILES","").splitlines()
res = process_batch_ext("local", None, files, {"gh_repo": os.environ.get("GH_REPO")}, os.environ.get("RUN_ID","cod1-demo"), mode="cod1")
print(res)
'@

$env:FILES  = $joined
$env:GH_REPO= $GhRepo
$env:RUN_ID = $RunId

$code | & python -
