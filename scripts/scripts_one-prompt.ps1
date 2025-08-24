\
    [CmdletBinding()]
    param(
      [ValidateSet('free','premium','wow')][string]$Tier='free',
      [ValidateSet('review','inventory')][string]$PromptKey='review',
      [Parameter(Mandatory=$true)][string]$Root
    )

    # Fail early on missing prereqs
    $ErrorActionPreference = 'Stop'
    Set-Location (Split-Path $MyInvocation.MyCommand.Path)

    Write-Host "[one-prompt] Tier=$Tier Prompt=$PromptKey Root=$Root"

    # Optional: make a codemap before certain prompts
    if ($PromptKey -eq 'inventory') {
      Write-Host "[one-prompt] Building codemap from $Root ..."
      node .\tools\harvest-codemap.mjs "$Root" ".\reports\CFH\codemap.json"
      exit $LASTEXITCODE
    }

    if ($PromptKey -eq 'review') {
      Write-Host "[one-prompt] Making review pack ..."
      powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\make-review-pack.ps1
      exit $LASTEXITCODE
    }

    Write-Warning "Unknown PromptKey: $PromptKey"
    exit 2
