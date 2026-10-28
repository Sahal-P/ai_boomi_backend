# FinBoy architecture

FinBoy is one FastAPI service for private households in `apps/api`, one Next.js App Router
application in `apps/web`, and PostgreSQL. HTTP routes validate contracts; synchronous
services own blocking work and write transactions; `db` owns SQLAlchemy metadata and
sessions; `core` owns settings, access, errors, clocks and redacted logging. There is
no startup `create_all`, queue service, payment execution or external analytics.
Self-serve sign-up exists behind `SIGNUP_ENABLED`, off by default.

The deployed boundary is Vercel's same-origin `/api/v1` rewrite to the loopback
voxpay API behind HTTPS nginx. Host-only session cookies, exact-Origin write checks,
independent single-use Gmail state/PKCE and the cross-host handoff remain in place.
Only health, the fixed read-only demo, sign-in (password, WhatsApp code and Google)
and the existing signed/capability-validated provider exceptions are public. Provider
credentials remain exclusively backend-side. See [production](production.md).

## Households and sign-in

Every household route takes `CurrentUser` (`api/deps.py`), which resolves the household
from the session cookie: the owner's twelve-hour password session (`finboy:household:v1`)
or a WhatsApp/Google session (`finboy:user:v2:<household>:<epoch>`, `SESSION_DAYS`). It
refuses deleted households and stale epochs, and answers pilot households
`web_not_available`. Services take the household as a parameter, so another household's
IDs look missing (404). Outside production a request without a session is the owner.
`services/accounts` owns households (capacity under an advisory lock, consent, erasure),
WhatsApp login codes (HMAC only, bound to a browser nonce), Google ID-token checks, daily
usage counters and the counts-only CLI. Quick add (`/api/v1/entries`) reuses the WhatsApp
statement reader and turns one sentence into a `manual_entry` import line plus the
ordinary versioned confirm decision. See the [sign-up contract](signup-round/contract.md).

## Sources, ledger and scope

Gmail scans and memory-only `.eml` uploads normalize messages, classify them, extract
bounded evidence and reconcile canonical transactions and obligations. One message
commits atomically. Successful sources deduplicate by stable provider/content identity;
failed sources retain a safe reason and attempt count and can be retried. Gmail retries
re-fetch selected source IDs; uploads require the original files. Bodies are never
stored. Extraction cache keys distinguish sample and household provenance.

All finance queries and reconciliation partition by `dataset`. `/api/v1/demo` builds a
fixed synthetic snapshot in memory without opening a household session. Its UI never
imports samples. The legacy demo mutation returns `demo_read_only`. Additive migration
0004 marks existing demo-only records as demo and mixed canonical values as quarantined,
preserving source events, canonical values, locks and revisions. Quarantined values
cannot enter ordinary finance, search, assistant, matching or review writes. The explicit
quarantined history view and isolation inventory retain inspectability. Mixed data needs
source-aware operator review; a dataset label is not proof of clean canonical values.

Confirmed, household, non-transfer transactions feed integer-paise INR calculations.
Refunds/reversals offset outflows; corrected original categories propagate to refunds.
Unpaid obligations due by the selected period end remain deductions across due-day and
month rollover. Future/today and overdue amounts are separate; uncertain obligations are
conservatively deducted and inspectable. Paid and dismissed states differ. Historical
summaries describe current unresolved liabilities, not reconstructed bank balances.

## Recovery and concurrency

A PostgreSQL trigger maintains a household generation across finance, source, revision,
connection and import mutations. Tokens also contain the IST calculation day. Clients
treat tokens as opaque. Versioned decisions and previews use the ingestion user lock
and the generation row. Previews run in a rolled-back savepoint. Confirm may atomically
save corrections; reject/reopen/merge/keep-separate/correct all preserve provenance.
Decision snapshots contain changed structured entities and source links, never bodies.
Undo appends revisions and succeeds only against the decision's unchanged snapshot.
Later sources, links, user locks or edits cause a safe conflict instead of being lost.
Original event-to-transaction lineage survives source movement, so later privacy removal
can remove derived merge stubs and financial decision snapshots exactly.

The additive counted transaction page supports all unresolved records independently
of month, filters, stable ordering, continuation and version checks. The old transaction
array remains available. Merge candidates are independent of the currently displayed
queue and include compatible confirmed targets. Evidence carries stable exact IDs;
field extraction completeness is separate from payment verification.

Imports run in the existing process using durable PostgreSQL counters. Run outcomes
separate complete, partial, failed, interrupted and cancelled processing. The worker
checks cancellation/scan permission before persistence checkpoints. Enabling scans never
starts or resumes a job. The worker's PostgreSQL session lock distinguishes an active
provider call from an abandoned run. A stopped upload cannot resume from a stored body.
Gmail caps are explicit; encrypted continuation tokens preserve the original query window.
There is no scheduler. Coverage is a query window, last successful scan, failures,
review/quarantine counts and truncation, never a claim of complete mailbox/bank coverage.

## Assistant, voice and privacy

Closed bookkeeping intents select deterministic engine operations. Full-scope merchant
arithmetic separates gross outflows, refunds/reversals and net spending before evidence
is capped. Contributing income/spending evidence is selected before the ten-row display
limit. Supported relative periods resolve against IST; unsupported periods get a specific
period clarification. Results include snapshot, resolved period, localized fact/warning
labels and separate display-script/speech metadata. LLMs never calculate ledger totals
or choose SQL/tools. Resemble Ultra English/Hindi, Gemini Malayalam and OpenAI
transcription remain backend-only, with independent speech failure and text fallback.

Explicit authenticated export downloads structured records/corrections, excluding raw
bodies, evidence snippets, credentials and account/reference/payment identifiers.
Deletion previews report removed and retained shared-source counts, dates and seven-day
backup retention. Previewed deletion rejects stale versions. Remaining evidence is
revalidated; unsupported retained canonical values are quarantined, and removal of the
last payment proof reopens review while retaining values and locks. Private decision
snapshots derived from deleted evidence are removed; operational audit is preserved. Operational task
outcomes use fixed allowlisted events and IDs in the existing audit table, with no
question text, merchant, amount, mail content, credential URL or external analytics.

## Frontend and verification ownership

Presentational components consume runtime-validated domain clients under `src/lib/api`
and small state hooks. The Product owner owns all frontend files during the UX round;
the Backend owner takes integration ownership only after its explicit handoff.
[UX API contract](ux-round/api-contract.md) freezes the additive schemas and examples;
[implementation map](ux-round/implementation-map.md) distinguishes implementation from
assembled browser and human acceptance. Unit tests require no PostgreSQL; schema and
high-risk journeys use only a loopback, non-production disposable database. Real consent,
phone playback, microphone permission and observed comprehension are separate evidence.
