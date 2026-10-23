# Prompt 4 — A4: Money engine, dashboard, review UX, and demo (full stack)

You are **A4** on FinBoy Phase 1, working in parallel with three other agents. You own
the deterministic money engine every number comes from, the ledger APIs, the main
product UI (shell, dashboard, transactions, review), and the demo runbook. This request
authorizes Phase 1 work defined in `docs/phase1/contract.md`.

**Read first:** `AGENTS.md`, `docs/phase1/contract.md` (§5 schema, §6 engine and money
rules, §7 API, §8 truth table), `README.md`, `apps/web/AGENTS.md` (read the bundled
Next.js docs before writing Next.js code). Do not delegate to subagents.

**Workspace:** branch `phase1/a4-money` in your own git worktree. API 8004, web 3004,
database `finboy_a4` (contract §4 lists what you own; the app shell, landing page and
UI primitives belong to D, the design workstream). A1's
`merge_transactions` / `keep_separate` are stubs on your branch: call them per §6 and
use test doubles in tests.

## Build — backend

1. **Fixture ledger seed** `pnpm seed:fixture-ledger` (dev only, refuses to run in
   production): inserts the §8 truth table directly, including the Hotel Arya `travel`
   miscategory, the 2 review items, a possible-duplicate pair, linked refund/reversal,
   commitments, and plausible `email_sources` / `source_events` / `confidence_factors`,
   so the UI and engine have realistic data before A1's pipeline merges. Mark the rows
   as fixture data in `docs/demo-runbook.md`; the real demo uses the pipeline.
2. **Money engine** (`services/money/engine.py`): implement contract §6 exactly. Keep
   the money rules as pure functions over typed rows (unit-tested without Postgres)
   plus thin SQL loaders (integration-tested). IST calendar periods via
   `core/clock.today_ist()`. Simulation lines + warnings (`pending_review_items`,
   `negative_remaining`, `low_buffer` < 10% of income, `incomplete_coverage`).
3. **API:** `/money/summary`, `/money/commitments`, `POST /money/simulations`,
   `/transactions` (filters: status, category, period, text query; stable ordering),
   `/transactions/{id}` (sources with sender domain, classification, received time,
   extraction method, evidence snippets; confidence factors; revisions),
   `PATCH /transactions/{id}` (category/merchant correction → revision +
   `user_locked_fields` + audit event without amounts), `confirm`, `reject` ("Not
   mine"), `merge` (calls A1 service), `keep-separate`. Validate everything; return
   404 for other users' ids; `Cache-Control: no-store`.

## Build — frontend (presentational components; data in `lib/api/money.ts`,
`lib/api/transactions.ts`, and small hooks)

1. **App shell:** already built by D (`(app)/layout.tsx`, glass sidebar + mobile tab bar).
   Your screens render inside it; ask D for shell changes (e.g. a review-count badge).
2. **Dashboard:** greeting ("Good morning, Arun"); cards for Tracked income, Tracked
   outflows, Upcoming commitments, **Estimated unallocated** with "Based on
   email-derived and confirmed records. Your actual bank balance may differ.";
   category breakdown (simple accessible bars; add a chart library only if truly
   needed); upcoming commitments list; "2 transactions need your help" banner; "How was
   this calculated?" sheet (formula lines, counts, links to evidence); empty state →
   `/connect`.
3. **Transactions:** list grouped by date, filters, detail sheet with confidence label,
   "Why FinBoy added this" checklist from `confidence_factors`, sources, history, and a
   **Correct** form. Correcting Hotel Arya `travel → food_dining` updates the dashboard
   immediately (food ₹6,610 → ₹7,860).
4. **Review queue:** cards per reason: unverified payment / merchant uncertain →
   Confirm, Not mine, Edit; possible duplicate → Merge / Keep separate (side-by-side
   sources). Optimistic UI with rollback on error; refresh summary afterwards.
5. **Stretch (only after the above is verified):** the report's willingness-to-pay
   card ("Keep FinBoy monitoring your finances automatically? ₹199/month · Start
   30-day trial"), recording clicks only if you add a tiny additive migration.

## Demo ownership

- `docs/demo-runbook.md`: exact 3-minute script (connect → import → dedupe → Hotel Arya
  correction → Malayalam voice question → ₹5,000 SIP simulation → privacy), the voice
  lines, expected numbers at each step, `DEMO_TODAY`, reset commands, and fallbacks
  (demo mailbox, `.eml` upload) if Google OAuth fails.
- Visual quality: follow `docs/design-system.md` (light 3D system, `/styleguide`);
  Indian currency formatting via `AnimatedAmount` / `formatRupees`.

## Design system

The UI is a light, 3D, premium system (docs/design-system.md, live at `/styleguide` in
dev). Build your screens from its tokens, `components/ui` primitives, motion primitives
and `<SceneSlot>` scenes; do not add colours, shadows, fonts, animation libraries or WebGL
canvases of your own. The app shell, landing page and primitives belong to D.
Suggested scenes: `check-orb` for confirm moments, `coin-swirl` with `merge` for duplicate merges, `coin-stack` for the simulator. Format money with `AnimatedAmount`/`formatRupees`.

## Done when

- With the fixture seed: dashboard shows ₹62,000 / ₹37,420 / ₹9,800 / ₹14,780; the ₹5,000
  simulation returns ₹9,780 with the pending-review warning; the correction changes food
  from ₹6,610 to ₹7,860; confirm/reject/merge/keep-separate work end to end.
- Tests: money rules (refund netting, transfers excluded, failed/merged/needs_review
  excluded, IST month boundaries, commitments window), simulation warnings, API
  validation and 404s, correction revisions, client schema tests for every response.
- Every screen checked in Chrome at 1440×1000, 390×844, and 320×740, with loading, empty,
  error, and API-offline states; keyboard and screen-reader basics.
- `pnpm check`, `pnpm build`, `pnpm test:integration` pass.

**Final report:** commands + real outcomes, screenshots taken, cross-boundary edits,
new dependencies, known gaps.
