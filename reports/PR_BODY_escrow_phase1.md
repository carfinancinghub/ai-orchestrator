Status: green — local API 8121; OpenAI/Gemini/Grok OK; Anthropic skipped.

Scope:
- api/routes: convert/prep, prune, resolve_deps, build_ts (stable)
- reports/: seed + batches, prune map, deps JSON, README_escrow_v1.md
- src/_ai_out/: generated TSX stubs from escrow plans
- scripts/start-api.ps1: helper for install + uvicorn (NoReload or dev)

Artifacts:
- reports/README_escrow_v1.md (27 plans, 125 stubs)
- reports/prune/pruned_escrow.csv
- reports/deps/resolved_deps.json
- reports/logs/escrow_tsc.txt, escrow_ci_note.txt

Notes:
- FRONTEND_ROOT via .env (not committed)
- Ignored: node_modules/, app/services/llm/, __pycache__, *.pyc, reports/artifacts/*.zip
- Next: Phase 3 Redis queue stub for disputes; optional Anthropic enable.

Validation:
- /readyz OK
- build_ts wrote stubs under src/_ai_out
- (Optional) Typecheck log at reports/logs/escrow_tsc.txt
