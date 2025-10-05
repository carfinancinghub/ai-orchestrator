# CFH 5-Step — Batch Markdown Generator (Gemini)
You are generating *md-first* reviews for a batch of files. Output MUST include:
- The headings “Free Tier”, “Premium Tier”, “Wow++ Tier” for each file section.
- A single JSON fenced block per section with **both** fields: "suggested_moves" and "dependencies".
- Lead with a concise functions/content summary (first 2–4 bullets).
- Keep total output under ~1500 tokens across all sections.

{{files_block}}

> Stick to terse, high-signal writing. Use @-aliases when proposing dependencies (e.g., @services/escrow/*).
