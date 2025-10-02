# Migration Plan — BuyerCommunityForum.tsx

## Goals
- Convert legacy file to **TypeScript, type-safe**.
- Preserve functionality and intent.
- Align with 3-tier model: **free**, **premium**, **wow++**.

## Detected Functions
- *(none detected; UI-only or declarative component?)*

## Tier Assignments (heuristic)
- **free**: *(none)*
- **premium**: *(none)*
- **wow++**: *(none)*

## TypeScript Contract
- Prefer explicit props types and return types.
- Use discriminated unions where applicable.
- No `any`; use `unknown` and narrow.

## File Actions
- Generate `.md` spec (this document).
- Generate `.ts`/`.tsx` candidate that matches this spec.
- Run reviewer pass to verify the candidate matches spec.

## Non-Functional
- Keep imports relative and stable.
- Avoid side effects in module scope.
- Ensure testability.

