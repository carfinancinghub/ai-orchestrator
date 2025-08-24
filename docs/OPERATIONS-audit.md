## Rollback
## Path: docs/OPERATIONS-audit.md (append)

If a batch of conversions needs to be undone:

1. Identify the commit(s) created by `/audit/js/commit`. They include messages like `audit: add N TS files`.
2. Use `git revert <commitSha>` for each commit you want to roll back.
3. If files were quarantined and later restored incorrectly, re-run `scripts/quarantine-review.ps1 -Restore -Paths ...` to put them back in quarantine for manual review.

## FAQ

**Q: I see `outside_root` in results. What does it mean?**  
A: The source file resolved path is not under `workspace_root` (or `root_override`). Update the root or skip these entries.

**Q: Why `wrote=0`?**  
A: Most common reasons: `missing` (file no longer exists) or candidates exceeded the guardrail and the call was rejected. Run a `dry-run` or lower thresholds.

**Q: Where are metrics?**  
A: `artifacts/audit_metrics.jsonl` — one line per file event plus a summary per run. Append-only.
