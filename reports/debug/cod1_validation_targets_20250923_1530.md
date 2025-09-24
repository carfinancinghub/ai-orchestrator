# === Verifier v2: resolves ../../ correctly ===
$ErrorActionPreference = "Stop"

# 0) Inputs
$TargetsFile = ".\reports\debug\cod1_validation_targets_20250923_1530.md"
if (-not (Test-Path $TargetsFile)) { throw "Targets file not found: $TargetsFile" }

# 1) Repo + remote
$RepoRoot = (git rev-parse --show-toplevel).Trim()
$Remote   = (git config --get remote.origin.url)
if ($Remote -match 'github\.com[:/](.+?)/(.+?)(\.git)?$') {
  $Org = $Matches[1]; $RepoName = $Matches[2]
} else { throw "Remote URL not recognized as GitHub: $Remote" }
$DefaultBranch = "main"
$BaseUrl = "https://github.com/$Org/$RepoName/blob/$DefaultBranch/"

# 2) Helper: make relative path from absolute to repo root (even if the file doesn't exist)
function Get-RelToRepo([string]$abs, [string]$root) {
  $a = [System.IO.Path]::GetFullPath($abs)
  $r = [System.IO.Path]::GetFullPath($root)
  if (-not $a.StartsWith($r, [System.StringComparison]::OrdinalIgnoreCase)) { return $abs }
  $rel = $a.Substring($r.Length).TrimStart('\','/')
  return $rel -replace '\\','/'
}

# 3) Read markdown links and resolve relative to the checklist file's folder
$BaseDir = Split-Path -Parent (Resolve-Path $TargetsFile)
$links = Select-String -Path $TargetsFile -Pattern '\[.+?\]\((.+?)\)' -AllMatches |
  ForEach-Object { $_.Matches } |
  ForEach-Object { $_.Groups[1].Value }

$results = foreach ($rel in $links) {
  # Resolve candidate full path even if it doesn't exist
  $joined = Join-Path $BaseDir $rel
  $abs = [System.IO.Path]::GetFullPath($joined)
  $relToRepo = Get-RelToRepo $abs $RepoRoot

  $fsPath = Join-Path $RepoRoot $relToRepo
  $exists = Test-Path $fsPath
  $size = $null; $sha1 = $null
  if ($exists -and (Get-Item $fsPath).PSIsContainer -eq $false) {
    $size = (Get-Item $fsPath).Length
    $sha1 = (Get-FileHash -Algorithm SHA1 $fsPath).Hash
  }
  $url = $BaseUrl + ($relToRepo -replace '\\','/')

  [pscustomobject]@{
    Path   = $relToRepo
    Exists = $exists
    Size   = $size
    SHA1   = $sha1
    URL    = $url
  }
}

# 4) Show and save
$results | Sort-Object Path | Format-Table -AutoSize
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$outCsv = ".\reports\debug\cod1_validation_results_$stamp.csv"
$results | Sort-Object Path | Export-Csv -NoTypeInformation -Encoding UTF8 $outCsv
"Results saved: $outCsv"
