**********************
PowerShell transcript start
Start time: 20250912033857
Username: Agasi\Agasi5
RunAs User: Agasi\Agasi5
Configuration Name: 
Machine: AGASI (Microsoft Windows NT 10.0.26100.0)
Host Application: C:\Program Files\PowerShell\7\pwsh.dll
Process ID: 15788
PSVersion: 7.5.2
PSEdition: Core
GitCommitId: 7.5.2
OS: Microsoft Windows 10.0.26100
Platform: Win32NT
PSCompatibleVersions: 1.0, 2.0, 3.0, 4.0, 5.0, 5.1, 6.0, 7.0
PSRemotingProtocolVersion: 2.3
SerializationVersion: 1.1.0.1
WSManStackVersion: 3.0
**********************
PS C:\c\ai-orchestrator> Write-Host "== Phase: cd to orchestrator =="
== Phase: cd to orchestrator ==
PS C:\c\ai-orchestrator> Set-Location $AIO
PS C:\c\ai-orchestrator> Write-Host "== Phase: Python venv =="
== Phase: Python venv ==
PS C:\c\ai-orchestrator> # Use local venv to avoid global site-packages noise
PS C:\c\ai-orchestrator> $venv = Join-Path $AIO ".venv"
PS C:\c\ai-orchestrator> if (!(Test-Path $venv)) {
  python -m venv $venv
}
PS C:\c\ai-orchestrator> # activate (PowerShell)
PS C:\c\ai-orchestrator> & "$venv\Scripts\Activate.ps1"
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) Write-Host "== Phase: Install requirements (if present) =="
== Phase: Install requirements (if present) ==
PS C:\c\ai-orchestrator>
(.venv) if (Test-Path ".\requirements.txt") { python -m pip install -U pip && pip install -r requirements.txt }


PS C:\c\ai-orchestrator>
(.venv) elseif (Test-Path ".\requirements-dev.txt") { python -m pip install -U pip && pip install -r requirements-dev.txt }
elseif: The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
elseif: The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
(.venv) else { python -m pip install -U pip }  # still upgrade pip for sanity
else: The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
else: The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) Write-Host "== Phase: Health check =="
== Phase: Health check ==
PS C:\c\ai-orchestrator>
(.venv) # If there is a health endpoint (optional)
PS C:\c\ai-orchestrator>
(.venv) try {
  curl.exe http://127.0.0.1:8021/health
} catch { Write-Host "health endpoint not responding yet (ok)" }
{"status":"ok","app":"cfh-orchestrator"}
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) Write-Host "== Phase: run-special smoke (limit 5) =="
== Phase: run-special smoke (limit 5) ==
PS C:\c\ai-orchestrator>
(.venv) # IMPORTANT: we are in the repo root, so 'app.ops_cli' should resolve
PS C:\c\ai-orchestrator>
(.venv) python -m app.ops_cli run-special --mode all --limit 5 --roots "$env:AIO_SCAN_ROOTS" --exts "$env:AIO_SPECIAL_EXTS" --skip-dirs "$env:AIO_SKIP_DIRS"

PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) Write-Host "== Phase: Snapshot artifacts / grouped_files / gates =="
== Phase: Snapshot artifacts / grouped_files / gates ==
PS C:\c\ai-orchestrator>
(.venv) if (Test-Path ".\artifacts\generations_special") {
  Write-Host "-- artifacts\generations_special (first 5 files) --"
  Get-ChildItem .\artifacts\generations_special -File | Select-Object -First 5 | Format-Table Name,Length
  $firstGen = Get-ChildItem .\artifacts\generations_special -File | Select-Object -First 1
  if ($firstGen) {
    Write-Host "-- head of $($firstGen.Name) --"
    Get-Content $firstGen.FullName -TotalCount 120
  }
}
-- artifacts\generations_special (first 5 files) --

Name                            Length
----                            ------
adminemailnotifications.test.ts    139
adminemailnotifications.ts         129
alias_check.ts                     119
app_test.ts                        110
app.test.ts                         99

