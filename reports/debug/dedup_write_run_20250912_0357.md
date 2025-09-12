**********************
PowerShell transcript start
Start time: 20250912035740
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
(.venv) # File 1: app/utils/numeric_junk.py
PS C:\c\ai-orchestrator>
(.venv) $new1 = "app\utils\numeric_junk.py"
PS C:\c\ai-orchestrator>
(.venv) New-Item -ItemType Directory -Force -Path "app\utils" | Out-Null
PS C:\c\ai-orchestrator>
(.venv) @'
# app/utils/numeric_junk.py
from pathlib import Path
import os
import re
from typing import Iterable

_DIGIT_RUN = int(os.getenv("AIO_NUMERIC_JUNK_DIGITS", "3"))
_ALLOWLIST = {s.strip().lower() for s in os.getenv("AIO_NUMERIC_ALLOWLIST", "").split(",") if s.strip()}

def is_numeric_junk(path: str) -> bool:
    stem = Path(path).stem.lower()
    if stem in _ALLOWLIST:
        return False
    if re.fullmatch(r"[\d\W]+", stem):
        return True
    if re.search(rf"\d{{{_DIGIT_RUN},}}", stem):
        return True
    return False

def filter_non_junk(paths: Iterable[str]) -> Iterable[str]:
    for p in paths:
        if not is_numeric_junk(p):
            yield p
'@ | Out-File $new1 -Encoding UTF8
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # File 2: scripts/dedup_numeric.py
PS C:\c\ai-orchestrator>
(.venv) $new2 = "scripts\dedup_numeric.py"
PS C:\c\ai-orchestrator>
(.venv) New-Item -ItemType Directory -Force -Path "scripts" | Out-Null
PS C:\c\ai-orchestrator>
(.venv) @'
# scripts/dedup_numeric.py
from pathlib import Path
import csv
import os
from collections import defaultdict
from app.utils.numeric_junk import is_numeric_junk

ROOTS = [p.strip() for p in os.getenv("AIO_SCAN_ROOTS", "").split(",") if p.strip()]
SKIP  = {p.strip().lower() for p in os.getenv("AIO_SKIP_DIRS", "").split(",") if p.strip()}

OUT_DIR   = Path("reports")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH  = OUT_DIR / "duplicates_eliminated.csv"
CAND_PATH = OUT_DIR / "conversion_candidates.txt"

EXTS = {".js", ".jsx", ".ts", ".tsx"}

def in_skip_parts(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(s in parts for s in SKIP)

def main() -> None:
    candidates = []
    for root in ROOTS:
        r = Path(root)
        if not r.exists():
            continue
        for p in r.rglob("*"):
            if not p.is_file(): continue
            if in_skip_parts(p): continue
            if p.suffix.lower() not in EXTS: continue
            if is_numeric_junk(str(p)): continue
            candidates.append(p)

    groups = defaultdict(list)
    for p in candidates:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        key = (p.stem.lower(), size)
        groups[key].append(p)

    kept, eliminated = [], []
    for key, files in groups.items():
        files_sorted = sorted(files, key=lambda z: (0 if z.suffix.lower() in {".ts", ".tsx"} else 1, str(z).lower()))
        best = files_sorted[0]
        kept.append(best)
        eliminated.extend((best, other) for other in files_sorted[1:])

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kept", "eliminated"])
        for best, other in eliminated:
            w.writerow([str(best), str(other)])

    with CAND_PATH.open("w", encoding="utf-8") as f:
        for c in kept:
            f.write(str(c) + "\n")

    print(f"[dedup] kept={len(kept)} eliminated={len(eliminated)} groups={len(groups)}")
    print(f"[dedup] wrote {CSV_PATH} and {CAND_PATH}")

if __name__ == "__main__":
    main()
'@ | Out-File $new2 -Encoding UTF8
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # 2) Run dedup (UTF-8 tolerant)
PS C:\c\ai-orchestrator>
(.venv) $env:PYTHONIOENCODING = "utf-8:replace"
PS C:\c\ai-orchestrator>
(.venv) $env:AIO_SCAN_ROOTS = "C:/Backup_Projects/CFH/frontend,C:/Backup_Projects/CFH/backend,C:/cfh,C:/TruthSource,C:/cfh_backup_20250713,C:/cfh_backup20250713,M:/cfh"
PS C:\c\ai-orchestrator>
(.venv) $env:AIO_SKIP_DIRS  = "node_modules,dist,.git,build,coverage,storybook-static,.next,.turbo,.yarn,.pnpm-store,.cache,out"
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) if (!(Test-Path ".venv")) { python -m venv .venv }
PS C:\c\ai-orchestrator>
(.venv) & ".venv\Scripts\Activate.ps1"
PS C:\c\ai-orchestrator>
(.venv) python -m pip install -U pip > $null
PS C:\c\ai-orchestrator>
(.venv) python scripts\dedup_numeric.py

PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # Show report heads
PS C:\c\ai-orchestrator>
(.venv) Write-Host "`n-- HEAD: reports\duplicates_eliminated.csv --"

-- HEAD: reports\duplicates_eliminated.csv --
PS C:\c\ai-orchestrator>
(.venv) Get-Content reports\duplicates_eliminated.csv -TotalCount 40
>> TerminatingError(Get-Content): "The running command stopped because the preference variable "ErrorActionPreference" or common parameter is set to Stop: Cannot find path 'C:\c\ai-orchestrator\reports\duplicates_eliminated.csv' because it does not exist."
>> TerminatingError(Get-Content): "The running command stopped because the preference variable "ErrorActionPreference" or common parameter is set to Stop: Cannot find path 'C:\c\ai-orchestrator\reports\duplicates_eliminated.csv' because it does not exist."
The running command stopped because the preference variable "ErrorActionPreference" or common parameter is set to Stop: Cannot find path 'C:\c\ai-orchestrator\reports\duplicates_eliminated.csv' because it does not exist.
Get-Content: Cannot find path 'C:\c\ai-orchestrator\reports\duplicates_eliminated.csv' because it does not exist.
PS C:\c\ai-orchestrator>
(.venv) Write-Host "`n-- HEAD: reports\conversion_candidates.txt --"

-- HEAD: reports\conversion_candidates.txt --
PS C:\c\ai-orchestrator>
(.venv) Get-Content reports\conversion_candidates.txt -TotalCount 80
>> TerminatingError(Get-Content): "The running command stopped because the preference variable "ErrorActionPreference" or common parameter is set to Stop: Cannot find path 'C:\c\ai-orchestrator\reports\conversion_candidates.txt' because it does not exist."
>> TerminatingError(Get-Content): "The running command stopped because the preference variable "ErrorActionPreference" or common parameter is set to Stop: Cannot find path 'C:\c\ai-orchestrator\reports\conversion_candidates.txt' because it does not exist."
The running command stopped because the preference variable "ErrorActionPreference" or common parameter is set to Stop: Cannot find path 'C:\c\ai-orchestrator\reports\conversion_candidates.txt' because it does not exist.
Get-Content: Cannot find path 'C:\c\ai-orchestrator\reports\conversion_candidates.txt' because it does not exist.
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # 3) Commit & push (note: .gitignore may ignore reports/debug/*.txt; we force-add)
PS C:\c\ai-orchestrator>
(.venv) git config commit.gpgsign false | Out-Null
PS C:\c\ai-orchestrator>
(.venv) if (-not (git config user.email)) { git config user.email "ci@local" | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) if (-not (git config user.name))  { git config user.name  "Local CI" | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) $env:GIT_ASKPASS = "echo"
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
>> TerminatingError(): "The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again."
The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
elseif: The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
(.venv) else                   { git checkout -B $BRANCH | Out-Null }
>> TerminatingError(): "The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again."
The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
else: The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) git add -- $new1 $new2

PS C:\c\ai-orchestrator>
(.venv) git add -f -- reports\duplicates_eliminated.csv reports\conversion_candidates.txt

PS C:\c\ai-orchestrator>
(.venv) git add -f -- $log

PS C:\c\ai-orchestrator>
(.venv) git commit --allow-empty --no-verify -m "feat: numeric-junk filter + dedup runner ($ts)" | Out-Null
PS C:\c\ai-orchestrator>
(.venv) git push -u origin $BRANCH

PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # 4) Print a GitHub URL for the log (so I can click it)
PS C:\c\ai-orchestrator>
(.venv) $remote = git remote get-url origin 2>$null
PS C:\c\ai-orchestrator>
(.venv) $ownerRepo = ($remote -match "github\.com[:/](.+?)(\.git)?$") ? $Matches[1] : "carfinancinghub/ai-orchestrator"
PS C:\c\ai-orchestrator>
(.venv) $repoPosix = ($PWD.Path -replace "\\","/")
PS C:\c\ai-orchestrator>
(.venv) $logPosix  = ($log -replace "\\","/")
PS C:\c\ai-orchestrator>
(.venv) $relLog    = $logPosix.Substring($repoPosix.Length + 1)
PS C:\c\ai-orchestrator>
(.venv) $blobUrl   = "https://github.com/$ownerRepo/blob/$BRANCH/$relLog"
PS C:\c\ai-orchestrator>
(.venv) try { Stop-Transcript | Out-Null } catch {}
**********************
PowerShell transcript end
End time: 20250912035748
**********************
