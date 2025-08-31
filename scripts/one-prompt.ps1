# Path: C:\c\ai-orchestrator\scripts\one-prompt.ps1
# Version: 0.2.0
# Last Updated: 2025-08-30 20:52 PDT
# Purpose: PowerShell script to trigger CFH AI-Orchestrator migration runs
param (
    [string]$PromptKey = "convert",
    [string]$Tier = "free",
    [string]$Root = "",
    [int]$Port = 8020,
    [string]$Org = "",
    [string]$User = "",
    [string]$RepoName = "",
    [string]$Platform = "github",
    [string]$Branches = "main",
    [int]$BatchOffset = 0,
    [int]$BatchLimit = 100,
    [switch]$TriggerWorkflow
)

Write-Host "== CFH One-Prompt : $PromptKey / $Tier =="

$uri = "http://127.0.0.1:$Port/run-one"
$body = @{
    prompt_key = $PromptKey
    tier = $Tier
    root = $Root
    org = $Org
    user = $User
    repo_name = $RepoName
    platform = $Platform
    branches = $Branches
    batch_offset = $BatchOffset
    batch_limit = $BatchLimit
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType "application/json" -TimeoutSec 600 -ErrorAction Stop
    Write-Host ($response | ConvertTo-Json -Depth 10)
}
catch {
    Write-Host "Error: $_"
    Write-Host "Metrics: $($_.Exception.Response | ConvertFrom-Json | ConvertTo-Json -Depth 10)"
    exit 1
}

if ($TriggerWorkflow) {
    Write-Host "== Triggering GitHub workflow convert.yml =="
    try {
        $ghToken = $env:GITHUB_TOKEN
        $workflowUri = "https://api.github.com/repos/$Org/ai-orchestrator/actions/workflows/convert.yml/dispatches"
        $workflowBody = @{ ref = "main" } | ConvertTo-Json
        Invoke-RestMethod -Uri $workflowUri -Method Post -Headers @{ Authorization = "Bearer $ghToken"; Accept = "application/vnd.github.v3+json" } -Body $workflowBody -TimeoutSec 30
        Write-Host "== Done =="
    }
    catch {
        Write-Host "Error triggering workflow: $_"
        exit 1
    }
}