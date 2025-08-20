# Rivers Auction Platform Feature and Standard Guide
Author: Grok (built by xAI) - Compiled on August 17, 2025
Path: C:\c\ai-orchestrator\docs\standards.md

## Overview
The Rivers Auction platform is a comprehensive auction marketplace for vehicles, with features for buyers, sellers, haulers, guests, and admins. It emphasizes AI-driven tools (e.g., strategy coaching, cost forecasting, risk assessment), premium gating (Free, Premium, Wow++/Enterprise tiers), real-time collaboration, analytics, and monetization. The ecosystem is modular, using React for frontend, Node.js for backend, and TypeScript/JavaScript for code. Crown Certified standards ensure modularity (standalone components/utilities), scalability (reusable across modules), and error handling (try-catch, logging, user feedback).

Key modules include:
- Hauler coordination (e.g., transport booking, route optimization, roadside assistance).
- Guest/new user dashboard (auctions, onboarding).
- Buyer search preferences (AI suggestions, alerts).
- Escrow tracking (status updates, releases).
- Risk assessment (vehicle risk prediction, dispute integration).
- Utilities for sharing, exports, and data aggregation.

This guide serves as a reference for AI evaluation during file review, conversion to TypeScript, value extraction, and function completeness checks. It outlines standards, features by tier, naming conventions, comment formats, and TODO/Suggestions placement.

## Features by Tier
**Free:**
- Basic rendering and interactions (e.g., view auctions, set preferences, track escrow status).
- Simple risk assessment (mileage, age, accidents).
- Exports in CSV (e.g., auction data).
- Onboarding and basic dashboard views.

**Premium:**
- AI-driven suggestions (e.g., search preferences, strategy coaching).
- Basic real-time updates (e.g., WebSocket for status changes).
- Enhanced exports (e.g., PDF summaries).

**Wow++ (Enterprise):**
- Advanced AI (e.g., cost forecasting, route optimization, dispute outcome integration).
- Real-time alerts (e.g., roadside assistance, dispute notifications).
- Detailed analytics (e.g., transport history charts, carrier performance scorecards).
- Social sharing (badges, summaries).
- Automated workflows (e.g., escrow releases, risk updates).
- Cross-module insights (e.g., marketplace analytics, dispute voting exports).

**Evaluation Check:** Ensure files implement tiered features correctly, with gating for Premium/Wow++.

## Naming Conventions
- **.ts** utilities: `camelCase` (e.g., `haulerBucket.ts`, `auctionExportUtils.ts`)
- **.tsx** components: `PascalCase` (e.g., `BookingModal.tsx`, `GuestDashboard.tsx`)
- **.test.ts** tests: `<source>.test.ts` (e.g., `haulerBucket.test.ts`)
- **.md** docs: `<source>` (e.g., `haulerBucket.md`)

**Evaluation Check:** Verify file names follow conventions; suggest renames if needed.

## Comment Block Formatting
**Code (.ts, .tsx):**
- File Header: `// File, Path, Author, Purpose, Status`
- Section Headers: `// === Section Name ===`
- Function Comments: Purpose, Inputs, Outputs
- TODOs/Suggestions: end of file: `// === TODOs and Suggestions ===`
- Functions Summary: bullet list (Purpose, Inputs, Outputs, Dependencies)

**Tests (.test.ts):** mirror the above; use `describe` blocks.

**Docs (.md):** 
- Use `# + ##` headers, bold where helpful, lists, code blocks.
- `## TODOs and Suggestions` at end.

**Evaluation Check:** Ensure comments are formatted correctly; add missing sections during conversion.

## TODO or Suggestions Placement
**Code:** end of file, before exports:
