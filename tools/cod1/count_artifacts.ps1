param(
  [string]$AIO = "C:\c\ai-orchestrator",
  [string]$RunId = ""
)
$ErrorActionPreference = "Stop"
Set-Location $AIO
if (-not $RunId) {
  $RunId = (Get-ChildItem "artifacts\suggestions" -Directory | Sort-Object Name -Descending | Select-Object -First 1).Name
}
$obj = [PSCustomObject]@{
  RunId       = $RunId
  Suggestions = (Get-ChildItem -File -Recurse "artifacts\suggestions\$RunId" -ErrorAction SilentlyContinue).Count
  Specs       = (Get-ChildItem -File -Recurse "artifacts\specs" -ErrorAction SilentlyContinue).Count
  Generated   = (Get-ChildItem -File -Recurse "artifacts\generated" -ErrorAction SilentlyContinue).Count
  Reviews     = (Get-ChildItem -File -Recurse "artifacts\reviews\$RunId\verify" -ErrorAction SilentlyContinue).Count
}
$obj | Format-List
