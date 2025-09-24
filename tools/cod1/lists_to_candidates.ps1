param(
  [string]$AIO       = "C:\c\ai-orchestrator",
  [string]$Frontend  = "C:\Backup_Projects\CFH\frontend",
  [string]$ListsDir  = $null,          # defaults to <AIO>\lists if omitted
  [switch]$OnlyUnderFrontend,
  [switch]$Recurse
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

# ----- resolve lists dir -----
if ([string]::IsNullOrWhiteSpace($ListsDir)) { $ListsDir = Join-Path $AIO "lists" }
$ListsDir = (Resolve-Path -LiteralPath $ListsDir).Path

# ----- collect .md / .txt -----
$listFiles = @()
if ($Recurse) {
  $listFiles += Get-ChildItem -LiteralPath $ListsDir -Recurse -File -Filter *.md  -ErrorAction SilentlyContinue
  $listFiles += Get-ChildItem -LiteralPath $ListsDir -Recurse -File -Filter *.txt -ErrorAction SilentlyContinue
} else {
  $listFiles += Get-ChildItem -LiteralPath $ListsDir -File -Filter *.md  -ErrorAction SilentlyContinue
  $listFiles += Get-ChildItem -LiteralPath $ListsDir -File -Filter *.txt -ErrorAction SilentlyContinue
}
if (-not $listFiles -or $listFiles.Count -eq 0) {
  throw "No .md/.txt files found in $ListsDir"
}

# ----- outputs -----
$reports     = Join-Path $AIO "reports"
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$rawOut      = Join-Path $reports "conversion_candidates_from_lists.txt"
$dedupOut    = Join-Path $reports "conversion_candidates_deduped.txt"
$reportOut   = Join-Path $reports "same_name_different_size_from_lists.md"
$missingOut  = Join-Path $reports "lists_missing_local.txt"
$summaryOut  = Join-Path $reports "lists_summary.txt"

# ----- parse list lines into absolute paths -----
$paths = New-Object System.Collections.Generic.List[string]
foreach ($file in $listFiles) {
  $inCode = $false
  Get-Content -LiteralPath $file.FullName | ForEach-Object {
    $line = $_.Trim()

    # toggle code fences
    if ($line -like '```*') { $inCode = -not $inCode; return }

    # skip comments/headings/tables/out-of-code fluff
    if (-not $inCode) {
      if ($line -eq "" -or
          $line -like '<!*' -or
          $line -like '#*'  -or
          $line -like '_*_' -or
          $line -like '*|*|*') { return }
    }

    # remove bullets/numbering
    $line = $line -replace '^[\-\*\d\.\)\s]+',''

    # accept Windows paths (C:\...) or /mnt/... style
    if ($line -match '^[A-Za-z]:\\' -or $line -match '^(\/|\\)') {
      $paths.Add($line)
    }
  }
}

# optionally keep only entries under your frontend tree
if ($OnlyUnderFrontend) {
  $front = (Resolve-Path -LiteralPath $Frontend).Path
  $frontLow = $front.ToLower()
  $paths = [System.Collections.Generic.List[string]]($paths | Where-Object { $_.ToLower().StartsWith($frontLow) })
}

# raw
$paths | Set-Content -Path $rawOut -Encoding UTF8

# ----- dedup by Name+Size and detect conflicts -----
$seen   = @{}
$byName = @{}
$out    = New-Object System.Collections.Generic.List[string]
$missing= New-Object System.Collections.Generic.List[string]

foreach ($p in $paths) {
  $fi = Get-Item -LiteralPath $p -ErrorAction SilentlyContinue
  if (-not $fi) { $missing.Add($p); continue }

  $key = "$($fi.Name)|$($fi.Length)"
  if (-not $seen.ContainsKey($key)) {
    $seen[$key] = $true
    $out.Add($fi.FullName)
  }

  if (-not $byName.ContainsKey($fi.Name)) {
    $byName[$fi.Name] = New-Object System.Collections.Generic.List[object]
  }
  $byName[$fi.Name].Add([PSCustomObject]@{ path=$fi.FullName; size=$fi.Length })
}

$out     | Set-Content -Path $dedupOut   -Encoding UTF8
$missing | Set-Content -Path $missingOut -Encoding UTF8

# conflicts report (same name, different sizes)
$lines = @('# Same-name different-size (from uploaded lists)','')
foreach ($name in ($byName.Keys | Sort-Object)) {
  $sizes = ($byName[$name] | Select-Object -ExpandProperty size | Sort-Object -Unique)
  if ($sizes.Count -gt 1) {
    $lines += "## $name"
    foreach ($e in ($byName[$name] | Sort-Object size, path)) {
      $lines += ("- {0} bytes - {1}" -f $e.size, $e.path)
    }
    $lines += ""
  }
}
$lines -join "`r`n" | Set-Content -Path $reportOut -Encoding UTF8

# feed dedup into pipeline candidate file
Copy-Item $dedupOut (Join-Path $reports 'conversion_candidates.txt') -Force

# summary
$jsCount  = ($out | Where-Object { $_.ToLower().EndsWith('.js')  }).Count
$jsxCount = ($out | Where-Object { $_.ToLower().EndsWith('.jsx') }).Count
$tsCount  = ($out | Where-Object { $_.ToLower().EndsWith('.ts')  }).Count
$tsxCount = ($out | Where-Object { $_.ToLower().EndsWith('.tsx') }).Count

@(
  "JS in list (existing): $jsCount"
  "JSX in list (existing): $jsxCount"
  "TS in list (existing): $tsCount"
  "TSX in list (existing): $tsxCount"
  "Missing (not on disk): $($missing.Count)"
  "Candidates raw: $($paths.Count)"
  "Candidates dedup: $($out.Count)"
) | Set-Content -Path $summaryOut -Encoding UTF8

Write-Host "Built from lists:"
Write-Host "  Raw      : $rawOut"
Write-Host "  Dedup    : $dedupOut (also copied to reports\conversion_candidates.txt)"
Write-Host "  Conflicts: $reportOut"
Write-Host "  Missing  : $missingOut"
Write-Host "  Summary  : $summaryOut"

