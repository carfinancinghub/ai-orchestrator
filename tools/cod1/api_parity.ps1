param(
  [string]$AIO        = "C:\c\ai-orchestrator",
  [string]$Frontend   = "C:\Backup_Projects\CFH\frontend",
  [switch]$CommentPR  # add this to post a PR comment via gh
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

$ts         = Get-Date -Format yyyyMMdd_HHmmss
$reports    = Join-Path $AIO "reports"
$funcDir    = Join-Path $reports "functions"
$parityJson = Join-Path $reports ("api_parity_{0}.json" -f $ts)
$parityMd   = Join-Path $reports ("api_parity_{0}.md"   -f $ts)

function Get-FunctionSymbols([string]$Path) {
  $out = New-Object System.Collections.Generic.List[object]
  try {
    $t = Get-Content -LiteralPath $Path -Raw -Encoding UTF8

    foreach($m in [regex]::Matches($t,'(?m)^\s*(export\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')) {
      $exp=[bool]$m.Groups[1].Value; $name=$m.Groups[2].Value; $sig="(" + $m.Groups[3].Value + ")"
      $out.Add([pscustomobject]@{ kind="function"; name=$name; exported=$exp; signature=$sig }) | Out-Null
    }
    foreach($m in [regex]::Matches($t,'(?m)^\s*(export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*\(([^)]*)\)\s*=>')) {
      $exp=[bool]$m.Groups[1].Value; $name=$m.Groups[2].Value; $sig="(" + $m.Groups[3].Value + ") =>"
      $isComponent = $false; if ($name -and $name.Substring(0,1) -cmatch '[A-Z]') { $isComponent = $true }
      $kind = if ($isComponent) { "component" } else { "arrow" }
      $out.Add([pscustomobject]@{ kind=$kind; name=$name; exported=$exp; signature=$sig }) | Out-Null
    }
    foreach($m in [regex]::Matches($t,'(?m)^\s*export\s+default\s+function\s+([A-Za-z0-9_]+)?\s*\(([^)]*)\)')) {
      $nm = if($m.Groups[1].Success){ $m.Groups[1].Value } else { "<default>" }
      $sig= "(" + $m.Groups[2].Value + ")"
      $isComponent = $false; if ($nm -ne "<default>" -and $nm.Substring(0,1) -cmatch '[A-Z]') { $isComponent = $true }
      $kind = if ($isComponent) { "component" } else { "function" }
      $out.Add([pscustomobject]@{ kind=$kind; name=$nm; exported=$true; signature=$sig; isDefault=$true }) | Out-Null
    }
  } catch { }
  $out
}

$results = New-Object System.Collections.Generic.List[object]
$funcJsons = Get-ChildItem $funcDir -File -Filter *.json -ErrorAction SilentlyContinue

foreach($fj in $funcJsons){
  $stem = [IO.Path]::GetFileNameWithoutExtension($fj.Name)      # e.g., myfile
  $orig = Get-Content $fj.FullName -Raw | ConvertFrom-Json
  $genTs  = Join-Path "artifacts\generated" ($stem + ".ts")
  $genTsx = Join-Path "artifacts\generated" ($stem + ".tsx")
  $genFile = $null
  if (Test-Path $genTs)  { $genFile = $genTs }
  if (Test-Path $genTsx) { $genFile = $genTsx }

  if (-not $genFile) {
    $results.Add([pscustomobject]@{
      stem=$stem; status="missing_generated"; missing=@(); extra=@(); orig_count=$orig.Count; gen_count=0
    }) | Out-Null
    continue
  }

  $gen = Get-FunctionSymbols $genFile

  # Compare by exported-ness + name (+ default flag when present)
  function Key($x){
    $def = $false
    if ($x.PSObject.Properties.Name -contains "isDefault") { $def = [bool]$x.isDefault }
    ("{0}|{1}|{2}" -f ($x.exported -as [bool]), $def, ($x.name -as [string]))
  }

  $origKeys = @{}; foreach($o in $orig){ $origKeys[(Key $o)] = $true }
  $genKeys  = @{}; foreach($g in $gen ){ $genKeys[(Key $g)]  = $true }

  $missing = @(); foreach($k in $origKeys.Keys){ if(-not $genKeys.ContainsKey($k)){ $missing += $k } }
  $extra   = @(); foreach($k in $genKeys.Keys){  if(-not $origKeys.ContainsKey($k)){ $extra   += $k } }

  $status = "ok"
  if ($missing.Count -gt 0 -and $extra.Count -gt 0) { $status = "missing_and_extra" }
  elseif ($missing.Count -gt 0) { $status = "missing" }
  elseif ($extra.Count -gt 0)   { $status = "extra" }

  $results.Add([pscustomobject]@{
    stem=$stem; generated=$genFile; status=$status; missing=$missing; extra=$extra;
    orig_count=$orig.Count; gen_count=$gen.Count
  }) | Out-Null
}

$results | ConvertTo-Json -Depth 6 | Set-Content -Path $parityJson -Encoding UTF8

# Markdown summary
$ok      = ($results | ? { $_.status -eq 'ok' }).Count
$mis     = ($results | ? { $_.status -eq 'missing' }).Count
$ext     = ($results | ? { $_.status -eq 'extra' }).Count
$missExt = ($results | ? { $_.status -eq 'missing_and_extra' }).Count
$none    = ($results | ? { $_.status -eq 'missing_generated' }).Count

$lines = @(
  '# API Parity ' + $ts,
  '',
  '* ok: ' + $ok,
  '* missing only: ' + $mis,
  '* extra only: ' + $ext,
  '* missing and extra: ' + $missExt,
  '* no generated file: ' + $none,
  ''
)

foreach ($r in ($results | Sort-Object status, stem)) {
  $lines += ('## ' + $r.stem + ' - ' + $r.status)
  $genVal = if ($r.generated) { [string]$r.generated } else { '<none>' }
  $lines += ('- generated: `' + $genVal + '`')
  if ($r.missing -and $r.missing.Count -gt 0) { $lines += ('- missing: ' + ($r.missing -join ', ')) }
  if ($r.extra   -and $r.extra.Count   -gt 0) { $lines += ('- extra: '   + ($r.extra   -join ', ')) }
  $lines += ''
}

$lines -join "`r`n" | Set-Content -Path $parityMd -Encoding UTF8

Write-Host 'API Parity:'
Write-Host "  JSON: $parityJson"
Write-Host "  MD  : $parityMd"

if ($CommentPR) {
  $up = Get-ChildItem (Join-Path $reports 'upload_*.txt') -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($up) {
    $prUrl = (Get-Content $up.FullName -Raw).Trim()
    try {
      $parts = $prUrl.TrimEnd('/') -split '/'
      $ownerRepo = $parts[3] + '/' + $parts[4]   # carfinancinghub/cfh
      $prNum = [int]$parts[-1]
      & gh pr comment $prNum -R $ownerRepo --body (Get-Content $parityMd -Raw) | Out-Null
      Write-Host "Commented API parity on PR #$prNum"
    } catch {
      Write-Warning "Could not parse PR or post comment: $($_.Exception.Message)"
    }
  } else {
    Write-Warning 'No upload_*.txt found; skipping PR comment.'
  }
}
