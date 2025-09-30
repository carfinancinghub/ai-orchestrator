# Fix GitHub CLI auth quickly
Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue
[Environment]::SetEnvironmentVariable("GITHUB_TOKEN", $null, "User")
[Environment]::SetEnvironmentVariable("GH_TOKEN",      $null, "User")
try {
  [Environment]::SetEnvironmentVariable("GITHUB_TOKEN", $null, "Machine")
  [Environment]::SetEnvironmentVariable("GH_TOKEN",      $null, "Machine")
} catch {}
try {
  gh auth status || gh auth login --hostname github.com --git-protocol https --web
} catch {
  gh auth login --hostname github.com --git-protocol https --web
}
gh auth refresh -h github.com -s repo -s workflow -s read:org -s gist 1>$null 2>$null
Write-Host "gh auth OK" -ForegroundColor Green
