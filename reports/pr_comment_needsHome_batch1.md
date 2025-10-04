**Status:** Orchestrator running; /readyz OK; providers enabled (OpenAI, Gemini, Grok, Anthropic).

**Batch:** _needsHome_
- **Run A (≥0.70, execute):** 12 files moved, 25 docs mirrored  
- **Run B (≥0.85, dry+execute):** 0 moves (conservative threshold), 30 docs mirrored

**Artifacts:**
- Routing audit: $(C:\c\ai-orchestrator\reports\routing_audit_reviews_20251003_161205.csv.FullName)
- Reviews JSON: $(C:\c\ai-orchestrator\reports\reviews_20251003_161205.json.FullName)

**Notes:**
- Rules are intentionally conservative; many candidates cluster in 0.70–0.84.
- Docs mirroring to C:\CFH\docs\frontend\src\components\... verified.

**Next steps proposed:**
1) Tune reviewer keyword/heuristics to push more suggestions ≥0.85.  
2) Run Batch 2 (50–100 files) from 
eedsHome and produce audit + docs.  
3) Optional: enable automove at threshold ≥0.80 with PR-attached audit.
