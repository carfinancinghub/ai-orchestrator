# ai-orchestrator — Public Audit Index (Run 20250923_2212)

This page aggregates the public links, current status, and next steps so SG Man can verify the orchestrator is production-ready.

## Core Public Links

- [.gitattributes](https://github.com/carfinancinghub/ai-orchestrator/blob/main/.gitattributes)
- [CI](https://github.com/carfinancinghub/ai-orchestrator/blob/main/.github/workflows/ci.yml)
- [CFH Lint Workflow](https://github.com/carfinancinghub/ai-orchestrator/blob/main/.github/workflows/cfh-lint.yml)
- [Gate — No Vendor](https://github.com/carfinancinghub/ai-orchestrator/blob/main/scripts/check-no-vendor.ps1)
- [Gate — No JS (staged, with exceptions)](https://github.com/carfinancinghub/ai-orchestrator/blob/main/scripts/check-no-js.ps1)
- [CFH Lint Script](https://github.com/carfinancinghub/ai-orchestrator/blob/main/scripts/cfh_lint.ps1)
- [Orchestrator core — ops.py](https://github.com/carfinancinghub/ai-orchestrator/blob/main/app/ops.py)
- [Synthesis — synthesize-ts.mjs](https://github.com/carfinancinghub/ai-orchestrator/blob/main/app/synthesize-ts.mjs)

## AI Review Content (Tiered TS guidance)

- [ai_review_20250923_084351.md](https://github.com/carfinancinghub/ai-orchestrator/blob/main/reports/ai_review_20250923_084351.md)
- [ai_reviews.md (index)](https://github.com/carfinancinghub/ai-orchestrator/blob/main/reports/ai_reviews.md)

## Verification Artifacts

- [Cod1 verification table (latest)](https://github.com/carfinancinghub/ai-orchestrator/blob/main/reports/debug/cod1_validation_results_20250923_2212.md)

---

## Status Snapshot

- ✅ Repo visibility: **public**
- ✅ `.gitattributes` normalized (LF, binary tags, linguist vendored)
- ✅ CI vendor gate wired (`check-no-vendor.ps1`)
- ✅ JS/JSX gate wired (`check-no-js.ps1`) — staged-only, with reasonable exceptions
- ✅ **CFH_LINT_SOFT: "0"** (hard mode) in workflow
- ✅ Tiered AI review page updated (`Free / Premium / Wow++` with `ts` fences)
- ✅ Public verification results published

## What’s Next (blocked on CFH repo tasks)

1. **Upload ≤25 TS/TSX** into **carfinancinghub/cfh** PR **#17** from `artifacts/generated/<runId>/` (overwrite-safe via SHA1).
2. **Run gates** for that PR (AIO + CFH lint); confirm green.
3. **Merge PR #17**.
4. **E2E smoke** of orchestrator: produce new review JSONs + `.md` and confirm the generated TS adheres to the tiered patterns.

If any gate fails, capture the failing path(s) and post back here so we can tune allow-lists or patterns.

---

## Notes for Review

- The tiered `.md` enforces patterns like `LoanTerms`, `LoanTermsValidated`, and `LoanTermsAI` (with deterministic `estimateMonthly`).
- We keep **debug reports tracked** on purpose so SG Man can audit runs; vendor gate excludes only true vendor/artefact directories.
- Where possible we use LF on disk and binary tagging for non-text; Windows users still get CRLF on checkout via Git’s eol config.

---

*Prepared for SG Man oversight — Run 20250923_2212*
