# extractor for Run 20250923_2212
Param(
  [string]$RunId = "20250923_2212",
  [string]$Source = "reports\ai_review_20250923_084351.md"
)
$ErrorActionPreference = "Stop"

$out = "artifacts\generated\$RunId"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$md = Get-Content $Source -Raw
$fences = [regex]::Matches($md, '(?ms)```ts\s+path=@(?<path>[^\r\n]+)\s*(?<code>.+?)```')

$max = [Math]::Min(25, $fences.Count)
for ($i=0; $i -lt $max; $i++) {
  $path = $fences[$i].Groups['path'].Value.Trim()
  $code = $fences[$i].Groups['code'].Value.Trim()

  if ($path -notmatch '^@') { throw "Fence $i has invalid path: $path" }
  $rel  = $path -replace '^@','' -replace '^[\\/]+',''
  $dest = Join-Path $out $rel
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null

  $bytes = [Text.Encoding]::UTF8.GetBytes($code)
  $sha1  = [BitConverter]::ToString((New-Object Security.Cryptography.SHA1Managed).ComputeHash($bytes)).Replace('-','').ToLower()

  if (Test-Path $dest) {
    $existing = Get-Content $dest -Raw
    $exSha1 = [BitConverter]::ToString((New-Object Security.Cryptography.SHA1Managed).ComputeHash([Text.Encoding]::UTF8.GetBytes($existing))).Replace('-','').ToLower()
    if ($exSha1 -ne $sha1) { throw "Refuse overwrite: SHA1 mismatch at $dest" }
  } else {
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    [IO.File]::WriteAllBytes($dest, $bytes)
  }
  Write-Host "Wrote: $dest ($sha1)"
}
