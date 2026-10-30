# Fast decisions round — contract (30 October 2026)

This round puts Liquid AI's d1-ultra decision model in front of FinBoy's slower OpenAI calls. It
supersedes earlier statements only where it says so:
- "every question uses OpenAI" and "the old rules-first short circuit no longer bypasses AI for
  recognized questions" ([capture-round handoff](../capture-round/handoff.md)): sure, common
  questions are now answered from the engine and templates, without the model's prose;
- "Clarifications, purchase questions and neutral education use the model's prose"
  ([voice](../voice.md)): a sure "what is SIP?" now gets the education template;
- "the statement model returns the first payment…" ([money manager](../money-manager-round/contract.md)):
  the statement model now reads only what d1-ultra is not sure of.

Everything else in earlier contracts still binds. This applies to every household, the owner's web
app included.

## Human decisions (30 October 2026)

- **Model:** Liquid AI's d1-ultra (`https://api.liquid.ai/decisions/v1/systemone`), wherever it makes
  FinBoy answer faster.
- **Questions:** when d1-ultra is sure a question is a common one, answer straight from FinBoy's own
  figures; the OpenAI-written intro line is dropped.
- **Rollout:** switch on straight after the offline test set passes; one setting turns it off.
- **Photos:** add the d1-ultra check, so a photo that is not a payment or bill gets an instant reply.
- **Where it lives:** branch `feat/finboy-fast-decisions` from main `b89821d`; loopback API 8061 and
  web 3061; disposable database `finboy_signup`; no migration.

## What d1-ultra is

A decision model: given text or pictures and named questions, it returns calibrated probabilities
for yes/no ("noul") and choice questions in one pass and writes no text. It cannot copy phrases,
read a screenshot, transcribe or word a reply, so it replaces none of those calls. Liquid publishes
no language list, no rate limits and no API data-retention terms.

## What gets faster

| Message | Before | When d1-ultra is sure |
|---|---|---|
| A simple entry: "chai 20", "salary 30000 aayi", "food budget 5000", "save 5000 a month" | OpenAI statement call | d1-ultra sorts it and picks the category; code reads the amount (`hindi_numbers.parse_amount`) and the day (`_past_day`), as the rules do |
| A check-up in other words: "aaj ka kharcha batao", "is hafte ka hisaab dikhao" | Statement call, then the assistant | The today, week or month check-up (`cfo.CHECKUPS`), no model |
| A greeting or chit-chat | Statement call | The "not sure" reply |
| A common question: spending (total or a category), income, what's left, bills due, a money term, a fund or share pick | Assistant call that writes the reply | The engine's figures, dates and warnings in the templates; a pick declines |
| A photo that is neither a payment nor a bill | Vision read | The existing "send a payment screenshot or a bill photo" reply |
| **Stays on the model:** a payee named, several items, a pasted bank SMS, a due, a purchase, "can I afford", a shop or person, anything the keyword rules read differently, or d1-ultra unsure, late or down | — | Exactly as before |

**No reply waits longer.** `triage.first()` starts today's model call and the d1-ultra request
together. The model's answer is used if it comes first; a sure d1-ultra answer is used only while
the model is still working, and also when the model fails. OpenAI spend is unchanged.

An explicit security pick that the rules already decline ("Which stock should I buy?") no longer
calls OpenAI at all: its answer was always overridden.

## How it decides

- `services/triage/provider.py`: the HTTP adapter. Only `d1-ultra` is accepted; any failure,
  oversized or malformed answer is a fixed `ProviderUnavailable`; no bodies are logged.
- `services/triage/service.py`: three question sets, one request each, and `first()`.
  - **Message:** kind (spent, received, due, budget, goal, today, week, month, question, other),
    several payments (yes/no), names a payee (yes/no), category (the closed list or none), mode.
    The wording follows the statement prompt's verbs and the category words (see the results).
  - **Question:** intent, money term, the one category it names (or none), names a shop or person
    (yes/no).
  - **Photo** (a JPEG of at most 768 px made from the cleaned image): payment screen, bill or other.
