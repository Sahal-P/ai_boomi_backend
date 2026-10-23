# Agent 1 — final money API handoff

Branch: `feat/finboy-money-api`.
Verified implementation head: `76a128ac1bfab81b819eb27c7db376d5dadf7d59`.
The following handoff-only commit changes documentation; resolve the final branch
head with `git rev-parse feat/finboy-money-api`. Frozen base stays `fd618ae`.
Worktree: `/Users/sahal/.codex/worktrees/finboy-money-api/ai_boom`.
Runtime environment checked: local PostgreSQL `127.0.0.1:5433/finboy_p1`,
nonproduction `test`, `DEMO_TODAY=2026-10-28`, exact CORS/web origins on 3011,
public API URL on 8011. No final integration database/ports were used.

## Delivered behavior

The unchanged contract §6 money models and public signatures now load user-scoped
SQL records and calculate integer-paise INR totals in pure functions. Confirmed
income, net refunds/reversals, transfer/status exclusions, inclusive IST months,
upcoming date windows, category totals, evidence IDs/counts, and all four simulation
warnings are implemented without LLM arithmetic or runtime fixture totals.

Every specified money/transaction route is implemented. Transaction lists remain
arrays; details and successful mutations return exactly
`{transaction, sources, confidence_factors, revisions}`. Period query:
`period=current_month`, or `period=month&year=2026&month=10`. List filters add closed
status/category, literal case-insensitive merchant `q`, and limit 1–200 (default 50).
Corrections allow only category, merchant, and positive integer `amount_minor`.
Merge request is `{keep_id}`; the path ID is merged into it, and the returned detail
is for that path ID, now `merged`. Keep-separate still requires explicit confirmation.

Typed actual response examples for Agent 2/Agent 3 are in
`docs/handoffs/agent-1-api-examples.json`, first published in `2a5fb4a`.
They include before/after summaries, transaction arrays, a three-source detail,
correction revisions/locks, commitments, simulation, request bodies, and safe errors.
`docs/money.md` specifies count, category/refund, warning, transition, audit, and
error semantics. All finance route responses use no-store and redacted error IDs;
write origins are checked before mutation.

Review services own commit/rollback and share A1 ingestion's per-user advisory
transaction lock. Writes call ledger services, preserve immutable source evidence,
write revisions/locked fields, and preserve user decisions on re-import. Necessary
ledger fixes: reject terminal-record merges, make repeated separation idempotent,
reopen a paid obligation when its recorded payment is rejected/amount-corrected,
and refresh confidence from moved merge evidence while locking the kept status/
dedupe choice. Merge redirects refund/source/paid-commitment links.

`pnpm seed:fixture-ledger` now calls existing A2 import orchestration over A1's real
rendered 42-message mailbox, in rules mode with provider calls disabled. It accepts
only local nonproduction `finboy_p1` and is idempotent. It does not construct a
parallel fake ledger or seed expected totals. The development ledger is currently
seeded and Hotel Arya was corrected while exporting examples; re-import preserves
that decision. Agent 5 should use the existing demo import flow for its own database.

## Exact verification and observed outcomes

| Command / check | Actual outcome |
| --- | --- |
| `uv sync --locked --all-packages` | Passed; no dependency/lockfile edits |
| `pnpm install --frozen-lockfile` | Passed; no npm/lockfile edits |
| `pnpm env:setup` and private worktree configuration | Passed; ignored env files mode 600 |
| `pnpm db:up` | Shared container already running and healthy; never stopped/deleted |
| `docker compose exec -T postgres createdb -U finboy finboy_p1` | Created isolated disposable DB |
| `pnpm db:migrate` | Passed, upgraded fresh DB to 0002_phase1 |
| `pnpm db:check` | Passed, no schema drift |
| `pnpm seed:fixture-ledger` | Real import completed: 42 processed, 26 canonical transactions, 0 failed |
| `uv run python apps/api/tests/money/export_examples.py` | Passed actual in-process HTTP calls against PostgreSQL; all example payloads Pydantic-validated |
| `uv run pytest apps/api/tests/money -m 'not integration' -q` | 81 money unit/HTTP tests passed; no database needed |
| `uv run pytest apps/api/tests/money/test_money_postgres.py -q` | Final implementation: 7 passed in 70.69 seconds |
| `pnpm check` | Final run passed Ruff/format, ESLint, 215 backend tests, 10 web client tests, Next type generation, strict TypeScript |
| `pnpm build` | Final run passed optimized Next production build |
| `pnpm test:integration` | 13 passed; 4 inherited ledger fixture setup errors from the old database-name allowlist (see below) |
| `pnpm eval:extraction` | Offline replay passed: 42 messages, 26 records, 6 duplicate merges, 3 refund/reversal links, 2 review items, 0 amount/direction/false-record errors |
| `pnpm eval:extraction --rules-only` | Passed the same truth table without provider calls |
| `git diff --check` | Passed |

