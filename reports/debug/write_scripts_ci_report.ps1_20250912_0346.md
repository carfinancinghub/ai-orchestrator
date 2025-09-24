**********************
PowerShell transcript start
Start time: 20250912034659
Username: Agasi\Agasi5
RunAs User: Agasi\Agasi5
Configuration Name: 
Machine: AGASI (Microsoft Windows NT 10.0.26100.0)
Host Application: C:\Program Files\PowerShell\7\pwsh.dll
Process ID: 63212
PSVersion: 7.5.3
PSEdition: Core
GitCommitId: 7.5.3
OS: Microsoft Windows 10.0.26100
Platform: Win32NT
PSCompatibleVersions: 1.0, 2.0, 3.0, 4.0, 5.0, 5.1, 6.0, 7.0
PSRemotingProtocolVersion: 2.3
SerializationVersion: 1.1.0.1
WSManStackVersion: 3.0
**********************
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) Write-Host "Wrote $REL"
Wrote scripts\ci\report.ps1
PS C:\c\ai-orchestrator>
(.venv) git config commit.gpgsign false | Out-Null
PS C:\c\ai-orchestrator>
(.venv) if (-not (git config user.email)) { git config user.email "ci@local" | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) if (-not (git config user.name))  { git config user.name  "Local CI" | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) $env:GIT_ASKPASS = "echo"
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # 3) Commit & push
PS C:\c\ai-orchestrator>
(.venv) git fetch origin 2>$null | Out-Null
PS C:\c\ai-orchestrator>
(.venv) $existsLocal  = (git branch --list $BRANCH)
PS C:\c\ai-orchestrator>
(.venv) $existsRemote = (git ls-remote --heads origin $BRANCH)
PS C:\c\ai-orchestrator>
(.venv) if     ($existsLocal)  { git switch $BRANCH | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) elseif ($existsRemote) { git switch -c $BRANCH origin/$BRANCH | Out-Null }
elseif: The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
elseif: The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
(.venv) else                   { git checkout -B $BRANCH | Out-Null }
else: The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
else: The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
