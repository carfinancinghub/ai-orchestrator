
Reusable Commands — 20250923_0843
Feed rebuild (every 30 minutes, relaxed)
powershell
Copy code
pwsh scripts/schedule_feed_rebuild.ps1 -Minutes 30 -RelaxHumanish
Batch run (≤25)
powershell
Copy code
pwsh .orchestrator\gen25_batch.ps1 -Root C:\Backup_Projects\CFH\frontend -Out artifacts\generated
Lint check (hard mode)
powershell
Copy code
pwsh scripts/cfh_lint_local.ps1 -OutPath C:\Backup_Projects\CFH\frontend\reports\cfh_lint_summary.json -HardMode