- **Sure** means a choice's probability of at least `SURE` (0.85), a yes/no answer within
  `CLEAR_NO` (0.1) of 0 or 1, and a photo "other" at `IMAGE_SURE` (0.95), as set by the offline
  gate (results below).
- A sort is skipped when `TRIAGE_ENABLED` is false, the message's language is not in
  `TRIAGE_LANGUAGES`, the settings are missing, or the call takes longer than
  `TRIAGE_TIMEOUT_SECONDS`.
- **Fast answers stay conservative.** A question is answered fast only when the keyword rules do
  not read it as a merchant lookup, a simulation or a currency question, it names no rupee amount
  (so "GT 650" never becomes a period question), and d1-ultra is clear it names no shop or person.
  For spending, either the keyword rules name the category and d1-ultra's leading choice is the
  same, or the rules name none and d1-ultra is sure of the category or that none is named (all
  spending).

## Offline gate

`pnpm eval:triage` runs 171 synthetic cases (`apps/api/fixtures/triage/`) through the real
`statement._fast`, `intent._quick` and photo check against live d1-ultra: 102 diary messages and 53
questions in English, Hindi, Hinglish, Malayalam and Manglish (39 of them must go to the model), and
16 pictures (six payment screens in light, dark and Hindi, four bills, six pictures that are not
money). Each case is sorted three times (`--runs`), because d1-ultra's probabilities vary a little
between calls. It reports, per language and for several thresholds, the fast share of the cases
that may be answered fast, fast mistakes by case ID, and d1-ultra's p50/p95 latency.
`pnpm eval:triage --check` (also a unit test) confirms that the cases agree with the code when
d1-ultra answers perfectly, and that no rule answers a case before d1-ultra sees it.

**Gate, per language (Hinglish counts with Hindi, Manglish with Malayalam):**
- no fast answer on a case that must go to the model (payee, several items, SMS, due, purchase,
  "can I afford", shop or person) or on a fund pick, and no wrong amount;
- at most 2% fast mistakes overall;
- for pictures, no payment screen or bill sorted as "other".

`TRIAGE_LANGUAGES` lists only the languages that pass.

**Results (31 October 2026): passed** for English, Hindi and Malayalam, and for pictures.
`pnpm eval:triage` against live d1-ultra from the development Mac: three runs of all 171 cases,
513 answers, none unavailable.

| | English | Hindi | Malayalam | Pictures |
| --- | --- | --- | --- | --- |
| Fast share at the chosen thresholds | 95% | 94% | 67% | 100% |
| Fast share at `SURE` 0.8 / 0.9 / 0.95 | 99 / 86 / 82% | 99 / 87 / 66% | 73 / 63 / 55% | — |
| Fast mistakes, any `SURE` from 0.8 to 0.95 | 0 | 0 | 0 | 0 |

- **Fast share** is the share of answers to cases that may be answered fast: 38 English, 47 Hindi
  with Hinglish, 31 Malayalam with Manglish, and 6 pictures that are not money. None of the cases
  that must go to the model was answered fast, and no payment screen or bill was ever sorted "other".
- **Wording.** The first run gave English 78%, Hindi 73% and Malayalam 55%.
  - d1-ultra had read paid bills as dues ("bijli bill 900 bhara").
  - It hesitated on an item with just an amount ("kirana 450") and took GPay or "kirana" for a payee.
  - It split "food" between groceries and food dining.
  - Common spending questions waited for the model: d1-ultra was rarely sure that "How much did I
    spend this month?" names no category (0.5–0.7).

  The final wording and rules fix this, with no new mistakes:
  - The message questions use the statement prompt's verbs for spent, received and due.
  - They say an item with just an amount is spent, and that kinds of spending and ways to pay are
    not payees.
  - Food in general is food dining, as in `categories.SYNONYMS`.
  - The question's category asks which one kind it *names*, so a question about all spending is
    "none" at 0.95 or more.
  - When the keyword rules name the category ("food"), d1-ultra's leading choice only has to agree.
