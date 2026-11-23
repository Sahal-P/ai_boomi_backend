# Advisor edits round — contract (23 November 2026)

**The problem.** In the web Ask, a household asked FinBoy to "categorise it all", then to "change
them and save it". Ask answered with suggestions, then "I can't change or save payment categories
from here." Its analysis was shallow too:
- `find_payments` listed at most 20 records, so 21 of 41 "Other" payments were never seen.
- "Where should I improve" called ₹44,500 of transfers spending. The engine leaves a payment out of
  spending only when its **kind** is `transfer`; category "transfer" alone still counts.

**What this round adds:**
- read-only analysis that sees every payment: `other_payees`, `spending_review` and paging in
  `find_payments`;
- proposals: Ask shows the exact changes, one tap applies them all and one Undo puts them back;
- remembered payee names, so the next entry from a renamed payee arrives under its new name;
- the same proposal card on the web and on WhatsApp.

**What it supersedes, and nothing else:**
- **"Ask reads the household's records through read-only tools"** (advisor round). Ask may now
  *propose* changes through `propose_changes`. The tool changes nothing itself; the household's tap
  does, through the services below.
- **"WhatsApp never confirms, edits or deletes records"** (capture round), only for the changes
  listed here and only after the household's tap. WhatsApp still never merges or deletes records.
- **"Records of your choices never contain amounts or names"** (privacy policy), only for change
  sets, which the policy now names.

**What still binds:**
- Amounts, dates and deleting stay on the Transactions page.
- Every figure in a reply is checked against FinBoy's own numbers.
- Logs carry outcomes and counts, never a payee, category, amount or name.
- Admins never see change sets.

## Human decisions (23 November 2026)

- **Approval:** show the changes, then apply on a tap. One tap applies everything; one Undo
  reverts everything.
- **Edits:** categories, own-account transfers, budgets and the savings goal, payee names.
- **Where:** web Ask and WhatsApp together.

## Reading everything (always offered)

| Tool | What code works out |
| --- | --- |
| `other_payees(period)` | Spending payees still in "Other", grouped as payee sorting groups them (`merchant_key`): payments, total, latest date and any remembered category, largest first, at most 50. Also unknown or hidden names (sorted one payment at a time) and payments categorised "transfer" that still count as spending. |
| `spending_review(period)` | One month: flexible spending by category against its average over the three months before (months with records only), fixed costs (rent, EMIs, utilities, subscriptions, phone, education, fees), saving, "Other" and its share, "transfer"-categorised spending, own-account moves (kind `transfer`, "not spending"), regular payments and money with people. |
| `find_payments` | Now `offset` and `remaining`, so a list pages 20 at a time. Each row has a short ref (`p1`, …) that this answer's context maps to its record ID; the model never sees record IDs. |

The prompt sends "where can I improve" to `spending_review`, points at flexible categories that grew,
and says that "transfer"-categorised spending still counts.

## Proposals: `propose_changes` (behind `ADVISOR_EDITS_ENABLED`)

The model calls it only when the household asks for a change. A question gets an offer in
`follow_ups` instead. At most 80 changes:

| Type | Input | Effect when applied |
| --- | --- | --- |
| `payee_category` | payee, category | Every spending record of the payee (confirmed or waiting) takes the category, except payments whose category the household set itself (kept). The payee's category is remembered. |
| `record_category` | ref, category | One record. A record marked as an own-account move counts again (kind `purchase`, or `salary`/`income_other` for money received). |
| `own_transfer` | payee or ref | Kind and category become `transfer`, so the records leave spending. A payee-wide change skips payments the household set to something else, and money received. |
| `rename_payee` | payee or ref, new name | The records' payee name (both directions). Payee-wide renames are remembered for the payee's next entries. |
| `budget` | category or `total`, monthly rupees or remove | `budgets.set_budget` |
| `savings_goal` | monthly rupees or remove | `budgets.set_goal` |

**Checked by code, before anything is shown:**
- payees must have records; unknown (`Unknown …`) and hidden (`[...]`) names may be several people,
  so they change one payment at a time, by ref;
- refs must come from `find_payments` in the same answer;
- categories are the closed list. Category `transfer` is refused for sorting: own-account moves use
  `own_transfer`. Money paid takes spending categories, money received takes income ones;
- new names are 1–60 printable characters and never "Unknown";
- budget and goal amounts must be ones the household said;
- two changes that disagree about one payment, payee, budget or the goal are refused. A change to
  one payment replaces a payee-wide change to it.

