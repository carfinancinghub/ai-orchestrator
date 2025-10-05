# Gemini 5-Step – md-first Generation (Auctions)

## System intent
You are generating **.md-first blueprints** for a TypeScript migration. Each .md MUST:
1) Start with a **Functions summary** (names, signatures, responsibilities)
2) Provide a **dependencies** array (repo aliases allowed, e.g., "@services/escrowHold.ts")
3) End with **TS plan** sketches (files to generate and brief implementation notes)

## Tiers
- **Free**: Industry-basic extracts, generic domain. No CFH-specific models or paywalled logic.
- **Premium**: Use interfaces / @aliases (e.g., @models/Vehicle), validation rules.
- **Wow++**: Full TS sketches & monetization primitives (e.g., bid fees), async flows.

## Input
- Batch CSVs with candidate file paths and sizes
- Blueprint hint: "Auctions: Bid + escrow"

## Output Schema (YAML fenced)
```yaml
functions:    # list of function specs
  - name: string
    signature: string
    summary: string
    confidence: 0.0..1.0
types:
  - name: string
    summary: string
dependencies:
  - string  # e.g., "@services/auctionBids.ts"
integrates_with:
  - string
plan:
  - file: string
    notes: string
Guardrails
Keep total content per .md under ~1500 tokens.

Confidence < 0.85 → mark but keep in schema (builder will stub).

Prefer @aliases over hard paths when possible.

Example head
php
Copy code
# Auction Module – Functions & Integrations (md-first)

## Functions (summary)
- handleBid(vin: string, amount: number): Promise<BidResult> ...

## Dependencies
...