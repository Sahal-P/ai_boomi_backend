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
- **Phases:** 1, the personal advisor with memory (this release); 2, a vetted knowledge library
  with sources and deeper recall (pgvector); 3, a proactive coach (opt-in nudges).

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

Periods are named (`today`, `this_week`, `last_month`, `last_n_months`…) and worked out in code.

### Memory (`services/advisor/memory.py`)

- Kinds: about, goal, plan, preference, person, note. Written in English, at most 300 characters.
- Never kept: OTPs, PINs, passwords, CVVs; long numbers and PANs are masked.
- One copy per fact; at most `ADVISOR_MEMORY_LIMIT` (80) per household, the oldest makes room.
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
| `ADVISOR_MEMORY_LIMIT` | 80 |

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
database `finboy_advisor`, migration `0015_advisor`. `ADVISOR_ENABLED` stays false until the live
gate passes and the human approves the release.

## Human steps

1. Approve this contract and, later, the release (`ADVISOR_ENABLED=true` with the web release,
   since the pricing copy lists asking under Free).
2. Before relying on the WhatsApp advisor: replace the WhatsApp user token (expires
   23 December 2026) with a permanent System User token.
3. A native read of the new Hindi and Malayalam copy (`hindi.py`, `malayalam.py`).
4. Phase 2: pgvector on the production PostgreSQL and a native review of the knowledge articles.
5. Phase 3: Meta approval of the coach template.

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
