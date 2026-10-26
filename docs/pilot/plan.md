# Plan: FinBoy WhatsApp voice-first village pilot (Hindi)

## Context

FinBoy in production is built for one literate household that gets bank emails: Gmail import,
English-only web screens, form-based review and city categories. Nothing has been tested with
real users. The goal is a product that low-literacy village households can actually use. The
chosen direction: make **WhatsApp the main interface**. Households record money with Hindi voice
notes, confirm with one tap, hear the replies, and opt in to reminders for dues. A small real pilot
tests this before anything bigger is built.

**Your decisions (26 Oct 2026)**
- Language and region: **Hindi, a North India village**.
- Approved:
  - WhatsApp may confirm, correct (amount) and reject a household's own records by button tap.
    Every change can be undone, and nothing counts until the household taps "हाँ".
  - Up to 10 pilot households, enrolled by hand (no public signup).
  - Opt-in reminders.
- **Not approved:** erasing data from WhatsApp. Erasure stays operator-run on request.
- Number: the **existing Meta test number**. Meta allows at most 5 registered recipients and
  yours is one, so the **pilot is 4 village households plus you**. Growing beyond that needs a
  real business number (a later decision).

**Reused as-is:**
- `services/whatsapp/`: signed webhook, allowlist, STOP/START consent, 24-hour window, metadata-only
  receipts and deliveries.
- `services/speech/service.py` (`transcribe_audio`, `synthesize_speech`).
- Screenshot to review queue: `services/whatsapp/capture.py`, `services/ingestion/screenshot.py`.
- Versioned, undoable decisions: `services/ux/decisions.py` (`decide`, `undo_decision`).
- `services/ux/state.py` (`data_version`).
- `services/money/engine.py` (`money_summary`, `PeriodSpec`).
- `services/ux/obligations.py` (`correct_obligation`).

**Blocking the pilot today:**
- `services/whatsapp/config.py` rejects any allowlisted sender whose household is not
  `LOCAL_USER_ID`.
- `services/imports/runner.py` (`create_run`, `run_import`) and `whatsapp/capture.py` are
  hard-coded to `LOCAL_USER_ID`.
- `whatsapp/events.py` ignores button taps; `whatsapp/meta.py` `send` only sends text or audio.
- Voice notes are always treated as questions, so cash and dues can't be recorded by voice.
- Dues come only from bill/EMI emails, as one-off rows; no user-created dues, scheduler or reminders.
- Sources, categories and due kinds are fixed by database CHECK constraints set for city households.

## How it works for a household

1. **Join.** The helper registers the number (Meta test recipient plus the private allowlist). The
   household sends "नमस्ते". FinBoy replies in voice and text with the consent summary and
   [✅ हाँ, मंज़ूर] [❌ नहीं]. Nothing else works until "हाँ".
2. **Record by voice.** "दूधवाले को पाँच सौ दिए" gets the voice and text reply
   "₹500 · दूधवाला · आज · पैसे गए — सही है?" with [✅ हाँ] [✏️ बदलें] [❌ नहीं].
   - हाँ confirms it and replies "जोड़ दिया ✅" with [↩️ वापस लें] (undo).
   - बदलें asks "सही रकम बोलिए"; the household says "चार सौ"; FinBoy reads it back and asks again.
   - नहीं rejects it (undoable).
   - Money in works the same way: "PM किसान के 2000 आए".
3. **Payment screenshot.** The existing reader, now replying with the same three buttons.
4. **Dues.** "समूह की किस्त 1200, हर महीने 10 तारीख":
   - FinBoy shows a confirm card and saves the due, then asks "याद दिलाऊँ?" [हाँ] [नहीं].
   - Two days before and on the day, it sends [✅ भर दिया] [⏰ अभी नहीं].
   - After paying it asks "अगले महीने भी?" [हाँ] [नहीं].
5. **Ask.** "इस हफ्ते कितना खर्च हुआ?" goes to the existing assistant, answered in Hindi voice and text.
6. **"हिसाब".** This week's money in, money out, dues coming and the top 3 categories, in short
   voice and text.

**Rules kept:**
- Nothing counts until "हाँ"; nothing is ever auto-confirmed.
- Only the household's own number can act on its records.
- No message, audio, image or transcript is stored.
- No investment advice.
- बंद/STOP silences everything.

## Build plan

Work on branch `feat/finboy-village-pilot` from `main`, on free loopback ports (check them first)
with a new disposable database `finboy_pilot`. Pilot flows run only for households with
`users.pilot = true`; you can switch your own household on for the dogfood week. Production
behaviour is unchanged until then.

### Phase 0 — Approvals, setup, recruitment (week 0; mostly you)
- **Record the round:** add a "Village pilot round" section to `AGENTS.md` and write
  `docs/pilot/contract.md`. It covers what is approved, the WhatsApp erasure that isn't, the
  5-recipient test cap, the data kept and the metrics allowlist.
- **Meta (human):**
  - Add the 4 numbers as test recipients (each confirms a code).
  - **Spike:** create two Hindi utility templates (due reminder, weekly summary) on the test
    account and send one to your number. If templates don't work on the test number, use the
    Phase 4 fallback.
