function Detect-GitRepoContext {
  param([string]$RemoteUrl)

  $DomainMap = @{
    "github.com"       = "github"
    "gitlab.com"       = "gitlab"
    "github.mycorp.io" = "github"
    "gitlab.internal"  = "gitlab"
  }

  foreach ($domain in $DomainMap.Keys) {
    if ($RemoteUrl -match "$domain[:/](.+)/(.+?)(\.git)?$") {
      return @{
        Platform  = $DomainMap[$domain]
        Owner     = $matches[1]
        RepoName  = $matches[2]
      }
    }
  }

  return $null
}