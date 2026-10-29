# Village pilot round — WhatsApp voice-first Hindi pilot

The human approved this round on 26 October 2026 (IST) from main `b2110a9`. It supersedes
the conflicting statements in `AGENTS.md`, `docs/capture-round/contract.md` and
`docs/whatsapp.md` only as written here. Every other privacy, money, ingestion, production and
access rule stays binding. Plan: `docs/pilot/plan.md`.

## Human decisions

- **Language and region:** Hindi, one North India village.
- **Approved:** WhatsApp may confirm, correct the amount of, and reject a pilot household's own
  records by explicit button tap, with undo. Up to 10 pilot households, each enrolled by hand.
  Opt-in reminders that FinBoy sends first.
- **Not approved:** erasing data from WhatsApp. Erasure is operator-run on request.
- **Number:** the existing Meta test number. Meta allows at most 5 registered recipients and the
  owner's number is one, so the pilot is 4 village households plus the owner. More households need
  a real business number, verification and billing: a separate human decision.

## Lifted and retained non-goals

Lifted for pilot households only: WhatsApp record decisions by button (confirm, reject, correct
amount, undo), voice-reported money and dues, user-created dues, opt-in reminders and summaries,
enrolled households other than `LOCAL_USER_ID`.

Still prohibited: automatic confirmation of anything; merging or deleting records from WhatsApp;
storing messages, audio, images, transcripts or questions; public signup; broadcasts or any send
without opt-in; investment picks; web access for pilot households. The owner's household, web
app and existing WhatsApp question flow behave exactly as before unless the owner's `users.pilot`
flag is switched on for the dogfood week.

## Households and access

- A pilot household is a `users` row with `pilot = true`, created by
  `uv run --package finboy-api python -m finboy.services.pilot.cli enroll`. Display names are
  "Pilot household N"; no personal names.
- The private `WHATSAPP_SENDER_ALLOWLIST_JSON` maps each phone number to its household UUID. A
  household must exist and be `LOCAL_USER_ID` or `pilot = true`, otherwise its messages are
  ignored. At most 10 pilot households. Phone numbers stay only in that private env value.
- Web, Gmail, upload, review, privacy and assistant HTTP routes stay `LOCAL_USER_ID`-only.

## Consent

