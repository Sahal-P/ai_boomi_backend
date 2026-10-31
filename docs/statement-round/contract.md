# Statement round — contract (31 October 2026)

Households can bring in months of payments at once from a **Google Pay transaction statement**
(PDF), on the web or by sending the PDF to FinBoy on WhatsApp. FinBoy keeps every detail the
statement prints, checks every row against Google's own totals, adds nothing twice, and turns the
history into four new report sections.

It supersedes earlier statements only where it says so:
- "PDFs can't be read" on the email upload card: one kind of PDF, a Google Pay statement, now is;
- WhatsApp ignoring `document` messages: a PDF document is read as a statement while statement
  import is on;
- periods being a single month ([UX API contract](../ux-round/api-contract.md)): money queries
  also take a range of months.

Everything else still binds, including "WhatsApp never merges or deletes records" and every
no-storage rule.

## Human decisions (31 October 2026)

- **What:** import transactions from a Google Pay statement; store every detail, missing and
  losing nothing; give useful reports.
- **Where:** on the web (Sources) **and** by sending the PDF on WhatsApp.
- **Reports:** all four new sections — Who you pay most, Regular payments, Money with people,
  Small payments.
- **Where it lives:**
  - branch `feat/finboy-statement-import` from `feat/finboy-ui-refresh` `00904f2` (Reports is not
    on main yet);
  - loopback API 8061 and web 3061, disposable database `finboy_signup`;
  - one additive migration, `0012_statement_imports`; one dependency, `pypdfium2`.
- **Release:** `STATEMENT_IMPORT_ENABLED` defaults to false. Production is unchanged until the
  human enables it and approves the release.

## What a statement holds

Designed against the human's own six-month statement (several hundred rows over dozens of
pages), read in memory only. None of its names, figures or IDs is copied into the repository,
tests, docs or logs.

- **Header (page 1):** phone number, email address, the period, and Google's totals **Sent** and
  **Received**. The footer says self transfers are left out of those totals.
- **Each row:** date and time to the minute (IST); "Paid to" or "Received from" and the name as
  Google Pay shows it; "UPI Transaction ID"; "Paid by" or "Paid to" with the bank and the
  account's last four digits; the amount to the paisa in Indian grouping (₹1,23,456.78).
- **Every page:** a "Note: This statement reflects payments made by you on the Google Pay app…"
  footer and "Page n of N".
- **Quirks:** amounts wrap onto two lines (`₹12,50` / `0`), long names wrap, one payee
  is often paid several times minutes apart, each with its own UPI ID, and a person can be printed
  with spaces when paid and without them when received from.
- **Not in a statement:** the payee's UPI handle, notes, categories, and payments made in other
  apps.

## What gets stored

| From the statement | Kept in |
| --- | --- |
| Date and time (IST) | `transactions.occurred_at`, `source_events.occurred_at` |
| Paid to / Received from | `direction`, `kind` (`purchase`, `income_other`; a self transfer is `transfer`), `event_type` |
| Name as printed | `source_events.merchant_raw` (exact); `transactions.merchant` (spacing tidied) |
| The printed details line | `source_events.evidence["detail"]` (80 characters) |
| UPI transaction ID | `reference_id` on the record and its evidence |
| Bank and last four digits | `evidence["bank"]`, `account_last4`; `payment_instrument = "UPI"` |
| Amount to the paisa | `amount_minor` |
| Where the row came from | one `email_sources` row per statement row (`source = "gpay_statement"`, key `gpay:<UPI ID>:<direction>:<paise>`, with a `:n` suffix for an exact repeat) → its `import_runs` row (`mode = "gpay_statement"`) → `statement_imports`; page and row number in the evidence |
| Period, Google's Sent and Received, what FinBoy read, pages, row counts, masked accounts, the file's SHA-256, whether it is for the household's WhatsApp number, removal time | `statement_imports` (one row per import) |
| Phone number and email address | **never stored.** The phone is compared, as WhatsApp's keyed digest of `91` + its ten digits, with the household's WhatsApp binding; only yes/no/unknown is kept |
| The PDF | **never stored.** Read in memory, like `.eml` uploads and WhatsApp media |

## Reading a statement (`services/statements/gpay.py`)

- **Engine:** PDFium through `pypdfium2`, with each character's position. Rows are rebuilt from the
  table's three columns using the header's x-positions; lines group by their vertical middle. So
  wrapped amounts and names join, and the footer is never read as a row.
  - pypdf was rejected: it read every amount but joined 29 names and 12 account labels without
    their space, which would split one payee into two.
  - On the human's statement PDFium matched macOS PDFKit on every row, with no differences.
- **Isolation:** a separate `python -I -m finboy.services.statements.gpay` process with an empty
  environment, a 30-second limit and CPU (and, on Linux, memory) limits. It returns JSON on
  stdout; PDF and library errors never cross back, only fixed codes.