-- head of adminemailnotifications.test.ts --
// Auto-generated stub for adminemailnotifications.test
export function adminemailnotifications.test(...args: any[]): any { /* TODO */ }
PS C:\c\ai-orchestrator>
(.venv) if (Test-Path ".\artifacts\generated") {
  Write-Host "-- artifacts\generated (tree) --"
  Get-ChildItem .\artifacts\generated -Recurse -File | Format-Table FullName,Length
}
-- artifacts\generated (tree) --
PS C:\c\ai-orchestrator>
(.venv) if (Test-Path ".\reports\grouped_files.txt") {
  Write-Host "-- grouped_files (head) --"
  Get-Content .\reports\grouped_files.txt -TotalCount 80
}
-- grouped_files (head) --
$I2H07PR: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$I2H07PR.js, C:\cfh\TruthSource\clean\js\$I2H07PR.js, C:\cfh\TruthSource\clean\ts\$I2H07PR.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$I2H07PR.js
$I2H07PR.test: C:\cfh\TruthSource\clean\ts\$I2H07PR.test.ts
$I2H07PR.test_1: C:\cfh\TruthSource\clean\ts\$I2H07PR.test_1.ts
$I2H07PR_1: C:\cfh\TruthSource\clean\js\$I2H07PR_1.js, C:\cfh\TruthSource\clean\ts\$I2H07PR_1.ts
$I2TCQIF: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$I2TCQIF.js, C:\cfh\TruthSource\clean\js\$I2TCQIF.js, C:\cfh\TruthSource\clean\ts\$I2TCQIF.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$I2TCQIF.js
$I2TCQIF.test: C:\cfh\TruthSource\clean\ts\$I2TCQIF.test.ts
$I2TCQIF.test_1: C:\cfh\TruthSource\clean\ts\$I2TCQIF.test_1.ts
$I2TCQIF_1: C:\cfh\TruthSource\clean\js\$I2TCQIF_1.js, C:\cfh\TruthSource\clean\ts\$I2TCQIF_1.ts
$I6521SG: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$I6521SG.js, C:\cfh\TruthSource\clean\js\$I6521SG.js, C:\cfh\TruthSource\clean\ts\$I6521SG.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$I6521SG.js
$I6521SG.test: C:\cfh\TruthSource\clean\ts\$I6521SG.test.ts
$I6521SG.test_1: C:\cfh\TruthSource\clean\ts\$I6521SG.test_1.ts
$I6521SG_1: C:\cfh\TruthSource\clean\js\$I6521SG_1.js, C:\cfh\TruthSource\clean\ts\$I6521SG_1.ts
$I7Q64XR: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$I7Q64XR.js, C:\cfh\TruthSource\clean\js\$I7Q64XR.js, C:\cfh\TruthSource\clean\ts\$I7Q64XR.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$I7Q64XR.js
$I7Q64XR.test: C:\cfh\TruthSource\clean\ts\$I7Q64XR.test.ts
$I7Q64XR.test_1: C:\cfh\TruthSource\clean\ts\$I7Q64XR.test_1.ts
$I7Q64XR_1: C:\cfh\TruthSource\clean\js\$I7Q64XR_1.js, C:\cfh\TruthSource\clean\ts\$I7Q64XR_1.ts
$I8347GR: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$I8347GR.js, C:\cfh\TruthSource\clean\js\$I8347GR.js, C:\cfh\TruthSource\clean\ts\$I8347GR.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$I8347GR.js
$I8347GR.test: C:\cfh\TruthSource\clean\ts\$I8347GR.test.ts
$I8347GR.test_1: C:\cfh\TruthSource\clean\ts\$I8347GR.test_1.ts
$I8347GR_1: C:\cfh\TruthSource\clean\js\$I8347GR_1.js, C:\cfh\TruthSource\clean\ts\$I8347GR_1.ts
$I9P8YQX: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$I9P8YQX.js, C:\cfh\TruthSource\clean\js\$I9P8YQX.js, C:\cfh\TruthSource\clean\ts\$I9P8YQX.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$I9P8YQX.js
$I9P8YQX.test: C:\cfh\TruthSource\clean\ts\$I9P8YQX.test.ts
$I9P8YQX.test_1: C:\cfh\TruthSource\clean\ts\$I9P8YQX.test_1.ts
$I9P8YQX_1: C:\cfh\TruthSource\clean\js\$I9P8YQX_1.js, C:\cfh\TruthSource\clean\ts\$I9P8YQX_1.ts
$IAN0K1W: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IAN0K1W.js, C:\cfh\TruthSource\clean\js\$IAN0K1W.js, C:\cfh\TruthSource\clean\ts\$IAN0K1W.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IAN0K1W.js
$IAN0K1W.test: C:\cfh\TruthSource\clean\ts\$IAN0K1W.test.ts
$IAN0K1W.test_1: C:\cfh\TruthSource\clean\ts\$IAN0K1W.test_1.ts
$IAN0K1W_1: C:\cfh\TruthSource\clean\js\$IAN0K1W_1.js, C:\cfh\TruthSource\clean\ts\$IAN0K1W_1.ts
$ICU46LY: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$ICU46LY.js, C:\cfh\TruthSource\clean\js\$ICU46LY.js, C:\cfh\TruthSource\clean\ts\$ICU46LY.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$ICU46LY.js
$ICU46LY.test: C:\cfh\TruthSource\clean\ts\$ICU46LY.test.ts
$ICU46LY.test_1: C:\cfh\TruthSource\clean\ts\$ICU46LY.test_1.ts
$ICU46LY_1: C:\cfh\TruthSource\clean\js\$ICU46LY_1.js, C:\cfh\TruthSource\clean\ts\$ICU46LY_1.ts
$II0SLOI: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$II0SLOI.js, C:\cfh\TruthSource\clean\js\$II0SLOI.js, C:\cfh\TruthSource\clean\ts\$II0SLOI.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$II0SLOI.js
$II0SLOI.test: C:\cfh\TruthSource\clean\ts\$II0SLOI.test.ts
$II0SLOI.test_1: C:\cfh\TruthSource\clean\ts\$II0SLOI.test_1.ts
$II0SLOI_1: C:\cfh\TruthSource\clean\js\$II0SLOI_1.js, C:\cfh\TruthSource\clean\ts\$II0SLOI_1.ts
$IIB1TND: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IIB1TND.js, C:\cfh\TruthSource\clean\js\$IIB1TND.js, C:\cfh\TruthSource\clean\ts\$IIB1TND.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IIB1TND.js
$IIB1TND.test: C:\cfh\TruthSource\clean\ts\$IIB1TND.test.ts
$IIB1TND.test_1: C:\cfh\TruthSource\clean\ts\$IIB1TND.test_1.ts
$IIB1TND_1: C:\cfh\TruthSource\clean\js\$IIB1TND_1.js, C:\cfh\TruthSource\clean\ts\$IIB1TND_1.ts
$IIYB9CP: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IIYB9CP.js, C:\cfh\TruthSource\clean\js\$IIYB9CP.js, C:\cfh\TruthSource\clean\ts\$IIYB9CP.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IIYB9CP.js
$IIYB9CP.test: C:\cfh\TruthSource\clean\ts\$IIYB9CP.test.ts
$IIYB9CP.test_1: C:\cfh\TruthSource\clean\ts\$IIYB9CP.test_1.ts
$IIYB9CP_1: C:\cfh\TruthSource\clean\js\$IIYB9CP_1.js, C:\cfh\TruthSource\clean\ts\$IIYB9CP_1.ts
$IJ8J2KP: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IJ8J2KP.js, C:\cfh\TruthSource\clean\js\$IJ8J2KP.js, C:\cfh\TruthSource\clean\ts\$IJ8J2KP.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IJ8J2KP.js
$IJ8J2KP.test: C:\cfh\TruthSource\clean\ts\$IJ8J2KP.test.ts
$IJ8J2KP.test_1: C:\cfh\TruthSource\clean\ts\$IJ8J2KP.test_1.ts
$IJ8J2KP_1: C:\cfh\TruthSource\clean\js\$IJ8J2KP_1.js, C:\cfh\TruthSource\clean\ts\$IJ8J2KP_1.ts
$ILA1E7N: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$ILA1E7N.js, C:\cfh\TruthSource\clean\js\$ILA1E7N.js, C:\cfh\TruthSource\clean\ts\$ILA1E7N.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$ILA1E7N.js
$ILA1E7N.test: C:\cfh\TruthSource\clean\ts\$ILA1E7N.test.ts
$ILA1E7N.test_1: C:\cfh\TruthSource\clean\ts\$ILA1E7N.test_1.ts
$ILA1E7N_1: C:\cfh\TruthSource\clean\js\$ILA1E7N_1.js, C:\cfh\TruthSource\clean\ts\$ILA1E7N_1.ts
$IMERYVT: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IMERYVT.js, C:\cfh\TruthSource\clean\js\$IMERYVT.js, C:\cfh\TruthSource\clean\ts\$IMERYVT.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IMERYVT.js
$IMERYVT.test: C:\cfh\TruthSource\clean\ts\$IMERYVT.test.ts
$IMERYVT.test_1: C:\cfh\TruthSource\clean\ts\$IMERYVT.test_1.ts
$IMERYVT_1: C:\cfh\TruthSource\clean\js\$IMERYVT_1.js, C:\cfh\TruthSource\clean\ts\$IMERYVT_1.ts
$ISA3BXZ: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$ISA3BXZ.js, C:\cfh\TruthSource\clean\js\$ISA3BXZ.js, C:\cfh\TruthSource\clean\ts\$ISA3BXZ.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$ISA3BXZ.js
$ISA3BXZ.test: C:\cfh\TruthSource\clean\ts\$ISA3BXZ.test.ts
$ISA3BXZ.test_1: C:\cfh\TruthSource\clean\ts\$ISA3BXZ.test_1.ts
$ISA3BXZ_1: C:\cfh\TruthSource\clean\js\$ISA3BXZ_1.js, C:\cfh\TruthSource\clean\ts\$ISA3BXZ_1.ts
$ISGT3J2: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$ISGT3J2.js, C:\cfh\TruthSource\clean\js\$ISGT3J2.js, C:\cfh\TruthSource\clean\ts\$ISGT3J2.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$ISGT3J2.js
$ISGT3J2.test: C:\cfh\TruthSource\clean\ts\$ISGT3J2.test.ts
$ISGT3J2.test_1: C:\cfh\TruthSource\clean\ts\$ISGT3J2.test_1.ts
$ISGT3J2_1: C:\cfh\TruthSource\clean\js\$ISGT3J2_1.js, C:\cfh\TruthSource\clean\ts\$ISGT3J2_1.ts
$IT49040: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IT49040.js, C:\cfh\TruthSource\clean\js\$IT49040.js, C:\cfh\TruthSource\clean\ts\$IT49040.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IT49040.js
$IT49040.test: C:\cfh\TruthSource\clean\ts\$IT49040.test.ts
$IT49040.test_1: C:\cfh\TruthSource\clean\ts\$IT49040.test_1.ts
$IT49040_1: C:\cfh\TruthSource\clean\js\$IT49040_1.js, C:\cfh\TruthSource\clean\ts\$IT49040_1.ts
$IUFDKGD: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IUFDKGD.js, C:\cfh\TruthSource\clean\js\$IUFDKGD.js, C:\cfh\TruthSource\clean\ts\$IUFDKGD.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IUFDKGD.js
$IUFDKGD.test: C:\cfh\TruthSource\clean\ts\$IUFDKGD.test.ts
$IUFDKGD.test_1: C:\cfh\TruthSource\clean\ts\$IUFDKGD.test_1.ts
$IUFDKGD_1: C:\cfh\TruthSource\clean\js\$IUFDKGD_1.js, C:\cfh\TruthSource\clean\ts\$IUFDKGD_1.ts
$IV1DCG4: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IV1DCG4.js, C:\cfh\TruthSource\clean\js\$IV1DCG4.js, C:\cfh\TruthSource\clean\ts\$IV1DCG4.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IV1DCG4.js
$IV1DCG4.test: C:\cfh\TruthSource\clean\ts\$IV1DCG4.test.ts
$IV1DCG4.test_1: C:\cfh\TruthSource\clean\ts\$IV1DCG4.test_1.ts
$IV1DCG4_1: C:\cfh\TruthSource\clean\js\$IV1DCG4_1.js, C:\cfh\TruthSource\clean\ts\$IV1DCG4_1.ts
$IVSWZ0J: C:\Backup_Projects\CFH\frontend\allprojectfilename\38662233-374818866-1006\$IVSWZ0J.js, C:\cfh\TruthSource\clean\js\$IVSWZ0J.js, C:\cfh\TruthSource\clean\ts\$IVSWZ0J.ts, C:\cfh\allprojectfilename\38662233-374818866-1006\$IVSWZ0J.js
$IVSWZ0J.test: C:\cfh\TruthSource\clean\ts\$IVSWZ0J.test.ts
$IVSWZ0J.test_1: C:\cfh\TruthSource\clean\ts\$IVSWZ0J.test_1.ts
$IVSWZ0J_1: C:\cfh\TruthSource\clean\js\$IVSWZ0J_1.js, C:\cfh\TruthSource\clean\ts\$IVSWZ0J_1.ts
PS C:\c\ai-orchestrator>
(.venv) $gates = Get-ChildItem .\reports -Include gates_*.json -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
PS C:\c\ai-orchestrator>
(.venv) if ($gates) {
  Write-Host "-- gates json (head) --"
  Get-Content $gates.FullName -TotalCount 80
}
-- gates json (head) --
{
  "run_id": "smoke_real",
  "timestamp": 1757428836.501771,
  "dry_run": false,
  "frontend": "C:\\Backup_Projects\\CFH\\frontend",
  "tooling": {
    "npm_bin": "C:\\Users\\Agasi5\\AppData\\Roaming\\npm\\npm.cmd"
  },
  "steps": {
    "build": {
      "cmd": "cmd.exe /c C:\\Users\\Agasi5\\AppData\\Roaming\\npm\\npm.cmd run build",
      "exit": 1,
      "pass": false,
      "tail": [
        "",
        "> frontend@0.0.0 build",
        "> vite build",
        "",
        "\u001b[36mvite v5.4.19 \u001b[32mbuilding for production...\u001b[36m\u001b[39m",
        "transforming...",
        "\u001b[32m\u00e2\u0153\u201c\u001b[39m 68 modules transformed.",
        "\u001b[31mx\u001b[39m Build failed in 529ms",
        "\u001b[31merror during build:",
        "\u001b[31m[vite]: Rollup failed to resolve import \"socket.io-client\" from \"C:/Backup_Projects/CFH/frontend/src/components/common/UnreadNotificationBadge.jsx\".",
        "This is most likely unintended because it can break your application at runtime.",
        "If you do want to externalize this module explicitly add it to",
        "`build.rollupOptions.external`\u001b[31m",
        "    at viteWarn (file:///C:/Backup_Projects/CFH/frontend/node_modules/vite/dist/node/chunks/dep-C6uTJdX2.js:65839:17)",
        "    at onwarn (file:///C:/Backup_Projects/CFH/frontend/node_modules/@vitejs/plugin-react/dist/index.js:89:7)",
        "    at onRollupWarning (file:///C:/Backup_Projects/CFH/frontend/node_modules/vite/dist/node/chunks/dep-C6uTJdX2.js:65869:5)",
        "    at onwarn (file:///C:/Backup_Projects/CFH/frontend/node_modules/vite/dist/node/chunks/dep-C6uTJdX2.js:65534:7)",
        "    at file:///C:/Backup_Projects/CFH/frontend/node_modules/rollup/dist/es/shared/node-entry.js:20898:13",
        "    at Object.logger [as onLog] (file:///C:/Backup_Projects/CFH/frontend/node_modules/rollup/dist/es/shared/node-entry.js:22770:9)",
        "    at ModuleLoader.handleInvalidResolvedId (file:///C:/Backup_Projects/CFH/frontend/node_modules/rollup/dist/es/shared/node-entry.js:21514:26)",
        "    at file:///C:/Backup_Projects/CFH/frontend/node_modules/rollup/dist/es/shared/node-entry.js:21472:26\u001b[39m"
      ]
    },
    "test": {
      "cmd": "cmd.exe /c C:\\Users\\Agasi5\\AppData\\Roaming\\npm\\npm.cmd test",
      "exit": -1,
      "pass": false,
      "tail": [
        "Command '['cmd.exe', '/c', 'C:\\\\Users\\\\Agasi5\\\\AppData\\\\Roaming\\\\npm\\\\npm.cmd', 'test']' timed out after 240 seconds"
      ]
    },
    "lint": {
      "cmd": "cmd.exe /c C:\\Users\\Agasi5\\AppData\\Roaming\\npm\\npm.cmd run lint",
      "exit": 0,
      "pass": true,
      "tail": [
        "",
        "> frontend@0.0.0 lint",
        "> eslint \"src/**/*.{ts,tsx}\"",
        "",
        "",
        "C:\\Backup_Projects\\CFH\\frontend\\src\\components\\title\\BulkTitleTransfer.tsx",
        "  23:30  warning  'userId' is defined but never used. Allowed unused args must match /^_/u  @typescript-eslint/no-unused-vars",
        "",
        "\u00e2\u0153\u2013 1 problem (0 errors, 1 warning)",
        ""
      ]
    }
  }
}
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) Write-Host "== Phase: Compute GitHub blob URL & write SUMMARY =="
== Phase: Compute GitHub blob URL & write SUMMARY ==
PS C:\c\ai-orchestrator>
(.venv) # Compute owner/repo and URL
PS C:\c\ai-orchestrator>
(.venv) $remote = git -C $AIO remote get-url origin 2>$null
PS C:\c\ai-orchestrator>
(.venv) if ($remote -match "github\.com[:/](.+?)(\.git)?$") { $ownerRepo = $Matches[1] } else { $ownerRepo = "carfinancinghub/ai-orchestrator" }
PS C:\c\ai-orchestrator>
(.venv) $AIOposix = ($AIO -replace "\\","/"); $logPosix = ($log -replace "\\","/")
PS C:\c\ai-orchestrator>
(.venv) $rel = ($logPosix.StartsWith("$AIOposix/")) ? $logPosix.Substring($AIOposix.Length + 1) : $logPosix
PS C:\c\ai-orchestrator>
(.venv) $blobUrl = "https://github.com/$ownerRepo/blob/$BRANCH/$rel"
PS C:\c\ai-orchestrator>
(.venv) "`n## SUMMARY`n**GitHub log:** $blobUrl`n" | Out-File $log -Append -Encoding UTF8
>> TerminatingError(Out-File): "The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\orchestrator_smoke_20250912_0338.md' because it is being used by another process."
Out-File: The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\orchestrator_smoke_20250912_0338.md' because it is being used by another process.
Out-File: The process cannot access the file 'C:\c\ai-orchestrator\reports\debug\orchestrator_smoke_20250912_0338.md' because it is being used by another process.
PS C:\c\ai-orchestrator>
(.venv) New-Item -ItemType Directory -Force -Path (Split-Path $sum) | Out-Null
PS C:\c\ai-orchestrator>
(.venv) $blobUrl | Out-File $sum -Encoding UTF8
PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) Write-Host "== Phase: Git push logs =="
== Phase: Git push logs ==
PS C:\c\ai-orchestrator>
(.venv) git -C $AIO config commit.gpgsign false | Out-Null
PS C:\c\ai-orchestrator>
(.venv) if (-not (git -C $AIO config user.email)) { git -C $AIO config user.email "ci@local" | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) if (-not (git -C $AIO config user.name))  { git -C $AIO config user.name  "Local CI" | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) $env:GIT_ASKPASS = "echo"
PS C:\c\ai-orchestrator>
(.venv) git -C $AIO fetch origin 2>$null | Out-Null
PS C:\c\ai-orchestrator>
(.venv) $existsLocal  = (git -C $AIO branch --list $BRANCH)
PS C:\c\ai-orchestrator>
(.venv) $existsRemote = (git -C $AIO ls-remote --heads origin $BRANCH)
PS C:\c\ai-orchestrator>
(.venv) if     ($existsLocal)  { git -C $AIO switch $BRANCH                | Out-Null }
PS C:\c\ai-orchestrator>
(.venv) elseif ($existsRemote) { git -C $AIO switch -c $BRANCH origin/$BRANCH | Out-Null }
elseif: The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
elseif: The term 'elseif' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
(.venv) else                   { git -C $AIO checkout -B $BRANCH           | Out-Null }
else: The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
else: The term 'else' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
PS C:\c\ai-orchestrator>
(.venv) git -C $AIO add -- $log $sum

PS C:\c\ai-orchestrator>
(.venv) git -C $AIO commit --allow-empty --no-verify -m "debug: orchestrator smoke ($ts)" | Out-Null
PS C:\c\ai-orchestrator>
(.venv) git -C $AIO push -u origin $BRANCH

PS C:\c\ai-orchestrator>
PS C:\c\ai-orchestrator>
(.venv) # Stop transcript (flush log)
PS C:\c\ai-orchestrator>
(.venv) try { Stop-Transcript | Out-Null } catch {}
**********************
PowerShell transcript end
End time: 20250912033914
**********************