- **Speech:** production transcribes with OpenAI today. Switching Hindi to Groq is optional and
  needs your verified key.
- **Recruit:** a trusted local helper (relative, SHG member or bank mitra) and 4 households.
  - In-person consent visits, in Hindi.
  - A 7-day paper-diary baseline: the helper notes counts per category, not names.
  - A short session per household noting the phrases and money categories they actually use.
    This finalizes the category list and the Hindi wording before Phase 3.

### Phase 1 — Separate households on WhatsApp
- **Allowlist:** `whatsapp/config.py` also accepts entries mapped to enrolled pilot households,
  still at most 5 senders and fail-closed. Raw phone numbers stay only in the private env
  allowlist, with no new phone storage in the database.
- **Migration `0008_village_pilot`:** adds `users.pilot`, `whatsapp_bindings.consented_at` and
  `whatsapp_bindings.reminders_opt_in_at`.
- **User-scoped capture:**
  - `create_run`/`run_import` take `user_id` (defaulting to `LOCAL_USER_ID` for existing callers).
  - `capture.py` uses `binding.user_id`, and the import-busy check is per household.
- **Web stays yours:** web routes remain `LOCAL_USER_ID`-only; pilot households have no web access.
- **New operator CLI `services/pilot/cli.py`:**
  - `enroll` creates a "Pilot household N" user (no personal names) and prints the ID for the env
    allowlist. Enrolling means an env update plus a FinBoy restart, per `docs/production.md`.
  - `erase` removes one pilot household's records, dues, decisions, sources, receipts and binding.
    It keeps the audit counts and refuses `LOCAL_USER_ID`.

### Phase 2 — Tap to confirm, with undo
- **Inbound:** `events.py` accepts `interactive.button_reply` and template `button` replies as
  `kind="button"` with a strict ID pattern.
- **Outbound:** `meta.py` adds `send_buttons` (at most 3 buttons, titles of 20 characters or fewer)
  and `send_template` (Hindi, with parameters and quick replies). Both use the same allowlist check
  and the same handling for sends whose outcome is unknown.
- **Migration 0008, prompts:** adds `whatsapp_prompts` with:
  - id, binding, household;
  - purpose: consent, confirm, change_amount, undo, due_paid, due_repeat or reminder_opt_in;
  - transaction, commitment or decision ID;
  - a fingerprint of the record's amount, date, direction and status;
  - state and expiry.

  It also widens the receipt and delivery CHECK constraints (button, interactive, template, new
  error codes). No message-text columns.