- **Limits:** 10 MB, 600 pages, 5,000 rows.
- **Recognised only with:** the "Transaction statement" title, a period line, Sent and Received
  totals, the table's column headers and the Google Pay footer on every page, with "Page n of N"
  numbered 1 to N in order. Anything else is `not_gpay_statement`; a password-protected file is
  `statement_locked`.
- **Strict check:** every row must parse, and every row's date must fall inside the period.
  - The paid rows must add up to Google's Sent and the received rows to Received, **to the paisa**.
  - Otherwise nothing is saved, and the import shows what FinBoy found next to Google's totals.
  - A row that is neither "Paid to" nor "Received from" (a self transfer, from the footer's note)
    is outside both totals, as Google prints them; it is saved as a transfer waiting in To review
    and never counts as spending or income.

## Saving rows (`services/statements/persist.py`)

One database transaction under the household's ledger lock. The household's records and their
evidence load once; rows are matched in memory and inserted in order (sources, records,
evidence), and links refresh once. 2,000 rows save in well under 10 seconds.

- **Identity:** a row's source key makes a second upload of the same statement, or an overlapping
  one, skip rows already imported ("already imported from an earlier statement").
- **Already in FinBoy:** a record from a screenshot, SMS, email or an earlier statement with the
  same UPI transaction ID (or, without one, the same instrument or payee, amount and time, as
  `choose_match` already decides) gains the row as evidence instead of a second record. A record
  takes at most one row of a statement; a second candidate waits in review.
- **Said or typed first:** a diary record (WhatsApp voice or text, quick add) with the same
  direction and amount within 36 hours is never joined. The statement row is saved as a
  `possible_duplicate` of it, waiting in To review, where the existing merge decides.
- **Counts at once:** a statement row is proof of payment, so its record is `confirmed`. An
  unsorted category does not send it to review (`confidence_for(..., statement=True)`), and later
  confidence refreshes keep trusting it.
- **Categories:** the household's own choice for the payee (merchant memory) first, then the rules
  in `services/ledger/categories.py`, widened this round (recharges, broadband and electricity,
  app stores and streaming, railways and travel, fuel, supermarkets, pharmacies and hospitals,
  food and cafés). Anything else is "Other", for Sort payees.
- **Removing an import** (web only): `delete_imported_data` gains an import-run scope. Records only
  this statement supports are removed, with their corrections; records with other evidence stay
  and lose only this statement's evidence. `removed_at` is set and the same file can be imported
  again. The shared extraction cache is left alone.

## API (additive)

All under `/api/v1`, with the existing session and exact-Origin rules.

- **`POST /imports/gpay`** — multipart, one field `file` (a `.pdf`, `application/pdf` or
  `application/octet-stream`). The file is read and checked before anything is saved; a statement
  that adds up returns 202 `{import_run_id}` and saves in the background, one that doesn't returns
  202 for an already-failed run that shows both totals.

  | Code | Status | When |
  | --- | --- | --- |
  | `statement_import_off` | 404 | `STATEMENT_IMPORT_ENABLED` is false (checked before the body is read) |
  | `invalid_statement` | 400 | not one PDF in `file` |
  | `upload_limit` | 413 | over 10 MB, 600 pages or 5,000 rows |
  | `not_gpay_statement` | 422 | not a Google Pay transaction statement |
  | `statement_locked` | 422 | password-protected |
  | `statement_unreadable` | 422 | a row, page or total couldn't be read exactly |
  | `statement_already_imported` | 409 | this exact file is already imported and not removed |
  | `import_busy` | 409 | another import of the household is running |

- **`GET /imports/{id}`** and the import list gain `statement` (null for other imports):
  `provider, period_start, period_end, pages, rows, new, linked, possible_duplicates,
  already_imported, not_counted, sent_minor, received_minor` (Google's), `paid_minor, got_minor`
  (what FinBoy read), `reconciled, accounts` (masked, "Bank ••1234"), `holder_matches`
  (true/false/null) and `removed_at`.
- **`GET /imports/{id}/removal-preview`** → `{records_removed, records_kept, data_version}`.
  **`POST /imports/{id}/remove`** `{expected_version}` → the import. A changed version is 409
  `version_conflict`; a running, failed or already removed import is 409 `invalid_decision`.
- **Ranges:** money and record queries accept `period=range&start=YYYY-MM-DD&end=YYYY-MM-DD`, at
  most 731 days. Budgets answer for the range's last month.
- **`GET /money/insights`** (any period) → the four report sections below, from confirmed
  household records only, with `data_version`.
- **`GET /money/payees`** (any period) → spending payees still under "Other", largest first (50 at
  most), with the period's spending and unsorted totals.
  **`POST /money/payees/category`** `{name, category, expected_version}` → `{updated,
  data_version}`: every spending record of that payee whose category the household hasn't set
  takes the category and locks it, with a revision (`payee_category`); merchant memory learns it,
  so the next WhatsApp entry, quick add or statement follows.
- **Session:** `statement_import: boolean` tells the web app whether to offer the card.
- **Literals:** `gpay_statement` joins the source modes and import modes; WhatsApp receipts gain
  kind `document` and errors `invalid_document` and `document_unavailable`.

## Reports

Reports' period control adds Last 3, 6 and 12 months; an imported statement's months
(`?from=2026-04&to=2026-09`) keep their own option. The figures, donut, month by month and
category links follow the range; budgets show its last month. The new sections appear only when
they have something to show:

1. **Who you pay most** — the top eight payees by amount (share of spending, number of payments),
   then "Who pays you" (top five) and the five biggest payments. A name opens exactly its records
   in the period.
2. **Regular payments** — payees paid a steady amount (within ±10% of the usual) in at least three
   of the six months ending with the period, at most twice a month at that amount (so a daily tea
   stall isn't a bill), and still being paid: one whose next payment is more than ten days late
   by the household's last record in the window has stopped and is left out. Lateness is judged
   against records, not today, so months not yet imported don't make every bill look stopped.
   Each shows its usual amount, months, and when it's next expected; the total a month is on top.
3. **Money with people** — everyone the household both paid and received money from in the period:
   sent, got back, and the difference ("You sent ₹79 more").
4. **Small payments** — payments under ₹200: the amount a month, their share of payments against
   their share of money, and the three places they happen most.

**Sort payees** is offered when more than 20% of spending is "Other": a sheet lists the payees
largest first, and one category per payee sorts its past payments and teaches future ones; a
meter shows how much of the period's spending is sorted.

Payees group by their case-folded name **without spaces** and show their most common spelling:
Google Pay prints some people as "Name K M" when paid and "NameKM" when received from (on the
human's statement this found a quarter more people both ways). For the same reason the records
search (`q`) ignores spaces, so a name's link opens both spellings. Transfers are left out, as in
the month summary.

## WhatsApp

- While `STATEMENT_IMPORT_ENABLED` is on, a `document` message of type `application/pdf` (10 MB at
  most) is downloaded through the bounded Meta media path and goes through the same reader and
  importer as the web, under an import run. While it is off, documents are ignored as before.
- Diary households agree to FinBoy's terms first (the existing consent card). No AI is used.
- **Replies** follow the reply-language rules (English, Hindi, Malayalam):
  - saved: rows and period; paid and received, both matching Google Pay; new, already in FinBoy
    and to check; the regular payments a month; small payments a month;
  - web households also get a link to Reports for the statement's months; pilot households, who
    use WhatsApp only, get the facts without a link;
  - every other outcome is one plain line: already imported, not a Google Pay statement,
    password-protected, couldn't read every row (including one that doesn't add up), couldn't
    open the file, another import running, unavailable.
- WhatsApp never removes an import, merges or deletes records. Removal is on the web, or by the
  operator for pilot households.

## Privacy and safety

- The PDF, the phone number and the email address on it are never stored or logged.
- Logs carry counts, fixed codes and IDs only — never names, amounts, UPI IDs or account digits.
- Household erasure and the full privacy delete also remove `statement_imports`.
- The human's statement is never committed or used as a fixture; tests build synthetic statements
  (invented names, banks and UPI IDs) in code.

## Release

1. Merge, deploy the API and run migration `0012_statement_imports` (additive; downgrade refuses
   while statement imports exist).
2. Run `pnpm eval:gpay <path to a statement>` on the server's build with a real statement kept
   outside the repository. It prints aggregates only (pages, rows by direction, whether both totals
   match, names split by a space within one direction, seconds) and exits non-zero unless the rows
   add up, no name is split and reading takes under 30 seconds. It passed on the human's
   statement: every row read, both totals matching, no split names, under half a second.
3. Set `STATEMENT_IMPORT_ENABLED=true` and restart the API, only with the human's approval. The
   web card, the WhatsApp document path and the empty-state links appear with it.

## Not in this round

PhonePe, Paytm and bank statements (the reader is one module per app, so they can be added);
turning regular payments into bill reminders; Ask answering payee questions beyond what it does
today; committing, pushing, merging or deploying unless the human asks.

## Verification

Recorded in the round's final report:
- `pnpm eval:gpay` on the human's statement (aggregates only);
- API unit tests (synthetic PDFs: wrapped amounts and names, several pages, missing or misnumbered
  pages, totals that don't add up, self transfers, not Google Pay, password-protected, too large,
  garbage bytes; insights; uploads; WhatsApp documents and replies);
- integration on the disposable database (confirmed rows with evidence, re-imports and overlaps,
  UPI-ID links, a spoken payment becoming a possible duplicate, removal keeping shared records,
  Sort payees teaching merchant memory, household isolation, 2,000 rows within budget);
- web unit tests and browser journeys at desktop, 390 px and 320 px against the test double;
- `pnpm check`, `pnpm build`, `pnpm db:check`, `pnpm test:integration`;
- a live pass on API 8061 and web 3061 with the human's statement at desktop and 375 px.
