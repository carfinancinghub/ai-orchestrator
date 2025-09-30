# Usage Guide

- `scripts\fix-gh-auth.ps1` — repairs GitHub CLI auth (clears env tokens, refreshes scopes).
- `scripts\gh-smoke.ps1` — **read-only** check across repos in `configs\repos.json`.
- `scripts\test-gh-access.ps1` — **read+write** test (clone, temp branch push, cleanup). Saves CSV/JSON/MD under `reports\local_checks\<ts>`.
- `scripts\orchestrator-smoke.ps1` — health + convert dry-run against local ai-orchestrator.

Edit `configs\repos.json` to add or remove repositories.
