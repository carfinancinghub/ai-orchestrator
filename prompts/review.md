# AI Codebase Review Prompt

Inputs:
- reports/<project>/codemap.json (structure, deps, aliases)
- (optional) target repo docs/ (ADRs, openapi, schemas)

Tasks:
1) Evaluate folder structure and alias usage.
2) Identify dead or missing modules; suggest consolidations.
3) Propose service boundaries and a target folder structure.
4) Recommend type safety improvements (DTOs, service interfaces).
5) Propose testing strategy (unit/integration) and CI gates.
6) Outline a migration plan from stubs to implementations.

Output:
- /reports/<project>/review-YYYYMMDD.md (actionable plan)
