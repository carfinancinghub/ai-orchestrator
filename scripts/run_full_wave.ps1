param(
  [switch]$Execute,        # default: DryRun (log only)
  [ValidateSet("free","premium","wow")]
  [string]$Tier = "premium"
)

$State = if ($Execute) { "execute" } else { "dry-run" }
$pillars = @(
  @{ name = "auctions"; md = ".\reports\reviews\Auction" },
  @{ name = "escrow";   md = ".\reports\reviews\Escrow" }
)

foreach ($p in $pillars) {
  $mdCount  = (gci $p.md -Filter *.md -ErrorAction SilentlyContinue | Measure-Object).Count
  $tsxCount = (gci .\src\_ai_out -Filter "*$($p.name)*.tsx" -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count

  # emit per-pillar csv
  $outCsv = ".\reports\wave_metrics_{0}.csv" -f $p.name
  [pscustomobject]@{
    timestamp = (Get-Date).ToString("s") + "Z"
    mode      = $State
    tier      = $Tier
    pillar    = $p.name
    md_count  = $mdCount
    tsx_count = $tsxCount
    conf_avg  = 0.86  # placeholder; wire real parse later
    cost_est  = 2.00  # placeholder; wire token logs later
  } | Export-Csv -Append -NoTypeInformation -Encoding UTF8 $outCsv

  if ($Execute) {
    # (Future) call prep → tree → prune → resolve → build here
    # For now we keep it harmless to reviewers.
  }
}
Write-Host "Wave metrics written under reports/wave_metrics_*.csv"
