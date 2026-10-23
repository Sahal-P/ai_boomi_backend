# Prompt 3 — A3: Malayalam voice money assistant (full stack)

You are **A3** on FinBoy Phase 1, working in parallel with three other agents. You own
the hero moment: the user asks in Malayalam, Manglish, or English and hears a correct
Malayalam answer whose numbers come from code, not the model. This request authorizes
Phase 1 work defined in `docs/phase1/contract.md`.

**Read first:** `AGENTS.md`, `docs/phase1/contract.md` (§6 money engine interface, §8
demo lines), `README.md`, `apps/web/AGENTS.md` (read the bundled Next.js docs before
writing Next.js code). Do not delegate to subagents.

**Workspace:** branch `phase1/a3-voice` in your own git worktree. API 8003, web 3003,
database `finboy_a3` (contract §3). You only write files A3 owns (contract §4). A4's
money engine is a stub on your branch: call it exactly per contract §6 and use fakes
built from the §8 truth table in your tests. Never compute money yourself.

## Browser / setup tasks (Chrome + gcloud; human does logins and permission prompts)

1. Copy `OPENAI_API_KEY` and `GOOGLE_CLOUD_PROJECT` from `~/.config/finboy/secrets.env`.
2. In Chrome, read OpenAI's official docs and choose current models for transcription
   (multilingual, Malayalam) and for intent parsing / answer wording. Set
   `OPENAI_TRANSCRIBE_MODEL` and `OPENAI_ASSISTANT_MODEL`; record choices and links in
   `docs/voice.md`.
3. `gcloud services enable texttospeech.googleapis.com`; set up Application Default
   Credentials (`gcloud auth application-default login`, then set the quota project).
   List `ml-IN` and `en-IN` voices, compare 2–3 Malayalam voices on a sample sentence
   with numbers, and pick one (record why in `docs/voice.md`). If ADC is blocked, use an
   API key restricted to the Text-to-Speech API, sent in the `X-Goog-Api-Key` header.
4. In Chrome, verify microphone capture on `/assistant` (the human clicks Allow).

## Build — backend

1. **Transcribe** `POST /assistant/transcribe`: multipart audio (webm/ogg/mp4/wav/mpeg,
   ≤ 3 MB, ≤ 30 s), a vocabulary prompt (SIP, UPI, EMI, salary, Swiggy, Zomato, Amazon),
   returns `{transcript, detected_language}`. Audio and transcripts are never stored or logged.
2. **Understand:** detect style (`ml` script, `manglish`, `en`, `mixed`), then parse a
   structured intent with OpenAI Structured Outputs: `spending_query`, `income_query`,
   `unallocated_query`, `upcoming_commitments`, `affordability_check`,
   `savings_simulation`, `merchant_lookup`, `education`, `regulated_advice`,
   `out_of_scope` + slots (category from the closed list, period, amount_minor,
   merchant, topic). Add deterministic fallback rules for the §8 demo lines so the demo
   works offline. All four phrasings of a question must yield the **same** intent.
3. **Policy router:** bookkeeping, education, and cash-flow simulation → answer.
   Requests for a specific fund/stock/portfolio → polite decline, then offer the
   simulation and neutral education (SIP, index funds, diversification). No security names.
4. **Calculate:** call only the A4 engine (`money_summary`, `category_breakdown`,
   `upcoming_commitments`, `find_transactions`, `simulate_monthly_commitment`).
5. **Compose:** deterministic templates per intent × style (Malayalam script, Manglish,
   English) filled from engine numbers. Optional LLM polish only behind a **numeric
   guard**: every number in the output must match an engine fact, otherwise use the
   template. `display_text` follows the user's style; `speech_text` is native
   Malayalam script for ml/manglish (e.g. "ഈ മാസം ഭക്ഷണത്തിന് 7,860 രൂപ ചെലവായി."),
   with ₹ rewritten as "രൂപ" and Indian digit grouping. Always mention pending review
   items and use "estimated unallocated", never "balance".
6. **Speak** `POST /assistant/speak`: Google TTS `ml-IN` / `en-IN`, MP3, ≤ 600 chars,
   no disk caching of user audio.
7. **`POST /assistant/ask`** returns the contract §7 shape including `facts`,
   `simulation`, evidence transactions, warnings, and the disclaimer for simulations.
8. **Benchmark** `pnpm voice:benchmark`: ≥ 12 questions (all §8 lines plus variants:
   Swiggy spend, upcoming bills, "what is SIP", out-of-scope). Generate repeatable
   audio with TTS into `apps/api/fixtures/voice/`, then run STT → intent and report
   transcript and intent accuracy. Ask the human to record 5 real questions into a
   gitignored folder and include them in the run. Never commit real voice recordings.

## Build — frontend `/assistant` (data in `lib/api/assistant.ts` + hooks)

- Large mic button (tap to start/stop) with states: idle, recording, transcribing,
  thinking, speaking, error. Handle a denied microphone permission gracefully.
- Editable transcript before sending, a text-input fallback, and suggestion chips with
  the §8 lines.
- Answer card: display text, audio playback with replay, display-style toggle
  (Malayalam / Manglish / English), "How was this calculated?" lines plus evidence
  transactions, and a simulation table like the report's (income, outflows,
  commitments, proposed SIP, remaining) with the "2 transactions awaiting confirmation"
  warning and the disclaimer.
- Accessible: `aria-live` status, keyboard operable, visible focus, works at 390 px width.

## Design system

The UI is a light, 3D, premium system (docs/design-system.md, live at `/styleguide` in
dev). Build your screens from its tokens, `components/ui` primitives, motion primitives
and `<SceneSlot>` scenes; do not add colours, shadows, fonts, animation libraries or WebGL
canvases of your own. The app shell, landing page and primitives belong to D.
Use the `voice-orb` scene for /assistant: pass `state` (idle/listening/thinking/speaking) and a `level` ref fed from the mic/TTS analyser.

## Done when

- Against fakes: each §8 line gives the right intent and policy, and the correct
  numbers (food ₹7,860, unallocated ₹14,780, SIP remaining ₹9,780); "which fund" is
  declined; Malayalam audio plays in Chrome.
- Tests: intent equivalence across styles, policy cases, numeric guard (including a
  hallucinated-number case), templates, Malayalam number normalization, mocked
  STT/TTS clients, upload validation, nothing sensitive in logs.
- Benchmark results recorded in `docs/voice.md` (STT quality per style, intent
  accuracy, latency).
- `/assistant` checked at 1440×1000 and 390×844 (including permission denied and API
  offline). `pnpm check` and `pnpm build` pass.

**Final report:** commands + real outcomes, models and voice chosen, benchmark table,
cross-boundary edits, new dependencies, known gaps.