The initial all-repository test collection found duplicate generic test basenames;
renaming the owned tests to `test_money_engine.py` and `test_money_postgres.py`
resolved it. Final check/build pass. No lint rules or tests were disabled.

Each PostgreSQL money scenario renders all 42 actual synthetic `.eml` messages into
a temporary mailbox, ingests them through A1, then queries APIs. Assertions verify
42 email sources, 36 source events, 26 transactions, three Amazon ₹799 source records,
three refund/reversal links, one paid commitment, two excluded review items, correction
history/locks, status preservation on fresh-provider-ID re-imports, wrong-user 404s,
literal/stable filters, separate/confirm/merge behavior, moved confidence factors,
refund/paid links, and rollback of flushed fields/revisions/audit records.

Confirmed truth: income 6200000, net outflows 3742000, upcoming 980000, estimated
unallocated 1478000, and 500000 proposal remaining 978000 paise. Food is 661000 before
and 786000 after Hotel Arya correction. These are tracked-record totals, not a
verified bank balance. Simulations retain the fixed disclaimer key; exact display
wording is in `docs/money.md` and the shared contract.

## Integration action for Agent 5

The inherited `apps/api/tests/ledger/test_persistence.py:33` safety allowlist accepts
only `finboy`, `finboy_a1`, and `finboy_test`. Therefore four original ledger tests
refuse `finboy_p1` during fixture setup, before doing any work. Please extend that
unowned test guard for the authorized `finboy_p1`–`finboy_p5` databases during final
integration, then rerun the whole integration suite. Agent 1 did not edit it or run
those tests against another agent's database. The new money fixture already checks
loopback/nonproduction plus an explicit FinBoy disposable-database allowlist so
final integration can run it; all Agent 1 executions used `finboy_p1` only.

New audit types: `transaction.corrected`, `transaction.confirmed`,
`transaction.rejected`, `transaction.merged`, `transaction.kept_separate`; subject
`transaction`; metadata only `{action, fields}` with fixed action and corrected
field names. A money-owned narrow insert keeps this in the write transaction;
the shared mail-only audit helper is unchanged. No shared model/audit constraints,
migrations, dependency/settings changes, or cross-owner source edits are required.
Only authorized money/ledger/routes/tests/docs/handoff paths changed.

## Real, mocked, and remaining limits

PostgreSQL, Alembic, rendered ingestion, and finance API calculations/writes were
real. HTTP verification used FastAPI/HTTPX/TestClient in-process with that database.
Unit HTTP/failure/CORS tests use controlled doubles. The extraction replay uses the
existing real recorded cassettes; this round made no new live provider calls.

No UI, speech, WhatsApp, provider account setup, or external messages were implemented
or tested by Agent 1. No browser screenshots: frontend source was unchanged; viewport,
keyboard, microphone, and complete product QA belong to Agents 2/3/5 after assembly.
Gmail reconnection/live consent remains with the integration flow as previously
noted. Synthetic-fixture accuracy does not establish real-mailbox coverage, and
simulations always include incomplete_coverage. No background server remains running
from this handoff. Main, other worktrees, and the uncommitted design were untouched.
