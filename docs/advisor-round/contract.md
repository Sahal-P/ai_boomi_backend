# Advisor round — contract (7 November 2026)

This round turns Ask into FinBoy's advisor: one money coach on the web and WhatsApp. It reads the
household's own records through read-only tools, keeps its chats, and remembers what matters,
like ChatGPT's memory. It supersedes earlier statements only where it says so:
- **Ask stores nothing** ([phase 1](../phase1/contract.md), [UI refresh](../ui-refresh/contract.md)):
  chats with FinBoy (questions and answers) and saved memories are now kept until the household
  deletes them.
- **"Never store messages, transcripts"** (pilot, sign-up and later rounds): only for questions
  to the advisor and its answers. A voice question is kept as its words, never as audio. Diary
  messages, audio, photos and screenshots are still never stored.
- **"Model output never selects SQL or tools"** and **"generated context cannot contain financial
  figures"** ([assistant](../voice.md)): the model now chooses among read-only tools over the
  money engine, and may quote figures that come from FinBoy's own numbers (checked below).
- **Ask is Premium** ([subscription round](../subscription-round/contract.md)): typed questions
  are for every household. Voice, spoken replies, photos and statements stay Premium.
- **Sure common questions are answered from templates** ([fast decisions](../triage-round/contract.md)):
  with the advisor on, questions go to the advisor; the keyword rules answer only as its fallback.
  Diary entries keep the Liquid fast path.

Everything else in earlier contracts still binds.

## Human decisions (7 November 2026)

- **Goal:** the best AI advisor, with a personalised experience and long-term memory "just like
  ChatGPT".
- **Privacy is not a blocker.** The AI may see the household's figures, payee names, memories and
  recent chats. Chats and memories are kept until the household deletes them. The published
  privacy policy is updated so it stays true.
- **Advice scope: a money coach.** Budgeting, saving, an emergency fund, loans and EMIs, fraud
  safety and government schemes in general terms. FinBoy never names, ranks or recommends a fund,
  stock, share, bond, crypto coin, insurance policy or loan product, and never says to buy, sell
  or hold one (personalised investment advice for a fee generally needs SEBI investment-adviser
  registration).
- **Access: everyone.** The advisor and memory are free for every household, within
  `DAILY_AI_LIMIT`.
- **Memory like ChatGPT's.** It learns on its own, says "Saved to memory", and the household can
  see, edit and delete each memory, delete them all or turn memory off.
