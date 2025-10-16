# Orchestrator Inventory (20250914_014145)

## Tools
- Node: v22.19.0
- Python: Python 3.13.7
- gh: gh version 2.78.0 (2025-08-21)
- Branch: fix/restore-report-docs

## Key files
- app\ops.py (size: 27327 bytes; modified: 9/13/2025 7:05:35 AM)
- app\ops_cli.py (size: 12418 bytes; modified: 9/8/2025 3:08:50 PM)
- app\dedup.py (size: 274 bytes; modified: 9/12/2025 9:18:31 PM)
- app\providers\gemini.py (missing)
- app\providers\grok.py (missing)
- app\github_uploader.py (missing)
- scripts\publish_all.ps1 (size: 1838 bytes; modified: 9/13/2025 11:21:10 PM)
- scripts\analyze_and_comment.ps1 (size: 1948 bytes; modified: 9/14/2025 12:05:04 AM)
- scripts\synthesize_and_commit.ps1 (size: 3078 bytes; modified: 9/13/2025 11:58:08 PM)
- scripts\ship_it.ps1 (size: 1778 bytes; modified: 9/14/2025 12:09:29 AM)
- .env (size: 1437 bytes; modified: 9/5/2025 10:36:51 AM)

### Scripts ternary check ('? :')
- Found ternary-like usage in: audit-run.ps1

## .env keys present (names only)
- AIO_PROVIDERS: set
- AIO_UPLOAD_TS: missing
- AIO_MAX_FILES_PER_PR: set

