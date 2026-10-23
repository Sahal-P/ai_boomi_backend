# Phase 1 completion round — frozen parallel contract

This document supersedes the conflicting scope, provider, language, runtime, and
ownership sections of the original Phase 1 prompts. The human authorized this round
on 24 October 2026. All other privacy, architecture, money, ingestion, and delivery
rules in `contract.md` remain binding. No subagents or additional chats are created.

## Frozen baseline and handoff

Agent 5 merges the full completed A1 `03695b6` and A2 `45ec529` implementations into
`feat/finboy-integration`. The immutable local branch `feat/finboy-ready-base` points
to the bootstrap commit. Resolve it with `git rev-parse feat/finboy-ready-base`.
`docs/handoffs/agent-5.md` on the integration branch records the resolved SHA in a
subsequent commit; the frozen ref will never be amended or advanced for this round.
Agents 1–4 inspect before publication and edit only after that ref exists. Create
managed worktrees from that ref, then the branch below. Do not follow moving HEAD.
Agent 5 does not merge into main, push, deploy, or publish any provider app.

| Owner | Branch | API | Web | Disposable database |
| --- | --- | --- | --- | --- |
| Agent 1 money API | feat/finboy-money-api | 8011 | 3011 | finboy_p1 |
| Agent 2 product UI | feat/finboy-product-ui | 8012 | 3012 | finboy_p2 |
| Agent 3 multilingual voice | feat/finboy-multilingual-voice | 8013 | 3013 | finboy_p3 |
| Agent 4 WhatsApp | feat/finboy-whatsapp | 8014 | 3014 | finboy_p4 |
| Agent 5 integration | feat/finboy-integration | 8015 | 3015 | finboy_p5 |

All listeners bind loopback. Use exact worktree CORS origins for localhost and
127.0.0.1, WEB_APP_URL at 127.0.0.1, and the matching NEXT_PUBLIC_API_URL.
Keep the shared PostgreSQL container and volume running; never db:down/Compose down.
Final 8000/3000/finboy checks happen only after assembled-branch environment review.
Gmail registered callbacks remain 8000/8002. Do not invent an 8015 callback; use a
registered callback for live checks or obtain explicit review for an additional URI.

## Exclusive ownership after bootstrap

All backend paths below are under `apps/api/src/finboy` unless qualified.