- **Phases:** 1, the personal advisor with memory; 2, a vetted knowledge library with sources and
  deeper recall (built without pgvector: see [Phase 2](#phase-2-money-guides-deeper-recall-diary-memory-and-live-steps));
  3, a proactive coach (opt-in nudges).

## How a question is answered

`services/advisor/service.py: advise()`:
1. **Context.** A static system prompt (the coach's rules, tool policy, advice boundary, memory
   policy, reply styles) comes first so OpenAI's prompt caching can reuse it. Then the household's
   context: today's IST date, the reply style, its saved memories (each with a short reference),
   a snapshot of its money, summaries of its last three earlier chats, the last eight turns of
   this chat, and the question.
2. **Model.** `responses.parse` with the read-only tools and the `AdvisorReply` output, `store=False`,
   reasoning effort `ADVISOR_REASONING_EFFORT`, one shared client.
3. **Tools.** Code runs each call for the signed-in household only and returns the outputs, for at
   most `ADVISOR_MAX_TOOL_ROUNDS` rounds; then the model must answer without tools. The engine's
   read lock is released before every network call.
4. **Checked figures** (`grounding.py`). Every rupee amount, percentage and number of 100 or more
   in the reply must appear in a tool result, the snapshot, a memory, the chat or the question
   (₹1,20,000, 120000, "1.2 lakh" and native digits count as one figure). If not, the model gets
   one correction; if it still fails, the fallback answers.
5. **Saved.** The question and answer are added to the chat, memory changes are applied, and the
   answer goes back with `thread_id`, `memory_changes` and `follow_ups`.
6. **Fallback.** On a timeout, error or unchecked figure, the keyword rules and templates answer
   (`answer_question(rules_only=True)`, no model call), so an OpenAI outage still answers common
   questions. An explicit security pick is declined by the rules without any model call.

### Tools (read-only, `services/advisor/tools.py`)

| Tool | Engine function |
|---|---|
| `money_summary(period)` | `engine.money_summary` |
| `category_spending(period, category)` | `engine.category_breakdown` |
| `find_payments(period, payee, category, direction, limit)` | `engine.find_transactions` (confirmed only; totals by code; rows become evidence) |
| `payees_and_people(period)` | `insights.money_insights` |
| `dues(days_ahead)` | `engine.upcoming_commitments` |
| `budgets_and_goal(period)` | `budgets.month_plan` |
| `compare(metric, category, first, second)` | two engine reads; difference and percentage computed in code |
| `afford_monthly(monthly_rupees)` | `engine.simulate_monthly_commitment`, only for an amount the person said |
| `plan_numbers(calculation, …)` | Phase 2: saving per month, months to a goal or an EMI, computed in code |
| `search_past_chats(query)` | Phase 2: the household's earlier chats (`history.search`) |
| `search_knowledge(query)` | Phase 2, with `KNOWLEDGE_ENABLED`: FinBoy's money guides (`knowledge.search`) |

Periods are named (`today`, `this_week`, `last_month`, `last_n_months`…) and worked out in code.

### Memory (`services/advisor/memory.py`)

- Kinds: about, goal, plan, preference, person, note. Written in English, at most 300 characters.
- Never kept: OTPs, PINs, passwords, CVVs; long numbers and PANs are masked.
- One copy per fact; at most `ADVISOR_MEMORY_LIMIT` per household (80, then 300 from phase 2),
  the oldest makes room.
- The model may only update or forget memories it was shown, by reference.
- `users.memory_enabled` off: memories are neither used nor saved (saved ones stay).

### Chats (`services/advisor/history.py`)

- Web: "New chat" starts a chat; Recent chats reopens one. WhatsApp: one rolling chat that ends
  after six quiet hours.
- Quiet chats get a two- or three-sentence summary and a title in the background
  (`summaries.py`); later chats see the last three.

## On WhatsApp

- With `ADVISOR_ENABLED`, questions and everyday chat ("hi", "I'm saving for a bike") go to the
  advisor for every household; before, everyday chat got "I didn't understand". Money entries,
  dues, budgets, goals and check-ups work as before.
- A reply adds "📝 Saved to memory" (Hindi and Malayalam too) when the advisor saved something.
- Commands without a model, in English, Hindi and Malayalam: "memory off" / "memory on",
  "forget everything", "clear chat history".
- Follow-up suggestions are web-only (WhatsApp reply buttons hold 20 characters).

## On the web

- Ask: free typed questions, personal starter questions (`GET /assistant/suggestions`, no model
  call), follow-up chips under the latest answer, a "Saved to memory" note with Manage, and
  Recent chats (web and WhatsApp). Earlier answers are shown without speech or evidence.
- Memory page (account menu → Memory): memories grouped by kind with edit and delete, the
  on/off switch, "Forget everything" and "Clear chat history".
- Pricing: asking and memory are listed under Free.

## API (additive)

- `POST /assistant/ask`: every signed-in household (`CurrentUser`) while `ADVISOR_ENABLED`;
  `AskRequest.thread_id`; `AssistantAnswer.thread_id`, `memory_changes`, `follow_ups`. With the
  flag off it is Premium and answers as before.
- `GET /assistant/threads`, `GET|DELETE /assistant/threads/{id}`, `DELETE /assistant/threads`,
  `GET /assistant/suggestions`.
- `GET|DELETE /memory`, `PATCH|DELETE /memory/{id}`, `PUT /memory/settings`.
- Another household's chat or memory reads as 404. `GET /auth/session` reports `advisor`.
- Readiness and the admin panel report `advisor` as off, configured or missing. Admins never see
  chats or memories.

## Data

Migration `0015_advisor` (additive): `advisor_threads`, `advisor_messages` (role, text, language,
tool names), `household_memories`, and `users.memory_enabled`. Erasure removes them with the
household's records; the export includes `memories` and `chats`. The downgrade refuses while any
memory or chat remains. Logs carry the outcome, tool names, counts and latency only.

## Settings

| Setting | Default |
|---|---|
| `ADVISOR_ENABLED` | false |
| `OPENAI_ADVISOR_MODEL` | unset: `OPENAI_ASSISTANT_MODEL` (set only after a live capability check) |
| `ADVISOR_REASONING_EFFORT` | low |
| `ADVISOR_TIMEOUT_SECONDS` | 20 (each call; a question gives up after twice this) |
| `ADVISOR_MAX_TOOL_ROUNDS` | 4 |
| `ADVISOR_HISTORY_TURNS` | 8 |
| `ADVISOR_MEMORY_LIMIT` | 300 (80 in phase 1) |
| `ADVISOR_MEMORY_PROMPT` | 40 (phase 2) |
| `KNOWLEDGE_ENABLED` | false (phase 2) |
| `OPENAI_EMBEDDING_MODEL` | unset: keyword search only (phase 2; set only after a live check) |
| `ADVISOR_EMBEDDING_DIMENSIONS` | 256 (phase 2) |

## Offline gate

`pnpm eval:advisor` runs synthetic questions through the real loop against a synthetic household
(`services/advisor/synthetic.py`). `--check` needs no network: it confirms each case is well
formed and that every figure it expects is one FinBoy can give. Live, each case runs three times.
To pass: no fallbacks, ≥95% of expected figures and policies, 100% refusals, ≥90% memory, ≥95%
reply script; p50 and p95 latency are printed. The starter set has 33 cases (English 14, Hindi 6,
Hinglish 5, Malayalam 5, Manglish 3); grow it towards about 200 with real (consented) phrasing
from the pilot before release.

## Where it lives

Branch `feat/finboy-advisor` from main `42b1a53`, loopback API 8101 and web 3101, disposable
database `finboy_advisor`, migrations `0015_advisor`, `0016_knowledge` and `0017_coach`.
`ADVISOR_ENABLED` stays false until the live gate passes and the human approves the release;
`COACH_ENABLED` stays false until the human releases the coach (phase 3).

## Human steps

1. Approve this contract and, later, the release (`ADVISOR_ENABLED=true` with the web release,
   since the pricing copy lists asking under Free).
2. Before relying on the WhatsApp advisor: replace the WhatsApp user token (expires
   23 December 2026) with a permanent System User token.
3. A native read of the new Hindi and Malayalam copy (`hindi.py`, `malayalam.py`).
4. Phase 2: the guide review and the embedding check in [its human steps](#human-steps-phase-2).
5. Phase 3: the steps in [its human steps](#human-steps-phase-3), Meta's approval of the coach
   template among them.

## Verification — 7 November 2026 (phase 1, local)

- `pnpm check`: Ruff clean; 1,480 API unit tests (61 new for the advisor) and 106 web unit tests
  passed; strict TypeScript. `pnpm build` passed with the new `/memory` route.
- `pnpm db:migrate` to `0015_advisor` and `pnpm db:check` (no drift) on `finboy_advisor`;
  `pnpm test:integration`: 113 passed (3 new), with `OPENAI_API_KEY` blank.
- Playwright against the contract double: the new advisor spec (a Free household asks by typing,
  follows up in the same chat and reopens it; memory saved, edited, refused with a PIN, switched
  off and forgotten; the account menu's Memory) and the existing Ask spec passed at 1440, 390 and
  320 px.
- Browser against the real API on 8101 with `ADVISOR_ENABLED=true` and no model key: a typed
  question was answered by the keyword rules (the degraded path) from a quick-added record and
  kept as a chat that Recent chats reopens; the Memory page listed, grouped and edited memories at
  desktop and 375 px; with the API stopped the app showed its "couldn't be reached" state.
- `pnpm eval:advisor --check` passed (33 cases). **The live gate has not run**: the OpenAI key in
  the private secrets file returns 401 `invalid_api_key` (as the money-manager round recorded), so
  every live case took the fallback. Nothing in this round has been verified against a real model
  answer, WhatsApp delivery or phone playback.

## Phase 2: money guides, deeper recall, diary memory and live steps

Built on phase 1 on the same branch (7 November 2026): migration `0016_knowledge`, no new
dependency. Two decisions were made while building it; no human decision changed:
- **No pgvector.** Embeddings are kept as `real[]` and compared in Python. A household has at most
  a few hundred memories and chat summaries and there are about forty guides, so a vector index
  buys nothing, while pgvector would need an extension on voxpay's PostgreSQL and on the shared
  development container. This supersedes the plan's "phase 2 needs pgvector".
- **Search by keywords and by meaning.** Keywords always (BM25 over the text and trilingual search
  terms, whole-phrase hits weighing more); meaning (OpenAI embeddings, cosine similarity) when
  `OPENAI_EMBEDDING_MODEL` is set; the two rankings are fused by reciprocal rank. Without
  embeddings everything still works by keywords.

### Money guides (`apps/api/knowledge/*.md`, `services/advisor/knowledge.py`)
- 33 guides:
  - Budgeting, saving and planning: budgeting basics, an emergency fund, irregular income, saving
    habits, big purchases, festivals and weddings, school fees.
  - Debt: the order to pay off debts, EMIs, moneylenders, bank charges, credit scores, SHG loans,
    the Kisan Credit Card.
  - Safety: UPI, loan apps, OTP and KYC scams, bank complaints.
  - Schemes: PM-KISAN, Jan Dhan, Atal Pension, PMSBY, PMJJBY, Ayushman Bharat, Sukanya Samriddhi,
    PPF, NPS.
  - Ideas: fixed and recurring deposits, SIPs, index funds, diversification, insurance, health
    insurance.

  They explain and never name or rank a product.
- Each guide has:
  - an English body;
  - titles in English, Hindi and Malayalam;
  - search terms in all three languages and their Latin spellings;
  - official `https` sources;
  - `reviewed_on`.
- **Production serves only guides with `reviewed_on`.** All 33 are drafts written in this round.
  A person checks each against its official sources (scheme amounts and rules change) and fills
  `reviewed_on` before it is served.
- `search_knowledge(query)` returns the best three guides. It is offered only with
  `KNOWLEDGE_ENABLED`.
- The reply lists the guide ids it used in `sources`. Code keeps only guides that were actually
  retrieved and returns them as `AssistantAnswer.sources`, each with:
  - `id`;
  - `title`, in the reader's script;
  - `url`, the first official source.
- The cited guides show:
  - on the web, as chips under the answer linking to the official site;
  - on WhatsApp, as a "📚 From FinBoy's money guides: …" line with the links.
- Figures a guide states (₹6,000 a year from PM-KISAN) pass the figure check, because they are in a
  tool result.
- `pnpm knowledge:index` checks every guide parses. With embeddings on, it caches the guides'
  embeddings in `knowledge_embeddings`, keyed by content hash, model and size. Otherwise they are
  computed on first use.

### Planning figures
- `plan_numbers` works out, in code:
  - a monthly saving towards a target by a month;
  - the months to reach a goal;
  - a loan's EMI, with the total paid and the interest.

  It uses `Decimal` and rounds up to whole rupees.
- Every input must be given, or the tool tells the model to ask instead:
  - **amounts:** ones the person said (their words, earlier turns, memories) or FinBoy showed (the
    snapshot, tool results);
  - **interest rate:** one the person gave.

### Deeper recall
- **Memory.** Up to `ADVISOR_MEMORY_LIMIT` (now 300) per household.
  - With at most `ADVISOR_MEMORY_PROMPT` (40), every memory goes into the prompt, as before.
  - Beyond that, the prompt gets the 10 most recent and the 30 closest to the question (keywords,
    plus meaning with embeddings).
  - Missing embeddings are computed in the same call as the question's and saved. Editing a memory
    clears its embedding, which is computed again later.
- **Earlier chats.** `search_past_chats(query)` searches the household's newest 200 chats, leaving
  out the current one: by their words and, with embeddings, by their summaries' meaning. It
  returns up to three, each with its summary and the closest exchange.
- **Summaries.** The background job gives new summaries embeddings and backfills up to 20 older
  ones a run. A chat that continues after it was summarised is summarised again once it goes quiet.

### Diary memory (WhatsApp)
- The diary reader may also return one lasting fact the message states, such as "Ramesh is the
  milkman". It is the same model call that reads "Ramesh doodhwale ko 60 diye".
- It never returns a guess, an amount, a number or anything about health.
- With the advisor and the household's memory on, the fact is saved as a memory (source
  `whatsapp`). The reply ends with "📝 Saved to memory" only when the fact is new.
- The message itself is still never stored.
- Liquid's fast path and the no-model rules never learn facts.

### Live steps on the web
- `POST /api/v1/assistant/ask/stream` answers as server-sent events, only while the advisor is on:
  1. `progress` events with the step: `thinking`, then each tool's name as it starts.
  2. Then one `answer` (the same `AssistantAnswer`) or one `error` (a `{status, error}` envelope).
- The flag, the daily AI limit and chat ownership are checked first. Those failures stay ordinary
  JSON errors.
- The advisor runs in a worker thread with its own database session. A closed connection stops the
  stream, not the answer, which is still kept in the chat.
- While it works, Ask shows the step in words, such as "Looking at your spending…" or "Reading
  FinBoy's money guides…".
- `POST /assistant/ask` is unchanged.
- The production proxy already streams (`proxy_buffering off`), and the response also sends
  `X-Accel-Buffering: no`.

### API, data and settings
- `AssistantAnswer.sources` is additive.
- Readiness reports:
  - `knowledge_configuration`: `off`, `configured`, or `missing` (switched on with nothing reviewed
    to serve);
  - `knowledge_search`: `keywords` or `keywords_and_meaning`.
- The admin panel shows "Money guides".
- Migration `0016_knowledge` is additive:
  - `knowledge_embeddings`;
  - `embedding` and `embedding_model` on `household_memories`;
  - `summary_embedding` and `embedding_model` on `advisor_threads`.

  Everything it adds can be recomputed, so its downgrade drops them.
- Settings are in the table above.
- Embeddings are requests to OpenAI with the memory, summary, guide or search text. Only the
  numbers that come back are kept. Logs: `advisor.embedding` with the outcome and count only.

### Gate
- 42 cases: English 18, Hindi 7, Hinglish 7, Malayalam 6, Manglish 4.
- Nine are new:
  - **Guides:** each must cite the expected guide.
  - **Planning:** each expected figure is confirmed offline by running `plan_numbers` on the
    case's own words.
- New gate: sources ≥ 90%.
- The live run switches the guides on.

### Also fixed in phase 2
- **Bold markers.** The web showed the advisor's WhatsApp-style `*bold*` as literal asterisks. It
  now renders them as bold.
- **What an answer rests on.** The records warning and the "From your household records" badge
  now appear only when the answer used the household's records: a record tool, or a figure from
  their snapshot.
  - An answer from the guides alone is badged "From FinBoy's money guides".
  - Planning maths and greetings claim neither.
- **Continued chats.** A chat that continues after its summary is summarised again once it is
  quiet.

### Verification — 7 November 2026 (phase 2, local)
- **`pnpm check`:** Ruff clean; 1,523 API unit tests passed (phase 1 had 1,480); 114 web unit
  tests passed; strict TypeScript. Covered:
  - guides, ranking, embeddings, planning figures, memory recall and past-chat search;
  - diary facts, the stream route and its client, progress labels and bold text.
- **`pnpm build`:** passed.
- **Database** (`finboy_advisor`):
  - `pnpm db:migrate` to `0016_knowledge`;
  - `pnpm db:check`: no drift;
  - `pnpm test:integration`: 116 passed (3 new), with `OPENAI_API_KEY` blank.
  - The new integration tests cover `real[]` embeddings round-tripping for recall, the guide cache
    keyed by content, model and size, and past-chat search within one household.
- **`pnpm eval:advisor --check`:** passed (42 cases). `pnpm knowledge:index` with embeddings off
  reported 33 guides, all 33 served locally.
- **Playwright** (contract double), advisor and Ask specs at 1440, 390 and 320 px: 34 passed, and
  the desktop-only voice-capture test was skipped on the two phone widths. Covered:
  - the streamed answer;
  - the guide chip linking to its official site (`target=_blank`, `rel=noopener noreferrer`);
  - a failure inside the stream with Ask again;
  - the phase 1 flows, now through the stream.
- **Browser, real API on 8101,** with `OPENAI_BASE_URL` pointing at a TEST-ONLY scripted stand-in
  for the Responses API on loopback. The stand-in returns one tool call, then a reply built from
  that tool's real output. So the real tool loop, figure check, stream and rendering ran; the
  model's wording and choices did not. At desktop width and 375 px:
  - "Looking at your spending…" before a records answer, with its figure checked against the
    engine's own output.
  - "Reading FinBoy's money guides…" before the PM-KISAN answer: ₹6,000 and ₹2,000 from the
    guide, the "From FinBoy's money guides" badge, no records warning, and the official-site chip.
  - "Working out the numbers…" before the EMI: ₹8,885 a month, ₹1,06,620 in all and ₹6,620
    interest, all from code, with no records claim.
  - With the stand-in stopped, the keyword rules answered through the stream (the degraded path).
  - With the API stopped, Ask showed "FinBoy couldn't be reached".
  - Logs carried only `advisor.answered` outcomes (`answered` or `fallback`), tool names, counts
    and latency.
- **Not verified:** a real model answer or the live gate (the local key still returns 401), real
  embeddings, WhatsApp delivery of diary facts or guide lines, and any human review of the guides.

### Human steps (phase 2)
1. Review each guide against its official sources, with a native read of the Hindi and Malayalam
   titles and terms, and fill `reviewed_on`. Until then production serves none.
2. Run a live capability check of an embedding model (for example `text-embedding-3-small` at 256
   dimensions) before setting `OPENAI_EMBEDDING_MODEL`. Then run `pnpm knowledge:index`.
3. Run the live gate with a valid key: it still fails on the 401 recorded in phase 1.

## Phase 3: the proactive coach

Built on phase 2 on the same branch (9 November 2026): migration `0017_coach`, no new dependency.
FinBoy now speaks first, only to households that ask for it: at most one short nudge a day on
WhatsApp, and a "For you" card on Home for everyone. No human decision changed. It supersedes
earlier statements only here:
- **FinBoy messages first only for dues and the monthly check-in** ([pilot](../pilot/contract.md),
  [money manager](../money-manager-round/contract.md)): opted-in households may also get coach
  nudges, as below. Everything about consent, STOP, daytime and the private allowlist still holds.
- **Diary households' WhatsApp chat holds only their questions and answers** (phase 1): a nudge
  FinBoy sent is kept as FinBoy's turn in that chat, so a reply like "how?" continues it.

### What the coach notices (`services/advisor/coach.py`)
Detectors read the same read-only engine Toolbox as the advisor's tools, so every figure is the
engine's own. Most important first:

| Kind | When | Once per |
|---|---|---|
| `weekly_recap` | Sundays, when the week had money in or out, or dues ahead | week |
| `due_soon` | a due within two days, not marked paid | due |
| `budget_over` | a monthly budget passed its limit | budget and month |
| `unusual_payment` | a payment of ₹1,000 or more in the last three days, more than three times the usual: the payee's median over six months (three or more earlier payments), else the category's over three months (five or more); never money moved to savings or between own accounts | payment |
| `income_in` | in the last three days, one salary, wages, crop, benefit or other income of at least half of last month's income (₹1,000 at least; ₹5,000 when last month shows none), so daily wages never bring a message each day | month |
| `budget_near` | a budget at 80% or more | budget and month |
| `goal_progress` | from the 20th, once income is recorded: kept so far against the monthly savings goal | month |
| `new_regular` | a payee that became regular since last month ended (`insights.regular_payments`), paid in the last week | payee |

### What it says
- **Lines written by code.** Each nudge has a line from the engine's figures in English, Hindi or
  Malayalam (`COACH` in `whatsapp/english.py`, `hindi.py`, `malayalam.py`). One sentence or two,
  without line breaks, so the same line is the web card's text, the template's parameter and every
  fallback.
- **Worded by the advisor.** Inside WhatsApp's 24-hour window the advisor model writes the nudge
  (`coach.compose`): the nudge's facts, the code-written version and the household's memories
  (when memory is on), no tools, `store=False`, one call. Every figure it writes must be in the
  facts, the code-written version or a memory (`grounding.py`); a Hindi or Malayalam nudge must be
  in its own script; at most 600 characters. Otherwise, or on any failure, the code-written
  message goes. It never names a fund, stock or other product, as everywhere else.
- **Kept in the chat.** A sent nudge (or one whose delivery is unknown) is added to the household's
  WhatsApp chat as FinBoy's message. Recent chats on the web shows it as FinBoy's, with no
  question.

### How it reaches WhatsApp (`services/whatsapp/coach.py`)
- **Opt-in only.** "Coach me" under the "this week" check-up (like the monthly check-in under
  "this month"), or the commands "coach on" / "coach off" (Hindi: "कोच चालू" / "कोच बंद",
  Malayalam: "കോച്ച് ഓൺ" / "കോച്ച് ഓഫ്"). Every nudge inside the window carries a "Stop coaching"
  button that keeps working on older nudges too. STOP stops everything, as before.
- **When.** `python -m finboy.services.pilot.cli coach` from `deploy/finboy-coach.timer`, hourly
  09:00–19:00 IST; the job itself sends only 08:00–20:00 IST.
- **At most one a day.** One per household number a day, counting the monthly check-in and due
  reminders: a number that heard from FinBoy today is skipped.
- **Never twice.** The `(number, kind, period)` and `(number, day)` rows in `advisor_nudges` are
  written before the send, so a crash or an overlapping run never repeats one. The period key is a
  keyed digest, so no payee name is stored there.
- **The window.** If the household wrote to FinBoy in the last 23½ hours, the nudge is an ordinary
  message with the "Stop coaching" button. Otherwise it is the approved `WHATSAPP_COACH_TEMPLATE`
  with the code-written line as its one parameter. Without the template, nothing goes out until the
  household writes again.
- **Consent through the send.** The binding is locked while sending, like replies and check-ins: a
  STOP or "coach off" that commits first stops the send.
- **Dues.** Pilot households that chose due reminders hear about dues from those, so the coach
  leaves dues to them.
- **Who.** Consented, enabled diary households (pilot or self-serve), at their allowlisted number
  or their own encrypted copy that still matches its hash. Never the owner's question-only number.
- **Logs.** `advisor.nudge` with the kind (`stage`), the outcome, who wrote it (`provider`:
  `advisor`, `fallback` or `template`) and the latency. The CLI prints counts only:
  `sent`, `failed`, `unknown`, `skipped` and `quiet` (nothing worth a message).

### The template (`finboy_coach_update`, category Utility, no buttons, one body parameter)
- en: "FinBoy coach: {{1}} Reply here to talk it through, or send "coach off" to stop these
  messages."
- hi: "FinBoy कोच: {{1}} बात करने के लिए यहीं जवाब दें, या ये संदेश बंद करने के लिए "कोच बंद" भेजें।"
- ml: "FinBoy കോച്ച്: {{1}} സംസാരിക്കാൻ ഇവിടെ മറുപടി അയക്കൂ, ഈ സന്ദേശങ്ങൾ നിർത്താൻ "കോച്ച് ഓഫ്" എന്ന്
  അയക്കൂ."

`{{1}}` is the code-written line, never the model's wording, so what Meta approved is what goes
out. The same bodies are in `COACH_TEMPLATE`, so the chat keeps what was sent.

### On the web
- **Home "For you"** (`GET /api/v1/coach`): the first three nudges for the current month, from the
  same detectors, read live with no model call and nothing written. Each has its line, a link to the
  place to look (Bills, Budgets, the record, Regular payments or Reports) and "Ask FinBoy", which
  opens Ask with a question typed in (`/assistant?ask=`) but never sends it. Hidden while loading,
  on an error, with nothing to say, for earlier months and while the coach is off.
- **WhatsApp.** The card says the nudges come on WhatsApp too, or offers "Get one a day on
  WhatsApp" (a `wa.me` link with "coach on" typed in), so the opt-in itself happens on WhatsApp.

### API, data and settings
- `GET /api/v1/coach` → `{items: [{kind, tone, title, text, href, ask}], whatsapp: none|off|on}`;
  404 `coach_off` while the coach is off. `GET /auth/session` reports `coach`.
- Readiness and the admin panel report `coach`: `off`, `window_only` (no template yet) or
  `configured`.
- Migration `0017_coach` (additive): `whatsapp_bindings.coach_opt_in_at`, the `coach_opt_in`
  prompt purpose, and `advisor_nudges` (binding, household, kind, keyed period, India day, message
  or template, delivery state and Meta's status). Erasure removes the rows with the household; its
  chats keep the words and go with them. The downgrade drops what it adds.

| Setting | Default |
|---|---|
| `COACH_ENABLED` | false (needs `ADVISOR_ENABLED`) |
| `WHATSAPP_COACH_TEMPLATE` | unset: inside the 24-hour window only |

### Gate
`pnpm eval:advisor` now also checks the coach:
- **Offline (`--check`).** One nudge of every kind in English, Hindi and Malayalam
  (`synthetic.nudges`). Each line must fit a template parameter, quote only its own facts (or its
  copy's fixed example) and make a message of at most 600 characters.
- **Live.** The model words each of the 24 nudges `--runs` times, with one saved memory. To pass,
  at least 90% go out in the advisor's words (the rest fall back to the code-written message). p50
  and p95 latency are printed; only kinds and languages are named.

### Verification — 9 November 2026 (phase 3, local)
- **`pnpm check`:** Ruff clean; 1,572 API unit tests passed (phase 2 had 1,523); 118 web unit tests
  passed; strict TypeScript. The new tests cover:
  - every detector and its thresholds, the order, and the lines in three languages (template-safe);
  - the advisor's wording: memory used, an invented figure, the wrong script, a long reply, a model
    or memory failure (each falls back);
  - the sender: daytime only, one a day (a check-in counts), never twice, the window or the template,
    consent locked through the send, pilot reminders keeping the dues, Meta failures, a self-serve
    number, one household's failure never stopping the others;
  - "coach on/off" in three languages and the "this week" buttons;
  - `GET /coach` with error redaction and exact CORS;
  - erasure and export, and the eval gate.
- **`pnpm build`:** passed; Ask is now in a Suspense boundary.
- **Database** (`finboy_advisor`):
  - `pnpm db:migrate` to `0017_coach`, a downgrade to `0016_knowledge` and back;
  - `pnpm db:check`: no drift;
  - `pnpm test:integration`: 120 passed (4 new), with `OPENAI_API_KEY` blank. They cover the claims
    (once per period, once a day), a check-in as the day's message, Meta statuses reaching a nudge
    only for its own number, erasure, and the whole timer job on real records with a fake Meta
    client.
- **`pnpm eval:advisor --check`:** passed (42 cases and 24 coach nudges).
- **Playwright** (contract double), the coach, advisor, Ask and Home specs at 1440, 390 and 320 px:
  58 passed and the desktop-only voice test was skipped on the two phone widths; then the coach spec
  with a failed "For you": 15 passed.
- **Browser, real API on 8101** with `COACH_ENABLED=true` and no model key, web on 3101, with
  synthetic records seeded for the local owner and removed afterwards:
  - Home's "For you" listed "Due soon", "Bigger than usual" (₹2,500 against the usual ₹400) and
    "Money in", in that order; the budget nudge came fourth and stayed hidden.
  - "Ask FinBoy" opened Ask with the question typed in, the address cleaned, and nothing sent.
  - "Open the payment" opened that record.
  - At 375 px there was no sideways scroll, with 16 px gutters and 44 px links.
  - With the API stopped, Home showed "FinBoy couldn't be reached".
- **CLI:** `coach` prints "Nudges: off" while the coach is off, and refuses without WhatsApp.
- **Found and fixed while building:**
  - Each new nudge's "Stop coaching" superseded the previous one, so stopping from an older nudge
    said "expired". Coach buttons now stay working.
  - A protocol-relative `//host` link would have passed the web's link check. It is refused now.
- **Not verified on 9 November:**
  - a real model wording a nudge, or the live gate: the key in the private secrets file still
    returned 401 that day (both ran on 10 November, below);
  - any WhatsApp delivery: there are no Meta credentials locally, and nothing was sent;
  - the template, which is not yet submitted to Meta;
  - a native read of the Hindi and Malayalam copy.

### Live gate — 10 November 2026
`pnpm eval:advisor --runs 3` with a valid key and the production model (`gpt-6-luna`, reasoning
effort low), the guides on and no embeddings:
- **First run: failed** on one fallback, though every rate passed. Spoken replies say ₹770.50 as
  "770 rupees and 50 paise", and the figure check read the 50 as an invented ₹50. So a correct
  answer was sent back for correction, and once fell back to the rules. Two Manglish replies also
  used Malayalam script.
- **Fixed:** the figure check reads "N rupees and M paise" (रुपये … पैसे, രൂപ … പൈസ) as one
  amount and still catches an invented ₹50; Hinglish and Manglish replies are told to use Latin
  letters only.
- **Second run: passed.**
  - Advisor, 126 answers: figures, policy, refusals, memory and script 100%; sources 99.2% (one
    Manglish emergency-fund answer did not cite its guide); no fallbacks; p50 5.3 s, p95 10.6 s.
  - Coach: all 72 nudges worded by the advisor (gate 90%); p50 2.0 s, p95 3.5 s.
- Still not verified: real households' questions, WhatsApp delivery of answers or nudges, real
  embeddings and the guides' review.

### Human steps (phase 3)
1. Submit `finboy_coach_update` (above) to Meta as a Utility template in English, Hindi and
   Malayalam. After approval, set `WHATSAPP_COACH_TEMPLATE`; until then nudges reach only
   households inside the 24-hour window.
2. A native read of the new Hindi and Malayalam coach copy (`COACH*` and `days` in `hindi.py` and
   `malayalam.py`) and of the template bodies.
3. ~~Run the live gate with a valid key~~: passed on 10 November (above).
4. Approve the release (`COACH_ENABLED=true` with `ADVISOR_ENABLED=true`), then install the timer
   ([production](../production.md#advisor-phase-3-the-proactive-coach)).
