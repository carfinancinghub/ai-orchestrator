**********************
PowerShell transcript start
Start time: 20250912103356
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
(.venv) @'
# app/upload_generated.py
from __future__ import annotations
import subprocess, os, sys
from pathlib import Path

def run(cmd: list[str], cwd: str | None = None):
    print("[upload]"," ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=True)

def upload_generated(branch: str="ts-migration/generated", repo_root: str="."):
    repo = Path(repo_root)
    gen  = repo / "artifacts" / "generated"
    if not gen.exists():
        print("[upload] no artifacts/generated to upload")
        return False
    run(["git","fetch","origin"], cwd=repo_root)
    run(["git","checkout","-B", branch], cwd=repo_root)
    run(["git","add", str(gen)], cwd=repo_root)
    run(["git","commit","-m","chore(ts-migration): upload generated TS artifacts"], cwd=repo_root)
    run(["git","push","-u","origin", branch], cwd=repo_root)
    return True

if __name__ == "__main__":
    ok = upload_generated()
    print({"ok": ok})
'@ | Set-Content app\upload_generated.py -Encoding UTF8
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) python -m app.upload_generated 2>&1 | Tee-Object -FilePath $log -Append
>> TerminatingError(out-file): "The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\upload_generated_20250912_1033.md' because it is being used by another process."
>> TerminatingError(out-file): "The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\upload_generated_20250912_1033.md' because it is being used by another process."
The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\upload_generated_20250912_1033.md' because it is being used by another process.
out-file: The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\upload_generated_20250912_1033.md' because it is being used by another process.
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) git add app\upload_generated.py $log

PS C:\c\ai-orchestrator>
(.venv) git commit --allow-empty -m "feat: standalone uploader for artifacts/generated ($ts)"

PS C:\c\ai-orchestrator>
(.venv) git push -u origin fix/restore-report-docs

PS C:\c\ai-orchestrator>
(.venv) $remote = git remote get-url origin 2>$null
PS C:\c\ai-orchestrator>
(.venv) $ownerRepo = ($remote -match "github\.com[:/](.+?)(\.git)?$") ? $Matches[1] : "carfinancinghub/ai-orchestrator"
PS C:\c\ai-orchestrator>
(.venv) $blobUrl = "https://github.com/$ownerRepo/blob/fix/restore-report-docs/" + ($log -replace "\\","/")
PS C:\c\ai-orchestrator>
(.venv) try { Stop-Transcript | Out-Null } catch {}
**********************
PowerShell transcript end
End time: 20250912103400
**********************
