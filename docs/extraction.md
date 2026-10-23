# FinBoy Phase 1 extraction

A1 implements the Python interfaces in contract §6. There are no HTTP routes or frontend
changes. Worktree: `phase1/a1-ledger`; local database: `finboy_a1`; API port: 8001.
The branch is based on scaffold commit `2b8e3c1`.

## Model and official documentation

On 23 October 2026, the following official pages were read in **Chrome**, including the
Python example on the SDK page:

- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Python SDK usage](https://developers.openai.com/api/docs/libraries)
- [GPT-6 Luna model details](https://developers.openai.com/api/docs/models/gpt-6-luna)

The chosen model is **`gpt-6-luna`**, set in the ignored backend environment as
`OPENAI_EXTRACTION_MODEL`. The model page lists Structured Outputs support and prices
of $0.10 input / $0.50 output per million text tokens. This focused extraction workload
uses the lower-cost model with deterministic rules and human review as safeguards.
The installed scaffold lockfile supplies `openai==3.37.0`; A1 adds no dependencies.

The implementation calls `OpenAI(...).responses.parse(text_format=LLMResult)` and reads
`output_parsed`. Requests have no tools, `store=False`, `reasoning.effort=none`, a
3,000-token output cap, a 30-second per-attempt timeout, and the SDK's two retries with
backoff. A process-wide semaphore caps concurrent API requests at four. Temperature
is omitted; the integration does not assume support for it across reasoning models.
A refusal, incomplete output, or unavailable provider falls back to rules. Domain
validation can reject a schema-valid claim, such as an invalid account suffix.

## Pipeline and retained data

1. Parse RFC822 with stdlib `email.policy.default`. Prefer the plain part; otherwise
   turn HTML into text, ignoring scripts, styles, and quoted blockquotes. Discard
   attachments, quoted replies, service footers, and URL targets. Inputs are limited
   to 2 MiB raw and 12,000 normalized characters.
2. Remove email/VPA addresses, mask account/phone/card digits beyond the last four,
   and mask other long digit runs. Monetary values and dates remain usable. Long
   numeric references are converted to deterministic hash tokens before masking,
   retaining dedupe discrimination without retaining their raw digits.
3. Score sender domains and financial keywords; negative promo/OTP/newsletter/win/offer
   signals reject non-financial candidates. Sender domains are heuristics, not proof
   of sender authentication. The fixture's `.test` domains are explicitly recognized.
4. Extract alert, order, invoice, and bill templates with named regex groups and
   positive INR parsing through `Decimal`, then convert to integer paise. Dates are
   interpreted in IST. Invalid grouping, negative values, zero, fractional paise,
   non-finite values, and unsupported numeric forms are rejected.
5. For candidates, Structured Outputs returns event claims, evidence, informational
   field confidence (`field_confidence`), and `not_transaction`. The system prompt identifies the email
   as UNTRUSTED DATA, forbids following instructions, requires unknowns to be null,
   and distinguishes orders, settlement, failures, refunds, and commitments.
   Evidence must be an actual substring of the minimized input, at most 80 characters;
   an LLM amount must match its monetary evidence. Settlement proof needs explicit
   debit/credit/settlement wording. Rules win; the model fills evidenced gaps only.
6. Cache structured responses in PostgreSQL `extraction_cache`. The key is SHA-256 of
   normalized content hash + extractor version + configured model. No raw body,
   subject, recipient, or API key is stored. Source metadata uses hashes; source
   events retain bounded field evidence and extracted fields. Persisted extractor IDs
   include the deterministic field names, so later reconciliation cannot mistake an
   LLM-filled field for deterministic evidence.

No key or no model means rules-only processing. Existing complete rule claims can be
confirmed; uncertain parsed claims become `needs_review`. A financial candidate with
no usable positive amount/event claim is marked as a failed source, rather than
inventing a transaction with an amount or direction. This is a schema/UI limit:
source-only failures require import inspection, whereas ledger review operates on
parsed transaction claims.

Application services emit no email or ledger content to logs, including on failure.
The application JSON formatter also suppresses third-party payloads. Regression tests
cover exception redaction, formatter behavior, and structured-only cassette contents.

## Reconciliation and review

The shared pure matching module is used by both evaluation and persistence:

- Provider message identity is idempotent under the database unique constraint.
- Matching reference plus amount/currency identifies a duplicate; conflicting values
  create `possible_duplicate` review items.
- Otherwise match equal amount within ten minutes with matching last4 and instrument,
  then equal amount and normalized merchant within 48 hours. Multiple matches require
  review. Distinct known references are kept distinct.
- Refunds and reversals are separate incoming events linked to a unique original,
  including when the original arrives later. Links use reference first, then a unique
  merchant/amount match within 90 days. They are never merged into the original debit.
- Failed payments persist as `failed`. Card-bill payments are `transfer`. Neither
  contributes to confirmed spending. Bill and EMI notices create commitments; one
  confirmed matching payment within seven days of the due date marks one paid.
- The small alias map recognizes Amazon's legal name and Bundl → Swiggy. Category
  rules run before model category fallback. HOTEL ARYA deliberately starts as `travel`;
  its user correction to `food_dining` is tested and preserved on re-import.

`ingest_messages` streams batches of four, prepares extraction concurrently, then
reconciles serially with a user-scoped PostgreSQL advisory transaction lock. It owns
one commit per message; failures roll back only that message and counters advance
only after commit. Progress callbacks receive snapshots after committed work. The
caller owns import-run lifecycle/counter writeback. Cache writes have their own small
transactions. Existing provider messages do not update canonical records.

New source evidence respects `user_locked_fields`, rejected status, and status
confirmed by a user revision. Source evidence remains immutable when users correct
canonical fields. `merge_transactions` and `keep_separate` are tenant-scoped and
write `transaction_revisions`; **their caller commits**. Manual merge redirects sources,
refund links, and paid-commitment links. Keeping records separate prevents weak future
matching, while an exact reference/amount re-import can still attach to the same record.

## Confidence

Stored factors use these base weights:

| Evidence | Weight |
| --- | ---: |
| Recognized sender and matched rule template | 25% |
| Deterministic amount and date | 25% |
| Reference available and not conflicting | 20% |
| Agreement across sources | 15% |
| Merchant/category quality | 15% |

For a single source, agreement is recorded as `null` (unavailable) and the other
applicable weights are normalized over 0.85. Missing amount/date/reference/merchant
quality receives zero, not a free pass. Multiple consistent sources use the full
weight; a disagreement receives zero for agreement. This explicit availability
normalization lets fully evidenced single-source alerts clear the threshold without
pretending a second notification exists. It is an implementation choice to review
when calibrating on real mail.

A score of at least 0.90 is necessary for automatic confirmation. Missing payment
proof, unknown merchant, uncertain category, or ambiguous identity requires review
regardless of score. Model self-scores are stored for inspection and **never used in
this calculation**. `confidence_factors` exposes the contributions and source count
for “Why FinBoy added this”.

## Synthetic evaluation and real outcomes

`scenario.json` contains 42 fully synthetic messages: 26 canonical transaction claims
(including a failed payment and two review items), four obligations (one paid), six
duplicate notifications, and six locally rejected messages. Every message carries
`X-FinBoy-Synthetic: 1`; all accounts and references are fake. The renderer creates an
independent `expected_ledger.json`; extraction never reads fixture IDs or expected
values. Rendering at the same anchor is byte-deterministic. Other anchors shift
calendar dates and clamp end-of-month dates; new dates need newly recorded cassettes.

```sh
pnpm demo:render-mailbox --anchor 2026-10-28
pnpm eval:extraction             # offline, strict recorded replay; no network
pnpm eval:extraction --rules-only
pnpm eval:extraction --live      # explicitly calls OpenAI and replaces recordings
```

Offline evaluation uses the model in settings, or the cassette manifest when unset.
A missing cassette or model/version mismatch fails evaluation; recordings are never
synthesized from expected values. Normal imports use live extraction when configured;
`FINBOY_EXTRACTION_MODE=rules|offline` is available for diagnostic/test runs.

The actual `pnpm eval:extraction --live` run on **23 October 2026** passed. It submitted
36 minimized synthetic financial candidates and recorded 36 actual structured
responses; six non-financial messages were filtered locally. Offline replay and the
rules-only baseline also passed. The first exploratory run exposed domain-invalid
model output; the resulting validation fix rejects unsupported claims and retains
valid rule evidence. The following are end-to-end hybrid results, not a claim that
LLM extraction alone attains perfect accuracy.

| Metric | Expected | Live | Offline |
| --- | ---: | ---: | ---: |
| Canonical records | 26 | 26 | 26 |
| Tracked income | ₹62,000 | ₹62,000 | ₹62,000 |
| Confirmed outflows, net | ₹37,420 | ₹37,420 | ₹37,420 |
| Upcoming obligations | ₹9,800 | ₹9,800 | ₹9,800 |
| Duplicates merged | 6 | 6 | 6 |
| Refunds/reversals linked | 3 | 3 | 3 |
| Review items | 2 | 2 | 2 |
| False transactions | 0 | 0 | 0 |
| Amount / direction errors | 0 / 0 | 0 / 0 | 0 / 0 |

After the explicit Hotel Arya correction, category net totals are rent ₹15,000,
food/dining ₹7,860 (before: ₹6,610), groceries ₹3,280, transport ₹2,140, shopping ₹2,640,
investments ₹5,000, and subscriptions ₹1,500. Gross confirmed direction sums are
₹63,750 incoming (including refunds/reversal) and ₹43,670 outgoing (including transfer).
These differ deliberately from tracked income and net spending. Unallocated is
₹14,780; the ₹5,000 simulation leaves ₹9,780 under contract money rules.

## Verification and limits

Executed in the A1 worktree against local `finboy_a1`:

- `uv sync --locked --all-packages`, `pnpm install --frozen-lockfile`, `pnpm env:setup`:
  succeeded; the private env was configured for A1 ports/database.
- `pnpm db:up`, local `createdb ... finboy_a1`, `pnpm db:migrate`: succeeded; only the
  shared container was started, and no shared container/volume was stopped or deleted.
- `pnpm db:check`: passed with no new upgrade operations.
- `pnpm eval:extraction --live`, `pnpm eval:extraction`, rules-only eval: passed as above.
- `pnpm check`: passed backend/frontend lint, 84 Python unit tests, 10 web client
  tests, and strict TS checks.
- `pnpm test:integration`: all 9 passed (4 A1 persistence/review/cache tests and 5
  baseline database tests). A1 has 42 unit tests; all run without PostgreSQL.
- `pnpm build`: production Next.js build passed. No frontend was edited, so browser
  viewport QA is outside A1's changes. Official OpenAI docs were inspected in Chrome.

No cross-boundary source edits, new dependencies, or migrations. Only contract A1 paths
were changed; ignored worktree env files were configured as requested.

Remaining limits: this is a synthetic demonstration across a few known styles, not
validation against real bank mail. Domain heuristics do not authenticate senders;
IMAP/Gmail trust verification belongs to the provider boundary. Attachment/PDF/OCR
extraction, fuzzy alias discovery, partial refunds, split payments, multi-currency,
and automatic resolution of ambiguous repeated purchases are not implemented. Pure
LLM-only claims remain conservative under the confidence threshold. Link/payment
windows and confidence availability normalization need calibration on labeled real
messages. Reconciliation currently scans one user's ledger and favors clarity over
large-mailbox performance. Commitments do not have a dedicated revision table in the
shared contract. End-to-end Gmail/UI/voice integration remains with A2/A3/A4.
