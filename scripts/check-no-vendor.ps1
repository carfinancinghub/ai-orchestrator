# scripts/check-no-vendor.ps1
# Purpose: Fail CI (and local pre-commit) if *tracked* vendor directories or vendor archives are committed.
# IMPORTANT: Only checks tracked files via `git ls-files` to avoid scanning local build caches.

$ErrorActionPreference = 'Stop'

# Ensure UTF-8 symbols print correctly on WinPS5
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}

# Get tracked files only
$tracked = & git ls-files 2>$null

if (-not $tracked) {
  Write-Host "vendor guard ✅ (no tracked files)"
  exit 0
}

# Blocked directory segments (if they appear in a tracked path)
$blockedDirSeg = '(^|[\\/])(node_modules|vendor)([\\/]|$)'

# Blocked archive extensions (if they are committed)
# We generally don't want binary archives committed; allowlist known report paths below if needed.
$blockedArchiveExt = '\.(zip|tar|tar\.gz|tgz|rar)$'

# Allowlist: tracked items that are explicitly OK (regexes)
# Keep this small. Add only if you truly *must* track a blocked pattern.
$allow = @(
  # Example: '^reports[\\/].*\.zip$'
  # Example: '^artifacts[\\/].*\.tar\.gz$'
)

# Filter blocked directories from tracked files
$dirHits = $tracked | Where-Object { $_ -match $blockedDirSeg }

# Filter blocked archives from tracked files
$arcHits = $tracked | Where-Object { $_ -match $blockedArchiveExt }

# Apply allowlist
function Remove-Allowed($paths, $allowPatterns) {
  if (-not $paths) { return @() }
  $kept = @()
  foreach ($p in $paths) {
    $isAllowed = $false
    foreach ($pat in $allowPatterns) {
      if ($p -match $pat) { $isAllowed = $true; break }
    }
    if (-not $isAllowed) { $kept += $p }
  }
  return $kept
}

$dirHits = Remove-Allowed $dirHits $allow
$arcHits = Remove-Allowed $arcHits $allow

if ($dirHits.Count -gt 0 -or $arcHits.Count -gt 0) {
  if ($dirHits.Count -gt 0) {
    Write-Host "❌ vendor directories tracked in Git:"
    $dirHits | ForEach-Object { Write-Host " - $_" }
  }
  if ($arcHits.Count -gt 0) {
    Write-Host "❌ vendor/binary archives tracked in Git:"
    $arcHits | ForEach-Object { Write-Host " - $_" }
  }
  throw "vendor guard failed."
}

Write-Host "vendor guard ✅"
exit 0