Problems go back to the model, which fixes them and calls again. A valid call returns the lines the
household will see, with figures that join the reply's checked numbers. The reply describes the
proposal and never says it is done. The answer's `change_set` carries its id, state, count, lines
(`groups`), kept and remembered counts.

**The plan is pure** (`changes.plan` over a `Ledger` read once), so the proposal shown and the
change applied follow the same rules.

## Change sets

Table `record_change_sets` (migration `0024_record_changes`):

| Field | Rule |
| --- | --- |
| `user_id`, `channel` | The household; `web` or `whatsapp`. |
| `message_id` | The advisor answer that offered it (`SET NULL` when the chat is cleared), so a reopened chat shows the card's state. |
| `state` | `proposed`, `applied`, `undone`, `declined` or `expired`. A proposal expires after 24 hours. |
| `changes` | The checked changes. |
| `summary` | The lines shown: the proposal, then what applying actually changed. |
| `before_state`, `after_state` | Each touched field before and after: record category, kind, payee name and locks; payee memory; budgets; the goal. |

**Apply** locks the household as review does, works the changes out again against the records as
they are now, and writes them through `correct_transaction(reason="advisor_change")` (revisions and
the household's locks), payee memory, `budgets.set_budget`/`set_goal` and `refresh_links`. A change
that no longer applies is skipped and counted. An expired, applied, dismissed or another household's
change set is refused.

**Undo** runs once. It puts back each field still at its applied value, with revisions
`change_undone`, and removes only the locks applying added to fields it put back. Anything changed
since stays, and is counted. Payee memory, budgets and the goal come back the same way.

**Erasure** deletes a household's change sets and their WhatsApp cards.

## Remembered payee names

- `merchant_categories.display_name` (nullable) is new, and `category` is now nullable. A row
  remembers a category, a name or both.
- `merchants.memory`, `remembered` and `remembered_name`: a renamed payee takes its new name's own
  category first, then the one remembered for the old name.
- Applied where categories already were: WhatsApp diary saves (`pilot._confirm`), statement imports
  (the new record only; matching keeps the statement's own name) and quick add's preview.

## Web

- `POST /api/v1/assistant/changes/{id}/apply`, `/undo` and `/dismiss`: household-scoped,
  origin-checked, `Cache-Control: no-store`, the usual error envelope (`changes_expired`,
  `changes_closed`, `changes_unavailable`, `not_found`). Apply needs `ADVISOR_EDITS_ENABLED`; Undo
  and Not now always work.
- A thread's messages carry their `change_set`.
- `ChangesCard` under the answer: the lines, "Apply N changes" and "Not now", then "Changes made"
  with Undo, and the undone, declined and expired states. It stacks at phone width, announces each
  result, and reloads Home, Transactions and Reports.

## WhatsApp

- After an answer with a proposal, a card: "✏️ FinBoy can make these changes:", the lines that fit
  1,024 characters, "+N more on the FinBoy website." for the rest, the kept count and "Nothing changes
  until you tap Apply." Buttons "✅ Apply N" and "❌ Not now" (purpose `advisor_changes`, one day).
- After Apply: "✅ Done: N changes made." with "FinBoy will remember these payees." when it does, and
  "↩️ Undo" (purpose `advisor_undo`, one day). The spoken twin says only the count.
- Refusals reuse receipt outcomes: `prompt_expired`, `prompt_answered`, `disabled`,
  `record_changed`.
- Copy in English, Hindi and Malayalam (`CHANGE_*`, `CHANGES_*`, `APPLY`, `NOT_NOW`).

## Flag and release

`ADVISOR_EDITS_ENABLED` (default false) offers `propose_changes` and allows Apply. The read tools
ship with the round. See [production](../production.md), "Advisor edits release".

## Checks

- **API unit:** plans (payee-wide and single changes, locks, own transfers, renames, budgets, the
  goal, conflicts), lines in three languages, the tool's checks and refs, paging, `other_payees`,
  `spending_review`, the flag, proposals saved with their answer (no payee names in logs), routes,
  and the WhatsApp card (1,024 characters, button titles, Apply, Not now, Undo, flag off).
- **Integration (PostgreSQL):** apply and undo, partial undo, refusals and expiry, skipped changes,
  remembered names and categories, erasure, and the WhatsApp tap flow with the recording Meta client.
- **Eval:** `pnpm eval:advisor` gains eight cases: sorting "Other" (English and Hindi), where to
  improve (reads own transfers, proposes nothing), what is in Other (proposes nothing), own
  transfers, renaming an Unknown payment, a food budget and a savings goal.
