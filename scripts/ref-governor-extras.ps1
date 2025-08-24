param(
  [Parameter(Mandatory=$true)][string]$Root,
  [string]$OutDir = "C:\CFH\TruthSource",
  [int]$MaxPerSection = 2000
)

$ErrorActionPreference = 'Stop'
function Stamp { param([string]$m) Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) }

function Is-ExcludedPath {
  param([string]$Path)
  $p = $Path.ToLowerInvariant()
  if ($p -match '\\windows(\\|$)') { return $true }
  if ($p -match '\\program files( \(x86\))?(\\|$)') { return $true }
  if ($p -match '\\programdata(\\|$)') { return $true }
  if ($p -match '\\users\\[^\\]+\\appdata(\\|$)') { return $true }
  if ($p -match '\\\$recycle\.bin(\\|$)') { return $true }
  if ($p -match 'system volume information') { return $true }
  if ($p -match '\\temp(\\|$)') { return $true }
  if ($p -match '\\node_modules(\\|$)') { return $true }
  if ($p -match '\\\.git(\\|$)') { return $true }
  if ($p -match '\\dist(\\|$)') { return $true }
  if ($p -match '\\build(\\|$)') { return $true }
  if ($p -match '\\coverage(\\|$)') { return $true }
  if ($p -match '\\logs?(\\|$)') { return $true }
  if ($p -match '\.log$') { return $true }
  return $false
}

$sanDir = Join-Path $OutDir "artifacts\ref\sanitized"
New-Item -ItemType Directory -Force -Path $sanDir | Out-Null

# tests
Stamp "Scanning for tests..."
$tests = Get-ChildItem -Path $Root -Recurse -File -Include *.test.js,*.test.jsx,*.test.ts,*.test.tsx -ErrorAction SilentlyContinue |
  Where-Object { -not (Is-ExcludedPath $_.FullName) }
$testsListPath = Join-Path $sanDir "file_scan_results_tests_sanitized.md"
"# Sanitized tests ($($tests.Count) items, capped at $MaxPerSection)" | Set-Content -Path $testsListPath -Encoding ASCII
$tests | Select-Object -ExpandProperty FullName | Sort-Object | Select-Object -First $MaxPerSection | ForEach-Object { "- $_" } | Add-Content -Path $testsListPath -Encoding ASCII

# docs that share basename with any canonical code file from js/jsx/ts/tsx sanitized lists
Stamp "Scanning for docs..."
$codeLists = Get-ChildItem $sanDir -Filter "file_scan_results_*_sanitized.md" | Where-Object { $_.Name -match '_(js|jsx|ts|tsx)_sanitized\.md$' }
$baseSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($lst in $codeLists) {
  foreach ($m in (Select-String -Path $lst.FullName -Pattern '^\s*-\s*(.+)$' -ErrorAction SilentlyContinue)) {
    $fp = $m.Matches[0].Groups[1].Value.Trim()
    $bn = [System.IO.Path]::GetFileNameWithoutExtension($fp)
    $baseSet.Add($bn) | Out-Null
  }
}
$md = Get-ChildItem -Path $Root -Recurse -File -Filter *.md -ErrorAction SilentlyContinue |
  Where-Object {
    -not (Is-ExcludedPath $_.FullName) -and
    $baseSet.Contains([System.IO.Path]::GetFileNameWithoutExtension($_.FullName))
  }
$docsListPath = Join-Path $sanDir "file_scan_results_docs_sanitized.md"
"# Sanitized docs ($($md.Count) items, capped at $MaxPerSection)" | Set-Content -Path $docsListPath -Encoding ASCII
$md | Select-Object -ExpandProperty FullName | Sort-Object | Select-Object -First $MaxPerSection | ForEach-Object { "- $_" } | Add-Content -Path $docsListPath -Encoding ASCII

Stamp "Done. tests: $testsListPath; docs: $docsListPath"
