# Path: reports/README_special.md
# SPECIAL mode (multi-root scan)

## What it does
- Scans multiple roots for JS/TS/MD files (skip: `node_modules`, `dist`, `.git`).
- Classifies by basename and emits:
  - `reports/grouped_files.txt`
  - `reports/special_inventory_<run_id>.csv`
  - `reports/special_scan_<run_id>.json`
- Optional review/generate stubs with `run-special`.

## Commands
```powershell
$env:AIO_SCAN_ROOTS = "C:/Backup_Projects/CFH/frontend, C:/c/ai-orchestrator"
python -m app.ops_cli scan-special --roots $env:AIO_SCAN_ROOTS --exts "js,jsx,ts,tsx,md" --skip-dirs "node_modules,dist,.git"

python -m app.ops_cli run-special  --roots $env:AIO_SCAN_ROOTS --exts "js,jsx,ts,tsx,md" --skip-dirs "node_modules,dist,.git" --mode review --limit 50
python -m app.ops_cli run-special  --roots $env:AIO_SCAN_ROOTS --exts "js,jsx,ts,tsx,md" --skip-dirs "node_modules,dist,.git" --mode all --limit 25

Outputs

reports/grouped_files.txt: basename: file1, file2, ...

reports/special_inventory_<run_id>.csv: base, ext, category, path

reports/review_summary_special_<run_id>.json: heuristic scores

artifacts/generations_special/*.ts: only when --mode generate|all

