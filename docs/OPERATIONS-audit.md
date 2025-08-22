# File: docs/OPERATIONS-audit.md
## What this does
- **Plan**: reads your inventories at `C:\CFH\TruthSource\docs\...`, de-dups, prefers TS/TSX, emits CSV/JSON.
- **Convert**: creates `.ts/.tsx` next to JS/JSX for in-root candidates.
- **Commit**: batches existing TS files via `core/git_ops.py`.
- **Quarantine**: moves problematic files under `artifacts/quarantine/YYYYMMDD/<reason>/` and logs a row in `artifacts/quarantine_manifest.jsonl`.

## Commands
- Plan only:
  ```powershell
  ./scripts/audit-run.ps1 -Root "C:\Backup_Projects\CFH"

Plan + Convert + Commit:

./scripts/audit-run.ps1 -Root "C:\Backup_Projects\CFH" -Convert -Commit


Show quarantine:

./scripts/quarantine-review.ps1 -Port 8010 -List -Limit 20


Restore from quarantine:

./scripts/quarantine-review.ps1 -Port 8010 -Restore @("artifacts\quarantine\YYYYMMDD\outside_root\file.js")
