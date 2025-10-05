# CFH Module Review (Batch)
Blueprint Excerpt (Module: {{module}}):
{{blueprint_excerpt}}

## Goals
- Generate AuctionModule.md with:
  - Overview (purpose, deps)
  - File Summaries (key extracts: functions like handleBid(), TS gaps)
  - Consolidated Specs (unified types, e.g., interface BidProps)
  - Risks & Suggestions (R&S)
- Tiers: 
  - Free: basic extracts
  - Premium: @ alias usage and typed props
  - Wow++: monetization hooks, real-time / AbortController examples

## Inputs
CSV: {{csv_path}}
Files: (contents inlined below)
{{files_block}}

## Output Must Include
- `## Overview`
- `## File Summaries`
- `## Consolidated Specs`
- `## Risks & Suggestions`
- `## Tiered Plan` (Free / Premium / Wow++)
- `## TS Build Plan` (list of .ts/.tsx to generate, folders, tests)
