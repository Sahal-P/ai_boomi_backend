# Frontend freshness review — 24 October 2026

Before this change, local main, both GitHub main branches and the production Vercel
deployment `dpl_FxHRPZc4AafXHUpADCz769KnHvAj` pointed to
`1c3560cfbad2fd4417ad1b7ba79c471a4062f105`. The committed UX frontend and backend
owner branches were already ancestors of main. No UX branch merge was missing.

Two unpublished mobile layout edits remained in the Product worktree. Reviewed
copies of its HEAD diff now let the Overview period selector shrink beside Refresh
at 320 px and give header actions the full phone width. Copying its entire Overview
file would have reverted three newer `overview_explanation_opened` outcome names;
those integration changes are preserved.

The older design branch `phase1/d-design-3d` has a later commit `24055d2`. Only the
three reviewed refinements since the previously integrated design snapshot are
included: hero reveal waits for warm rendered frames, tight channel bends are eased,
and acrylic clearcoat fades at grazing angles. The current graphics-off fallback,
marketing routes, privacy copy and product flows are preserved. A wholesale merge
of the old branch would reintroduce stale product code and is unnecessary. This is
a selective snapshot integration, not an assertion that its Git tip is an ancestor.

The original design and Product worktrees remain untouched. No backend, dependency,
schema, access, provider or production data changes accompany this release. The
scoped backend release remains `3098a14`; do not roll it back to pre-scope code.

Validation on the final application changes:

- `pnpm check`: Ruff/format, ESLint and strict TypeScript pass; 584 backend unit
  tests and 37 web tests pass. The 49 database integration tests are intentionally
  deselected by that command; no database changes were made.
- `NEXT_PUBLIC_API_URL=/ pnpm build`: production build passes.
- `E2E_PORT=3040 E2E_REUSE_SERVER=1 pnpm --filter @finboy/web exec playwright test
  e2e/overview.spec.ts e2e/layout.spec.ts --workers=2`: 32 pass, four intentional
  device-specific skips. These synthetic browser journeys include connected,
  secondary-panel failure, offline/recovery and graphics-off states.
- Chrome at 1440×1000, 390×844 and 320×740: the production-build landing page reaches
  a ready WebGL hero, retains usable content/actions and has no horizontal overflow
  or console errors. A pre-existing Three.Clock deprecation warning remains.

The browser tests use the test-only API double and local production build, not the
household backend. Production deployment identity and read-only checks are verified
separately after publication; no fixture or test suite runs against production.