- **Chosen:** `SURE` 0.85, `CLEAR_NO` 0.1, `IMAGE_SURE` 0.95, `TRIAGE_LANGUAGES=["en","hi","ml"]`.
  - In a separate three-run check with the final wording, only 3 of 513 answers were wrong in a way
    that would have changed a reply. All three were one Manglish "this week" request read as "this
    month", the surest at 0.58.
  - 0.85 keeps a wide margin for real messages, which are messier than these, and is fast for
    nearly all English and Hindi cases.
  - The yes/no threshold stays strict: it guards payees and several items, and loosening it gained
    almost nothing.
  - Photos stay at 0.95: 0.98 halves their fast share, and a payment screenshot sorted "other" costs
    more than a slower reply.
- **Held-out check:** 26 new cases that the wording was not tuned on, three runs each, twice, in all
  five language groups.
  - 85–91% of the answers that may be fast were fast.
  - No payee, several-item, due, shop or affordability case was answered fast.
  - The only detail was "ഈ മാസം യാത്രയ്ക്ക് എത്ര ചെലവായി?": d1-ultra read യാത്ര (journey) as travel
    (train, flight, hotel) rather than transport. FinBoy has both categories.
- **Latency** from the development Mac in India: p50 0.55 s and p95 0.90 s.
  - Other runs gave p95 between 0.77 s and 1.26 s.
  - Fewer than 1% of calls came back unavailable, either late or failed; the adapter does not
    record which.
  - About 0.1 s of each call is connection setup.
  - The server's figures will come from `triage.sorted` after release.
- **Cost:** a diary message is about 780 input tokens, $0.00003 by Liquid's usage figure.
- **Local end-to-end** (API 8061, web 3061, disposable `finboy_signup`, local OpenAI key rejected):
  answers came from d1-ultra alone, with `triage.answered` outcome `fast`.
  - Quick add read "chai 20" as money out, ₹20, today, food and dining (651 ms).
  - "How much did I spend this month?" got the engine's ₹8,550 with its three supporting records
    (646 ms).
  - "How much did I spend on food this month?" got food and dining, ₹4,200 (562 ms).
  - The in-app privacy screen shows the Liquid AI sentence at desktop and 375 px widths, with no
    sideways scrolling.
- **Not covered:** real voice transcripts, real photos and real spelling. Human acceptance covers
  them.

## Settings

| Setting | Value |
| --- | --- |
| `LIQUID_API_KEY` | from the Liquid Console (`liquid_…`); backend only |
| `LIQUID_DECISION_MODEL` | `d1-ultra`, after a synthetic live check |
| `LIQUID_BASE_URL` | `https://api.liquid.ai` (default) |
| `TRIAGE_ENABLED` | `false` in code; `true` once the gate passes and the human releases it |
| `TRIAGE_LANGUAGES` | JSON list of languages that passed, such as `["en","hi"]` |
| `TRIAGE_TIMEOUT_SECONDS` | 2 (0.5–10) |

`/api/v1/readiness` reports `triage_configuration`: `off`, `configured` or `missing`.

## Data and privacy

- **Sent to Liquid AI:** a diary message with account, card, reference and phone numbers masked
  (the same text the statement model gets); a question (as OpenAI gets it); a small JPEG of a
  cleaned photo. Never audio, ledger rows or engine amounts.
- **Stored:** nothing new. No message, image, transcript or d1-ultra answer is kept.
- **Logs:** `triage.sorted` (stage, outcome, latency, provider, model) and `triage.answered`
  (stage, fast or model, latency); `whatsapp.processed` adds the reply time per kind of message.
  Fixed fields only.
- **Privacy policy:** names Liquid AI ("quickly telling what a message, question or photo is
  about"), on the public policy and the in-app privacy screen.

## Human steps

1. **Liquid key:** create a Liquid Console organisation and API key, save it in
   `~/.config/finboy/secrets.env`, and run `pnpm eval:triage` with it locally. Done 31 October 2026;
   the gate passed (results above).
2. **Data terms:** the privacy policy promises providers do not keep or train on data where they
   offer that choice. Check Liquid's console and terms for this before any real household's
   message or photo reaches it.
3. **Release:** following [production](../production.md#fast-decisions-release-procedure).
4. **Acceptance:** real phone messages, questions and a stray photo in each enabled language,
   recorded separately from these checks.
