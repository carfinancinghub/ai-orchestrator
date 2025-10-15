# CFH Frontend Batch Review — {{review_tier|default("free")}} tier

## Context
You are reviewing files from the CFH (Car Financing Hub) React/TypeScript codebase. Your goal is to:
- Propose a **target feature folder** for each file (e.g., `buyer`, `seller`, `admin`, `escrow`, `analytics`, `mechanic`, etc.).
- Output a short **reason** tied to code cues (imports, component names, test hints).
- Provide a lightweight, commit-friendly **markdown** snippet per file.

### Folder hints
- Buyer/checkout flows → `buyer/`
- Seller/listing tools → `seller/`
- Admin dashboards/notifications → `admin/`
- Escrow/payment, KYC, risk → `escrow/`
- Analytics/metrics → `analytics/`
- Mechanics/haulers/logistics → `mechanic/` or `hauler/`
- Auth/i18n/shared hooks/components → `common/` or `shared/`

## Output format
For EACH file, write a section exactly like this:

### File: `{{relative_path}}`
**Type:** `.{{ext}}`  |  **Suggested Dest:** `{{feature}}`  |  **Confidence:** `{{confidence}}`

**Why**
- One short bullet that cites concrete code cues (imports, function/component names, comments)

**Sketch (tier-dependent)**
- **free**: 1-2 bullets of what the file does.
- **premium**: add notable types/interfaces and any `@alias` imports you would standardize (e.g., `@/models`, `@/hooks`).
- **wow**: add a 3-5 line pseudo-TS sketch for one core function (no execution, no external calls).

**Suggested Moves (JSON)**  
```json
{
  "path": "{{relative_path}}",
  "moves": [
    {
      "dest": "{{feature_path}}",
      "confidence": {{confidence_float}},
      "reason": "short reason anchored to code cues"
    }
  ]
}
