function Get-RawGitHubUrl {
  [CmdletBinding()] param([Parameter(Mandatory=$true)][string]$Path,[string]$Ref)
  function Normalize([string]$p){$abs=[IO.Path]::GetFullPath($p);($abs -replace '\\','/').TrimEnd('/')}
  $repoRoot=(git rev-parse --show-toplevel).Trim(); if(-not $repoRoot){throw "Not a git repo"}
  $rootN=Normalize $repoRoot; $full=Normalize (Resolve-Path -LiteralPath $Path).Path
  if(-not $full.StartsWith("$rootN/",[StringComparison]::OrdinalIgnoreCase)-and -not($full -eq $rootN)){throw "Path must be inside repo root: $rootN (got: $full)"}
  $rel=$full.Substring($rootN.Length).TrimStart('/')
  $remote=(git remote get-url origin).Trim()
  if($remote -match 'github\.com[:/](.+?)/(.+?)(?:\.git)?$'){ $owner=$matches[1]; $repo=$matches[2] } else { throw "Unsupported remote: $remote" }
  if(-not $Ref){ $Ref=(git rev-parse --abbrev-ref HEAD).Trim() } if($Ref -eq 'HEAD'){ $Ref=(git rev-parse HEAD).Trim() }
  $relWeb=$rel -replace '\\','/'; $encoded=[Uri]::EscapeDataString($relWeb) -replace '%2F','/'
  $url="https://raw.githubusercontent.com/$owner/$repo/$Ref/$encoded"; Write-Host $url; return $url
}