Until a pilot binding has `consented_at`, every message except STOP/बंद gets the consent card
(text, voice readback, [✅ हाँ, मंज़ूर] [❌ नहीं] in Hindi) and nothing is recorded or answered.
Since 29 October 2026 the card is in English unless the message shows Hindi or Malayalam, and
`hindi` chooses Hindi (the human's choice,
[Reply language](../whatsapp.md#reply-language-29-october-2026)). The
card says what is kept, that voice, photos and messages are not kept, that only this number sees
the records, how to stop, and that the helper or operator deletes everything on request. Tapping
"नहीं" keeps nothing and leaves the gate closed. STOP/बंद and START/शुरू work as before.

## Conversation

- **Buttons:** reply buttons only, at most 3, titles of 20 characters or fewer. IDs are
  `fb1:<prompt hex>:<choice>` and are accepted only from the binding that received them, while the
  prompt is open and unexpired.
- **Confirm card** (after a voice entry or a screenshot): amount, counterparty when known, date,
  money in/out, category, "सही है?" with [✅ हाँ] [✏️ बदलें] [❌ नहीं], plus a Hindi voice readback
  when speech is available. Cards expire after 7 days. A tap is refused if the record changed
  since the card was sent (fingerprint check).
- **हाँ / नहीं** call `services/ux/decisions.decide` with `confirm` / `reject` and the household's
  current `data_version`; the reply offers [↩️ वापस लें], which calls `undo_decision` under its
  existing strict version rules, then re-offers the card.
- **बदलें** opens a 10-minute amount prompt. The next text or voice message is read only as an
  amount (`ingestion/hindi_numbers.py`), applied as a `correct` decision, and the card is sent
  again. An unreadable amount asks again; nothing is guessed.
- **Voice or text statements:** a structured, untrusted, tool-less OpenAI parse (`store=False`)
  returns spent, received, due, question or unclear, with the amount phrase, counterparty and due
  label as literal substrings of the transcript, a closed-list category, cash/UPI mode and a day
  phrase. The amount must be grounded deterministically or FinBoy asks "कितने रुपये?". Spent and
  received become one notification line through the existing import pipeline with source
  `whatsapp_voice`, always landing in review. Questions use the existing assistant. Unclear
  messages get a short example of how to say it; nothing is kept to retry later.
- **Dues:** a due needs a day of the month ("10 तारीख"), otherwise FinBoy asks for it. It becomes
  a `commitments` row with kind `loan` and status `pending` (never counted) until हाँ makes it
  `upcoming`; नहीं makes it `dismissed`; both can be undone, and बदलें changes a pending amount.
- **Paid:** a reminder's [✅ भर दिया] records the instalment as one `whatsapp_voice` line paid to the
  due's label (category `loan_emi`), confirms it through `decide`, and links it with
  `obligations.correct_obligation`, so money left falls only by what was paid. An already-paid due
  is not paid again; a busy import records nothing and the button stays usable. [⏰ अभी नहीं]
  also keeps the button usable. "अगले महीने भी यही देना है?" [✅ हाँ, अगले महीने] saves next
  month's due as `upcoming` (same day, clamped to the month's length) with undo. There is no
  recurrence engine.
- **Reminders:** only for bindings with `reminders_opt_in_at`, asked once after a household's
  first due. A due gets at most one `two_days` reminder (due within the next two days) and one
  `due_day` reminder (due today or overdue). With `WHATSAPP_REMINDER_TEMPLATE` set, the `remind`
  job sends the approved Hindi utility template 08:00–20:00 IST with [✅ भर दिया] [⏰ अभी नहीं],
  under the same consent lock as replies. Without a template, the nearest unreminded due (from
  two days ahead to seven days overdue) follows the household's next reply as its own card
  (delivery kind `reminder`) with the same buttons, inside the 24-hour window.
- **हिसाब / hisaab** (typed or spoken; also "हिसाब बताओ", "hisaab batao"): this week (Monday to
  today) from `money_summary`: money in, money out, the top 3 outflow categories, dues in the next
  7 days, overdue dues and the number of records still waiting for हाँ, in text and voice. It
  works even while an amount question is open.

## Data kept and never kept

Kept: the ledger records the household confirms (amount, date, direction, counterparty,
category), dues, decisions and revisions, prompt metadata (purpose, record IDs, a keyed
fingerprint, state, expiry), consent and opt-in timestamps, and delivery/receipt metadata. Never
kept: message text, transcripts, audio, images, captions, questions or answers.

## Schema (migration `0008_village_pilot`, additive)

- `users.pilot boolean not null default false`.
- `whatsapp_bindings.consented_at`, `whatsapp_bindings.reminders_opt_in_at` (nullable timestamps).
- New `whatsapp_prompts`: id, binding, household, purpose, transaction/commitment/decision IDs,
  keyed fingerprint, state, created/expires/answered timestamps. No text columns.
- New `whatsapp_reminders`: due, kind (`two_days`, `due_day`), state, outbound message ID,
  provider status, timestamps; unique (due, kind).
- Widened CHECKs: receipt kind `button`; delivery kinds `interactive` and `reminder`; receipt
  error codes `prompt_expired`, `record_changed`, `amount_unclear`, `statement_unavailable`;
  source and import mode `whatsapp_voice`; commitment kind `loan` and status `pending`;
  categories `farming`, `livestock`, `phone_recharge`, `family_events`, `remittance`, `wages`,
  `farm_sales`, `govt_benefit`. Voice lines keep the existing source classifications; no new
  classification is needed. The category list is a draft to confirm in the week-0 interviews.
- `pending` dues are excluded from every total, list and obligation route; the engine accepts
  kind `loan`.

## Operator tools (`finboy.services.pilot.cli`)

`enroll` (create the next "Pilot household N" and print its ID), `owner on|off` (the owner's
dogfood week), `erase <household> --confirm` (delete one pilot household's records, sources,
dues, decisions, prompts, reminders, receipts, deliveries and binding, and clear the shared,
regenerable extraction cache as privacy deletion does; keep the numbered user row with
`pilot = false` and the audit counts; refuses `LOCAL_USER_ID`; runs under that household's
import lock), `report [--weeks 1-12]` (one JSON line per household and
week) and `remind` (the template job, run by `deploy/finboy-pilot-remind.timer`). Output never
includes amounts, names, labels, numbers or message content.

## Metrics allowlist

Per household ("Pilot household N" or "owner") and IST week from Monday, exactly what
`pilot.cli report` prints: active days; messages by kind (audio, text, image, button, command);
captures by channel (voice or text, screenshot); confirm, correct, reject and undo counts; dues
spoken, paid, paid by the due date and reminded; receipt failure codes (speech, statement,
amount, assistant, provider, capture, image, expired prompt, changed record); consented and
reminders opted in by the week's end; stopped now. Amounts, categories, labels, names and text
are never reported. Template provider statuses stay in `whatsapp_reminders` for inspection.

## Reminder template (human step)

Create on the existing WhatsApp Business Account, then set `WHATSAPP_REMINDER_TEMPLATE` to its
name only after Meta approves it:

- Name `finboy_due_reminder`, category Utility, language Hindi (`hi`).
- Body: `📌 याद दिलाना: {{1}} — {{2}} — {{3}} को देना है। भर दिया हो तो ✅ दबाइए।`
  with samples `समूह की किस्त`, `₹1,200`, `10 नवंबर` (FinBoy sends the due label, the amount and
  the date, in that order).
- Two quick-reply buttons, in this order: `✅ भर दिया`, `⏰ अभी नहीं`. FinBoy sets each button's
  payload at send time to its own `fb1:` prompt ID.

A weekly Sunday summary template was planned as optional and is not built: households ask
"हिसाब" instead, and the helper encourages a daily or weekly हिसाब message.

## Human-only steps and acceptance

The human registers each household's number as a Meta test recipient, creates and submits the
Hindi templates, recruits the helper and households, runs consent visits and the paper-diary
baseline, edits the private allowlist, and approves every production release. Real Hindi voice
round trips, button taps on a phone, voice playback on a low-end Android, reminder delivery and
helper-observed sessions are recorded separately from automated tests.

## Runtime

Branch `feat/finboy-village-pilot`, loopback API 8051 / web 3051, disposable database
`finboy_pilot`. Mocked Meta and provider calls in tests; no production test suites.

## Amendment — money manager round (29 October 2026)

For diary households, money is saved at once and FinBoy asks first only when unsure; households
can undo, change the amount or the category by button, set budgets and a savings goal, and opt in
to a monthly check-in. See [the money manager contract](../money-manager-round/contract.md), which
supersedes "nothing counts until a tap" here only as documented there.
