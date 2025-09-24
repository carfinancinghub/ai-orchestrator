param(
  [string]$FeedPath = ".\reports\conversion_candidates.txt",
  [string]$GeneratedRoot = ".\artifacts\generated"
)
$feed = Get-Content $FeedPath -ErrorAction SilentlyContinue | Where-Object { $_ }
$exists = $feed | Where-Object { Test-Path $_ }
$genStems = Get-ChildItem $GeneratedRoot -Recurse -File -Include *.ts,*.tsx -EA SilentlyContinue |
  ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.Name).ToLower() } | Sort-Object -Unique
$need = foreach($p in $exists){
  $stem = [IO.Path]::GetFileNameWithoutExtension([IO.Path]::GetFileName($p)).ToLower()
  if($stem -notin $genStems){ $p }
}
"Feed total   : {0}" -f ($feed.Count)
"Exist on disk: {0}" -f ($exists.Count)
"Generated    : {0}" -f ($genStems.Count)
"Still need   : {0}" -f ($need.Count)
