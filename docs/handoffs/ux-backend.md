# UX Backend handoff — 24 October 2026

Core implementation: `76cb9b9`, precision follow-up `3337b85` on `feat/finboy-ux-backend`, exact starting baseline
`b572565aa521a753fbee1271ca0c68e470ff15c8`. Contract-only bootstrap `2e42622`;
continuation contract `c05b44b`; current contract v1.1.2 in
`docs/ux-round/api-contract.md`. Product can read committed schemas/fixtures through
Git without accessing this worktree. No apps/web, pnpm lockfile or root package
script edits were made. No additional agents/chats were created.

## Implemented and exercised

- Read-only fixed demo; disabled household demo-import mutation; same-scope matching,
  household-only finance/assistant/evidence, and additive non-destructive scope backfill.
- Overdue and uncertain liabilities carried until resolved, including due-day/month
  rollover, inspect/correct/paid/dismissed operations and repaired reconciliation.
- Counted/filterable all-unresolved and historical pages, record 201, stable IDs,
  independent confirmed merge candidates and separated extraction/payment metadata.
- Rollback-only financial impact previews; atomic correction+confirm; reversible
  confirm/reject/reopen/correct/merge/keep-separate decisions; stale-safe undo preserving
  sources, links, locks and revisions. Failed events can be reopened for explicit review.
- Durable import discovery/outcomes/timestamps/issues; successful-source idempotency,
  stable failed-source retry/attempts, targeted Gmail refetch, original-file upload
  recovery, truthful interruption and cancellation checkpoints. Cancel tolerates
  progress generations because it only sets an idempotent monotonic flag.
- IST window/cap metadata and encrypted Gmail continuation; manual scan semantics;
  snapshot tokens combine database generation and IST calculation day.
- Full-scope merchant gross/refund/net totals; relevant income/spending evidence chosen
  before display caps; exact IDs, resolved period, localized fact/warning labels and
  native versus romanized display metadata. Existing speech providers are preserved.
- Authenticated source-aware deletion preview/export and stale deletion rejection,
  surviving-source revalidation, retained-record quarantine when unsupported, and
  allowlisted privacy-safe task outcomes with ownership validation.

## Schema and runtime

Migrations: `0004_ux_trust`, `0005_scan_continuation`, `0006_event_origins`. No destructive migration,
source deletion/reset or canonical value rewriting. Read
`docs/ux-round/data-isolation-operations.md` before production. The inventory command
is read-only and outputs counts only; mixed canonical values remain quarantined for
reviewed operator recovery rather than being blindly declared household data.

Assigned disposable database `finboy_ux_api` on loopback was created independently.
API port 8031 and frontend 3031 are reserved for this owner; Product retains its
8032/3032/finboy_ux_ui allocation. No new OAuth callbacks or provider grants. The
private ignored env has only this disposable runtime's local settings.

## Verification actually performed

- `pnpm check`: passed Ruff/format, **400 backend unit tests**, **19 existing web client
  tests**, ESLint and strict TypeScript. Unit tests require no PostgreSQL.
- `pnpm build`: passed the baseline frontend build. Product changes and integrated
  browser acceptance are still separate gates.
- `pnpm db:migrate`: passed through `0006_event_origins` on finboy_ux_api.
- `pnpm db:check`: no new upgrade operations detected.
- `pnpm test:integration`: **46 passed**, using only the assigned disposable database.
  Includes a pre-upgrade temporary schema with demo/live/mixed provenance and explicit
  canonical value/source/revision preservation assertions; the schema rolls back.
- New trust journeys include failed-upload recovery, targeted Gmail retry/continuation,
  interruption/cancel counters, confirmed merge target/preview/undo, stale write/undo
  conflicts, atomic corrections, old unresolved records and 201 rows, deterministic
  merchant/refund/income evidence, shared-source deletion preview and private export.
  Google HTTP in those tests is mocked; persistence, HTTP routes and extraction are real.
- Read-only voxpay preflight: finboy, nginx and PostgreSQL active; current release
  `/opt/finboy/releases/7bf4587`, roughly 9.9GB free. No production code/data changed.
- `git diff --check`: passed. Provider credentials, bodies and real financial records
  never entered fixtures, Git or operational output.

## Product/integration requirements still open

Consume v1.1.1, including `can_continue`, the continuation action and actual terminal
cancel outcomes. Always use `/transactions/page` for counted history, versioned
`/decisions` for review, previewed privacy deletion and explicit export. Preserve the
production `/` API proxy, host-only cookie and cross-host Gmail handoff. Snapshot
versions are opaque; do not assume an integer. New error codes and exact IDs need
contextual UI, rather than generic connection errors. Source timestamps/coverage
are distinct from health. Root browser scripts belong to Product; preserve Python
commands when adding them.

Agent 1 retains final integration/release ownership. No main merge or deployment
until Product explicitly hands off and stops editing shared integration files.
Then assemble on `feat/finboy-ux-integration`, repeat checks/build/migration/drift/
PostgreSQL and Product's actual UI-to-API browser suite at all three widths. The
F01–F38 matrix currently records backend evidence and pending Product/integration
acceptance; it is not a completion claim. Actual human consent, microphone/phone
playback, screen-reader/device performance and observed comprehension remain explicit.


Follow-up review: literal merchant phrases (for example, a new bookshop) are parsed
as bounded merchant filters rather than falling through to all-spending answers;
merchant and category filters can combine. A regression covers that distinction.
Coverage discovery queries the latest Gmail scan independently of upload-history
volume and treats pre-migration missing windows as unknown. This preserves the
same response schemas. Production read-only provenance inventory returned 26
demo-only transactions, four demo-only obligations, and zero mixed records of either
type. No production mutation or migration was performed for that inventory.


Integration coordination note: a separate human-authorized ingestion eligibility
repair is active on `feat/finboy-ingestion-eligibility`. Its owner is working from
the same baseline in a separate worktree. Preserve its reviewed committed handoff
and any newer main/production state during final assembly; do not edit that tree
or overwrite its protections. The UX Product handoff remains the frontend ownership
gate. Literal merchant/category regressions also cover a merchant name containing
"food", so it cannot silently add a category filter.


Privacy/review closure: migration 0006 preserves original transaction lineage while
manual merges move current evidence. Exact preview/removal now includes origin stubs
and financial decision snapshots, including bill-only derived snapshots. Shared and
source-free manual records survive; loss of the last payment proof reopens review
without replacing values or locks. Unknown older merge lineage blocks deletion before
mutation. Production preflight found zero merged records. Six additional PostgreSQL
cases cover this interaction. Expanded real synthetic HTTP fixtures are in
`docs/ux-round/fixtures/actual-http-v1.json`, validated by unit tests; their explicit
export helper uses only the guarded temporary-user fixture and makes no provider calls.

The local API can run HTTPS on 8031 with a temporary private certificate, scoped to
Node through `NODE_EXTRA_CA_CERTS`, for real same-origin proxy browser checks. Preserve
strict HTTPS validation in production proxy configuration; a frontend test-only
loopback-HTTP exception should be removed during integration in favor of this runtime.
Do not install the test certificate into system trust or use production credentials.