| Owner | Exclusive files |
| --- | --- |
| Agent 1 | services/money/**; services/ledger/** when necessary; api/v1/money.py; api/v1/transactions.py; apps/api/tests/money/**; docs/money.md |
| Agent 2 | apps/web/src/** except lib/api/http.ts and lib/api/health.ts; apps/web/public/**; apps/web/scripts/**; apps/web/package.json; pnpm-lock.yaml; docs/design-system.md; docs/product-ui.md |
| Agent 3 | services/assistant/**; services/speech/**; api/v1/assistant.py; apps/api/tests/assistant/**; apps/api/tests/speech/**; apps/api/fixtures/voice/**; docs/voice.md |
| Agent 4 | services/whatsapp/**; api/v1/whatsapp.py; db/models/whatsapp.py; apps/api/alembic/versions/0003_whatsapp*.py; apps/api/tests/whatsapp/**; docs/whatsapp.md |
| Agent 5 | main.py; core/**; api/router.py; db/base.py; db/session.py; db/models/__init__.py; apps/api/alembic/env.py; root package.json; both Python pyproject files; uv.lock; shared web http.ts/health.ts; services/mail/**; services/imports/**; services/privacy/**; apps/api/tests/mail/**; apps/api/tests/system/**; apps/web/e2e/**; integration documentation; README/AGENTS/contract updates |

Do not concurrently edit another owner's files. Agent 5 takes final integration edit
ownership only after that owner hands off. Shared changes are narrow commits that
owners explicitly consume. Record Python dependency requests in
`docs/handoffs/agent-N-dependencies.md`; Agent 5 alone edits/relocks Python dependencies.
Agent 2 alone edits npm dependencies/lock while parallel. Record schema proposals
before implementation. Keep the current ledger schema unless a concrete need is reviewed.

The design worktree `/Users/sahal/Dev/FourNotFour/ai_boom-design-3d` contains valuable
UNCOMMITTED source at scaffold HEAD. Agent 2 imports a reviewed snapshot, preserving
A2 routes and newer API helpers. Nobody resets, cleans, stashes, or commits another
active worktree. Do not claim the design is integrated based on its branch HEAD.
The pre-existing `.gitignore` edit in the original A2 worktree is left untouched.

## Product scope and provider routing

English, Hindi, and Malayalam text/voice questions share the existing email-derived
ledger and deterministic money engine. No product login. LLMs understand; code
calculates; users approve uncertainty. No fund/stock picks, payment screenshots,
OCR, WhatsApp expense capture, or WhatsApp ledger mutations.

- Language = `en | hi | ml`; DisplayStyle = `auto | en | hi | hinglish | ml | manglish`.
  Shared aliases live in `core/languages.py`.
- English/Hindi TTS: Resemble Ultra (later explicit human choice supersedes Chatterbox); human account setup in the
  hello404lab Chrome profile. Verify actual API entitlement, model, voice, codec,
  and a small synthetic sample using official docs. No cloning/training.
- Malayalam TTS: an actually available Gemini TTS model/voice; verify a synthetic
  sample. Never assume an archived model or advertised locale is available.
- OpenAI transcription remains backend only with configured verified model.
- Missing credentials/access/worker yields explicit unavailable or text-only UI;
  never fake audio, successful provider results, or financial answers.
- WhatsApp uses existing Meta app ai_boom Messaging Demo (ID 953180210789448),
  SAHAL business portfolio; human setup in the sahlcyprus Chrome profile. Scope is
  TEXT and VOICE QUESTIONS only. No arbitrary send HTTP endpoint.

Browser profiles must be resolved by account/stable identity, never saved numeric
IDs after restart. Human performs login, consent, 2FA, CAPTCHA, mic permission, and
billing. Prior completed consent need not be repeated unless the grant was revoked
or materially different access is required. Gmail grant was deliberately revoked
following A2's live fetch/revoke check; reconnect before live demo.

## Frozen interfaces

Keep contract §6 money models/function signatures, integer paise/INR, IST clock,
InboundMessage/IngestionStats/ingest_messages, and Gmail/import/privacy HTTP unchanged.
`GET /transactions` returns an ARRAY of existing TransactionView. Detail returns
`{transaction, sources, confidence_factors, revisions}`; Agent 1 supplies typed examples.

Agent 3 owns these typed boundaries after bootstrap (initial implementations raise
fixed ProviderUnavailable errors; there is no successful placeholder behavior):

```python
# services/assistant/service.py; models exported from services/assistant/models.py
answer_question(session, *, user_id, text, display_style, settings) -> AssistantAnswer
# services/speech/service.py; models exported from services/speech/models.py
transcribe_audio(*, audio: bytes, content_type: str, settings, language_hint=None) -> Transcript
synthesize_speech(*, text: str, language: Language, settings) -> SynthesizedAudio
```

Transcript: transcript, detected_language = en|hi|ml|unknown.
SynthesizedAudio: data bytes (excluded from repr), media_type audio/mpeg.
AssistantAnswer fields: intent string; policy answer|decline|clarify; display_text;
speech_text; speech_language; facts; simulation; evidence_transactions; warnings.
Each fact is `{key: string, amount_minor: integer|null, count: integer|null,
currency: INR|null}`. simulation is existing CashFlowSimulation|null;
evidence_transactions are existing TransactionView; warnings is a list of strings.

`POST /api/v1/assistant/ask` takes `{text, display_style}` and returns AssistantAnswer.
Transcribe accepts bounded in-memory multipart audio ≤3 MB and ≤30 seconds, with
optional language_hint. Speak takes `{text, language}` with ≤600 characters and
returns actual MP3 bytes / audio/mpeg. Web and WhatsApp call these exact APIs/services;
no duplicated assistant reasoning, arithmetic, or provider clients.

## Shared settings reserved in bootstrap

Keys are optional SecretStr; absent settings must allow health/import/offline use.
RESEMBLE_API_KEY, RESEMBLE_PROJECT_UUID, RESEMBLE_VOICE_UUID_EN,
RESEMBLE_VOICE_UUID_HI, RESEMBLE_TTS_MODEL, GEMINI_API_KEY, GEMINI_TTS_MODEL,
GEMINI_TTS_VOICE. No model/voice defaults are invented.
ASSISTANT_TIMEOUT_SECONDS and SPEECH_TIMEOUT_SECONDS default 30 (1–60);
PROVIDER_MAX_RETRIES defaults 1 (0–3); FFMPEG_BINARY defaults ffmpeg.
SPEECH_MAX_AUDIO_BYTES ≤3145728, SPEECH_MAX_DURATION_SECONDS ≤30,
SPEECH_MAX_TEXT_CHARACTERS ≤600. Agent 3 reports additional shared needs early. RESEMBLE_TTS_BASE_URL defaults to
https://f.cluster.resemble.ai; GEMINI_TTS_BASE_URL defaults to
https://generativelanguage.googleapis.com/v1beta. Both require HTTPS without
credentials/query/fragment. FFPROBE_BINARY defaults ffprobe. No new Python dependency
is needed for Agent 3 at bootstrap; httpx/OpenAI/stdlib and system ffmpeg are available.

WHATSAPP_ENABLED defaults false. WHATSAPP_APP_ID, WHATSAPP_APP_SECRET,
WHATSAPP_VERIFY_TOKEN, WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
WHATSAPP_BUSINESS_ACCOUNT_ID, WHATSAPP_GRAPH_API_VERSION,
WHATSAPP_SENDER_ALLOWLIST_JSON (private JSON approved provider sender ID → local user
UUID) are reserved. Secret values/identifiers are never returned or logged.
WHATSAPP_TIMEOUT_SECONDS defaults 15 (1–60); MAX_WEBHOOK_BYTES 262144 (≤1048576);
INGRESS_PORT 8095. Prefix the latter fields with WHATSAPP_. Agent 4 owns parsing and
authorizing the private allowlist; unknown sender never maps automatically to Arun.
All example credential/model/voice values are blank. Preserve existing secrets.

## WhatsApp exposure and persistence

Product routes stay localhost-only. A separate path-filtering ingress exposes ONLY
GET/POST `/api/v1/whatsapp/webhook` through any tunnel. It must deny /docs, health,
privacy, transactions, money, other methods/paths, and arbitrary send routes. Keep
one FastAPI app and PostgreSQL as the only persistent service; a small stateless
loopback proxy may forward only the webhook. Agent 5 prepares/verifies it with
Agent 4's implementation. No public tunnel until approved recipient/config exists.

`db/models/whatsapp.py` is registered during bootstrap and intentionally defines no
tables; empty router is registered and exposes no routes. Agent 4 adds reviewed
minimal binding/receipt/delivery metadata plus additive 0003_whatsapp migration.
Store user ID, hashes, provider IDs, language, enabled flag, timestamps, fixed states.
Never persist raw webhook bodies, phone numbers, questions, transcripts/audio,
or financial answers. Duplicates must not produce duplicate answers. Verify webhook
signature and sender authorization before reaching ledger/assistant services.

## Acceptance and integration

Agent 5 merges Agent 1, Agent 3, Agent 4, then Agent 2 after their handoffs. Each
handoff `docs/handoffs/agent-N.md` records branch/head, owned changes, exact commands
and results, real vs mocked checks, settings/dependencies/schema, screenshots/gaps.
Do independent QA while owners work. Do not seed final totals directly into DB.

Use the 42-message actual demo mailbox and offline recordings through imports/demo
and imports/eml; verify counters, re-import idempotency, three-source Amazon ₹799,
Hotel Arya travel→food correction, review exclusions/actions, failure recovery,
source-aware privacy deletion with audit preserved. Expected salary ₹62,000, net
outflows ₹37,420, upcoming ₹9,800, estimated unallocated ₹14,780; ₹5,000 proposal
leaves ₹9,780. Food ₹6,610 before correction / ₹7,860 after. Simulations end with:
“This models cash flow from FinBoy's tracked records. It is not a recommendation
to purchase any security.” Actual bank balances may differ from tracked records.

Run pnpm check, build, db:migrate, db:check, test:integration, eval:extraction (offline),
voice:benchmark. Browser: 1440×1000, 390×844, 320×740; loading/empty/error/offline,
keyboard/mic denied/no-WebGL. Actual Resemble Ultra English/Hindi, Gemini Malayalam MP3,
and approved-phone received WhatsApp text/voice reply are required live criteria.
Graph HTTP 200 and mocked tests alone do not establish delivery/provider success.
No mass rerecording or costly live evaluation without necessity. Commit synthetic
fixtures only. Final report distinguishes every incomplete live criterion.


## Later provider decision recorded at integration

Agent 3's final handoff records explicit human approval: “Use Resemble Ultra credit
no replicate is needed.” This supersedes the initial Chatterbox requirement; no
Replicate subscription/token/adapter is needed. Verified voices: Lucy en-US
`fb2d2858`, Fatima Hindi `af3b3fad`; model `resemble-ultra`. Verified Malayalam:
Gemini `gemini-3.8-flash-tts` / Kore. These are handoff live checks; integration will
verify shared-service responses and actual browser/phone acceptance separately.
