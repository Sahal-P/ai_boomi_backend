# Deterministic money and review APIs

All money is integer paise, INR. Calculations use only user-scoped ledger records;
no LLM, fixture oracle, or demo totals participate at runtime. The unchanged
contract §6 models and six public money function signatures remain in
`apps/api/src/finboy/services/money/engine.py`. Pure calculations are separate from
small SQLAlchemy loaders.

## Calculation semantics

`today_ist()` is the only business clock. Months include midnight on the first day
through the last microsecond of the final day in Asia/Kolkata. Explicit months use
`period=month&year=2026&month=10`; the default is `period=current_month`.

Only `confirmed` transactions contribute. Income includes incoming salary and
other income. Net outflows include outgoing records except transfers, less incoming
refunds/reversals. Failed, merged, rejected, and review records never contribute.
Review amounts/counts are reported separately. Refunds use the linked original's
current category, including when that original is in an earlier month. Refund-only
months and net categories may be negative. No refund is silently clamped to zero.

Upcoming commitments have status `upcoming` and due dates from the later of today
and period start through period end, inclusive. Paid/dismissed and overdue records
are excluded. Income minus net outflows minus upcoming commitments is **Estimated
unallocated amount**. Display: “Based on email-derived and confirmed records. Your
actual bank balance may differ.”

Evidence IDs include every canonical record contributing to income/net outflows,
including refunds and reversals, ordered by timestamp then UUID. Category and
outflow counts count the contributing debit and refund/reversal records; they are
not counts of email notifications. Commitment views carry source/payment IDs.

Simulations subtract a positive proposal from the current month's unallocated
amount. Warning order is pending review, negative remaining, low buffer, incomplete
coverage. A remaining amount strictly below 10% of tracked income gives low buffer
when tracked income is positive; a negative amount can give both warnings. Every
simulation includes incomplete coverage because no bank/coverage verification exists.
The fixed disclaimer key resolves to exactly:

> This models cash flow from FinBoy's tracked records. It is not a recommendation to purchase any security.

## HTTP contracts

Every response, including finance validation/error responses, is `no-store` and uses
the shared safe error envelope/request ID. A database failure returns fixed 503
`database_unavailable`; other unexpected errors are redacted. Write origins, when
supplied, must match the explicit worktree CORS origins.

| Endpoint | Response / request |
| --- | --- |
| GET `/api/v1/money/summary` | `MoneySummary` |
| GET `/api/v1/money/commitments` | `CommitmentView[]` |
| POST `/api/v1/money/simulations` | `{monthly_amount_minor, label?}` → `CashFlowSimulation` |
| GET `/api/v1/transactions` | `TransactionView[]`, default limit 50, maximum 200 |
| GET `/api/v1/transactions/{id}` | `{transaction, sources, confidence_factors, revisions}` |
| PATCH `/api/v1/transactions/{id}` | One or more of `category`, `merchant`, `amount_minor` → detail |
| POST `/api/v1/transactions/{id}/confirm` | No body → detail |
| POST `/api/v1/transactions/{id}/reject` | No body → detail |
| POST `/api/v1/transactions/{merge_id}/merge` | `{keep_id}` → detail of the now-merged `merge_id` |
| POST `/api/v1/transactions/{id}/keep-separate` | No body → detail; explicit confirm still required |

List filters: period/year/month, closed category/status, `q` (literal, case-insensitive
merchant substring, 1–160 characters), limit. SQL escapes search wildcards and sorts
by timestamp descending then UUID ascending. Unknown filters/fields, invalid UUIDs,
incomplete periods, null/empty corrections, nonpositive/fractional/boolean amounts
are rejected with redacted 422 responses. Corrections are capped at 10^14 paise;
merchant 160 characters; simulation label 80 characters. Missing/wrong-user IDs give
404. Invalid transitions/self-merges/incompatible merges give 409. Terminal rejected,
failed, and merged records cannot be corrected; rejected records cannot be confirmed.

Details join actual email metadata/events, extracted claims/methods, bounded evidence
(up to 16 fields, 80 characters each), field confidence, stored deterministic
confidence factors, and revision history. Raw emails/subjects/provider message IDs
are not exposed. Source evidence stays immutable during canonical corrections.

## Review writes

The money review service owns commit/rollback and uses the same per-user advisory
transaction lock as A1 ingestion, followed by the existing ledger row locks.
Category/merchant/amount corrections and status decisions create user revisions and
`user_locked_fields`. Confirm/reject, merge, and keep-separate call ledger services;
merge redirects source evidence, refund links, and paid commitments. Keep-separate
locks dedupe without confirming uncertain financial claims. A rejected or amount-
corrected payment reopens its paid obligation when the payment no longer qualifies;
merchant/category edits retain the existing paid link. Dismissed commitments stay
dismissed. Every failed write rolls back changes, revisions, and audit metadata.

Audit inserts use fixed `transaction.corrected|confirmed|rejected|merged|kept_separate`
event types, subject `transaction`, and only fixed action plus corrected field names.
No amounts, merchant values, snippets, identifiers, or exception text enter audit
metadata/logs. No schema or shared audit constraint changes are required. These
events use a narrow money-owned insert; the mail-only audit helper remains unchanged.

## Development data and examples

Agent 1 runs on API 8011/web 3011 and local disposable `finboy_p1`, with demo date
2026-10-28. `pnpm seed:fixture-ledger` runs A2's import orchestration over the existing
rendered 42-message A1 mailbox in rules mode, with provider calls disabled. It is
idempotent and refuses production/nonlocal/other databases. It never inserts a
parallel fake ledger or reads `expected_ledger.json` as runtime input.

`docs/handoffs/agent-1-api-examples.json` contains Pydantic-validated synthetic actual
API responses before/after Hotel Arya correction, transaction arrays, three-source
detail, commitments, simulation, requests, and errors. To regenerate once on the
freshly seeded, uncorrected `finboy_p1` ledger:

```sh
pnpm seed:fixture-ledger
uv run python apps/api/tests/money/export_examples.py
```

The exporter intentionally refuses an already-corrected ledger rather than silently
rewriting a user's decision. Focused verification and remaining limits are recorded
in `docs/handoffs/agent-1.md`.

Implementation references: [FastAPI typed query models](https://fastapi.tiangolo.com/tutorial/query-param-models/)
and [SQLAlchemy 2.1 transaction framing](https://docs.sqlalchemy.org/en/21/orm/session_basics.html#framing-out-a-begin-commit-rollback-block).
