param(
  [string]$FeedPath = ".\reports\conversion_candidates.txt",
  [string]$GeneratedRoot = ".\artifacts\generated"
)
$feed = Get-Content $FeedPath -ErrorAction SilentlyContinue | Where-Object { $_ }
$genStems = Get-ChildItem $GeneratedRoot -Recurse -File -Include *.ts,*.tsx -EA SilentlyContinue |
  ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.Name).ToLower() } | Sort-Object -Unique
$keep = foreach($p in $feed){
  $stem = [IO.Path]::GetFileNameWithoutExtension([IO.Path]::GetFileName($p)).ToLower()
  if($stem -notin $genStems){ $p }
}
$keep | Set-Content $FeedPath -Encoding UTF8
Write-Host ("Pruned feed. Remaining: {0}" -f (($keep | Where-Object { $_ }).Count))
