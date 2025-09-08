
Special Pipeline – Multi-Root Scan & Generation
What it does

Scan multiple roots for JS/TS/MD files and classify them as:

test – file name contains .test. or .spec.

letters_only – base name is only A–Z characters

other

Group by base name (e.g., app.jsx, app.tsx → base app) and write a quick audit file.

Generate TS stubs for selected bases into artifacts/generations_special/*.ts.

Persist inventories and a run summary in reports/.

Quick start (PowerShell)
$env:AIO_SCAN_ROOTS = "C:/Backup_Projects/CFH/frontend, $(Get-Location)"
$env:AIO_SPECIAL_EXTS = "js,jsx,ts,tsx,md"
$env:AIO_SKIP_DIRS    = "node_modules,dist,.git"

# Scan only
python -m app.ops_cli scan-special --roots "$env:AIO_SCAN_ROOTS" --exts "$env:AIO_SPECIAL_EXTS" --skip-dirs "$env:AIO_SKIP_DIRS"

# Scan + generate TS stubs
python -m app.ops_cli run-special --mode generate --limit 25 --roots "$env:AIO_SCAN_ROOTS" --exts "$env:AIO_SPECIAL_EXTS" --skip-dirs "$env:AIO_SKIP_DIRS"

# Optional narrowing
# --only-tests   # just *.test.* / *.spec.*
# --only-letters # just bases with letters only

Outputs

Reports (./reports):

grouped_files.txt – one line per base → comma-separated full paths

special_inventory_<run_id>.csv – columns: base, ext, category, path

special_scan_<run_id>.json – summary { run_id, counts, outputs }

Artifacts (./artifacts):

generations_special/<base>.ts – generated TS stub per base

Tip

If you see old *.gen.json files in artifacts/generations_special, remove them:

Get-ChildItem artifacts/generations_special -Filter *.gen.json -File | Remove-Item -Force

Configuration

Environment variables (optional):

AIO_SCAN_ROOTS – comma-separated absolute paths to scan

AIO_SPECIAL_EXTS – extensions to include (default: js,jsx,ts,tsx,md)

AIO_SKIP_DIRS – directory name filters to skip

CLI flags (--roots, --exts, --skip-dirs, --only-tests, --only-letters) take precedence.

How bases are chosen

Files are grouped by basename (filename without extension). During generation, a heuristic computes a worth_score and a recommendation (keep | merge | discard). The generator emits a minimal, syntactically valid stub per base.

Examples

List inventory rows:

Get-Content reports/special_inventory_<run_id>.csv -TotalCount 100


Inspect generated stubs:

Get-ChildItem artifacts/generations_special -Filter *.ts -File | Sort-Object LastWriteTime -Desc | Select-Object -First 10 | Format-Table Name,Length

Troubleshooting

No items found: ensure --roots is quoted and points to existing paths.

Too many files: use --only-tests or --only-letters, or lower --limit.

Old .gen.json files: clean as shown above.

Windows paths: prefer absolute paths in AIO_SCAN_ROOTS.

Next steps

Wire generation outputs into the main staging flow.

Script a PR to the target repo after review.