- **New `whatsapp/confirm.py`:**
  - Sends the card as text plus a Hindi voice readback (`synthesize_speech`, then `upload_audio`).
  - On a tap it checks the prompt belongs to this household, is open, is under 7 days old and the
    record's fingerprint is unchanged. Then it calls `decide(... action confirm|reject,
    expected_version=data_version(session, user_id))`.
  - It replies with an undo button that calls `undo_decision`.
  - After बदलें, the next message within 10 minutes is read as an amount and sent as
    `decide(action="confirm", correction={"amount_minor": …})`.
- **Consent gate:** in `processor.py`, until `consented_at` is set, every message gets the consent
  card. Hindi बंद/शुरू work alongside STOP/START.

### Phase 3 — Record money by voice
- **New `whatsapp/statement.py`:** a structured OpenAI parse of the transcript, following the
  `assistant/intent.py:parse_intent` and `screenshot.py:read_payment` pattern (untrusted input,
  no tools, `store=False`). It returns:
  - type: spent, received, due, question or unclear;
  - the amount phrase and counterparty as literal substrings of the transcript;
  - mode: cash, UPI or unknown;
  - when: today, yesterday or a date phrase;
  - a closed-list category, and the due day for dues.
- **New `ingestion/hindi_numbers.py`:** checks amounts deterministically from digits and
  Hindi/Hinglish number words (सौ, हज़ार, लाख, डेढ़, ढाई, सवा, साढ़े, "paanch sau"). If an amount
  can't be confirmed, FinBoy asks "कितने रुपये?" and never guesses.
- **Routing in `processor.py`:**
  - A question goes to the existing assistant.
  - A statement is rendered as one payment line, like screenshots ("Rs. 500.00 paid to doodhwala
    in cash on 26-10-26"). It goes through `screenshot.as_message` and
    `run_import(source="whatsapp_voice", user_id=…)`, lands in Review, then gets a confirm card.
  - Anything unclear gets [📝 लिख लो] [❓ सवाल है].
- **Migration:**
  - Adds source `whatsapp_voice` and classification `self_reported`.
  - Adds the week-0 categories. Draft list: farming, livestock, phone_recharge, family_events,
    remittance, wages, crop_sale, govt_benefit.
  - Kept in sync in `db/models/ledger.py`, `ingestion/types.py`, `ingestion/pipeline.py`,
    `ledger/categories.py` (Hindi keyword rules) and `assistant/intent.py` `CATEGORIES`.
  - Also updated in web `apps/web/src/lib/api/money.ts` and `lib/labels.ts`, so the web schemas
    keep accepting the data.

### Phase 4 — Dues and reminders
- **Saving dues:** a statement of type `due` gets a confirm card, then becomes
  `Commitment(kind="loan", confidence 1, source_event_id NULL)`; the migration adds `loan`.
- **Paid and repeat:** "भर दिया" runs `correct_obligation` (status paid), then "अगले महीने भी?"
  creates the next due. There is no recurrence engine.
- **Opt-in:** the prompt after a household's first due sets `reminders_opt_in_at`.
- **Sending:**
  - New `whatsapp/reminders.py` with a `whatsapp_reminders` table: commitment, kind
    (two_days, due_day, weekly_summary), state, and a unique constraint on (commitment, kind) so a
    reminder is never sent twice.
  - A systemd timer runs it every 30 minutes, 08:00–20:00 IST, like the existing backup timer,
    and sends the approved template.
- **Fallback without templates:** if a household writes within 24 hours of a due, the reminder is
  added to the reply, and the helper encourages a daily "हिसाब" message.

### Phase 5 — Weekly summary and pilot report
- "हिसाब"/"hisaab" returns
  `money_summary(session, user_id=…, period=PeriodSpec(range Monday→today))`
  in three short lines plus voice.
- An optional Sunday-evening summary template goes to opted-in households, via the reminder job.
- **`pilot report`** shows, per household and week:
  - active days, and records by channel (voice, screenshot, text);
  - confirm, change, reject and undo counts;
  - dues created, paid and reminded;
  - speech and parsing failures, and consent or STOP changes.

  Counts only: no amounts, names or text.

## Measurement (weeks 5–8)

| Measure | How | Target |
| --- | --- | --- |
| Coverage | FinBoy records ÷ paper-diary entries (counts the helper matches) | ≥ 60% by week 3 |
| Self-service | Confirmations done without help (helper log) | ≥ 80% |
| Accuracy | बदलें taps ÷ captures; wrong confirmations found in the weekly check | ≤ 15% / ≤ 5% |
| Engagement | Active days per household per week | ≥ 4 |
| Dues | Reminded dues paid by the due date, compared with the baseline interview | Most |
| Understanding | Explains "हिसाब" in their own words (3 questions, weeks 2 and 4) | 3 of 4 households |
| Cost | Provider usage per household-week (speech, voice, vision, assistant) | Recorded; sets the budget |

In week 9, decide whether to move to a real business number and 20–50 households, or to rework.

## Main files
- `apps/api/src/finboy/services/whatsapp/`: `config.py`, `events.py`, `meta.py`, `processor.py`,
  `capture.py`; new `confirm.py`, `statement.py`, `reminders.py`.
- `apps/api/src/finboy/services/imports/runner.py`; `services/ingestion/{pipeline,types}.py`
  and new `hindi_numbers.py`; `services/ledger/categories.py`; `services/assistant/intent.py`.
- `apps/api/src/finboy/db/models/{core,ledger,whatsapp}.py`;
  `apps/api/alembic/versions/0008_village_pilot.py`; new `services/pilot/cli.py`.
- `apps/web/src/lib/api/money.ts`, `apps/web/src/lib/labels.ts` (category sync only).
- `AGENTS.md`, new `docs/pilot/contract.md`, `docs/whatsapp.md`, `docs/production.md`
  (timer, enrollment).

## Verification
- **Unit tests (pytest, no PostgreSQL):**
  - Synthetic Meta payloads for button and template replies, and button-ID validation.
  - A household can't act on another household's record.
  - The consent gate.
  - Confirm, reject and undo through `decide`/`undo_decision`.
  - Expired prompts, and refusal when the record changed.
  - Hindi number tables: डेढ़ सौ=150, ढाई हज़ार=2500, सवा लाख=125000, "paanch sau"=500.
  - A stated-but-unconfirmable amount is never recorded.
  - Reminders are never sent twice; template payload shape; the 24-hour window.
  - No message-content columns, and only allowlisted log fields.
- **Integration (disposable `finboy_pilot`):**
  - You plus 2 pilot households, with ledgers, summaries, decisions and reminders kept separate.
  - `pnpm db:migrate`, `pnpm db:check`, `pnpm test:integration`, `pnpm check`, `pnpm build`.
- **Local end to end:** through the restricted ingress (`pnpm dev:whatsapp-ingress`) with signed
  synthetic payloads; Meta calls are mocked.
- **Production, only with your go-ahead:** follow `docs/production.md` (backup, additive migration,
  restart only FinBoy). One week on your own number first, then the 4 households.
- **Human acceptance, recorded separately:**
  - A real Hindi voice note produces the card, a tap updates the total.
  - The voice reply plays on a low-end Android.
  - A reminder (or the fallback) arrives.
  - Sessions the helper observes.

## Timeline
- Week 0: setup and baseline.
- Weeks 1–3: build phases 1–5.
- Week 4: your own number.
- Weeks 5–8: the pilot.
- Week 9: review.
