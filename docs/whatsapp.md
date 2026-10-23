# WhatsApp ledger questions

This channel answers text and voice **questions** about FinBoy's email-derived
ledger. It calls the same assistant and speech functions as the web app. It cannot
capture payments, OCR screenshots, change transactions, recommend securities, run
broadcasts, or send unsolicited financial updates. Uncertain transactions are
reviewed in FinBoy on the demo computer; local web URLs are removed from phone replies.

## Current real setup (24 October 2026, IST)

- Existing **ai_boom Messaging Demo**, App ID **953180210789448**, **SAHAL** portfolio
  reused. No new Meta app, business phone, production registration, or billing change.
- Chrome resolved using the `sahlcyprus@gmail.com` account/stable extension identity.
  Human completed login. Previously approved test recipient retained privately.
- **Graph v26.0** confirmed in current Meta docs, OAuth dialog, and live Graph reads.
  The original token's debugger returned the correct app and WhatsApp management/
  messaging scopes, but `is_valid=false`; it expired 23 October, 09:00 UTC. Phone and
  WABA requests returned 401/code 190. App-secret authentication succeeded.
- Human completed the existing-settings token renewal. Live debugger confirms a
  valid token for this app with both WhatsApp permissions; phone and WABA reads
  return 200. Actual expiry is **24 October 2026, 03:30 IST** (23 October 22:00 UTC).
  No permanent system-user credential or wider scope was created.
- A temporary HTTPS tunnel forwards only to the restricted ingress described below.
  Before registration, public probes returned 404 for `/`, `/docs`, `/openapi.json`,
  health, money, transactions, privacy, assistant, arbitrary send, trailing-slash
  webhook, and unsupported methods. Correct verification challenge returned 200.
- Meta's actual app-subscription POST returned success; a fresh GET confirmed the
  active `whatsapp_business_account` subscription, exact callback, and `messages`
  field. The separate WABA subscription was absent; its POST returned success and
  a fresh GET confirmed this existing app. These checks do not establish delivery.
- Public synthetic signature/unknown-sender probe returned 200 without a receipt;
  tampered exact bytes returned 403. No message was sent by those probes.
- A real allowlisted text question reached the signed webhook. The frozen runtime
  correctly recorded `assistant_unavailable` and sent its truthful text fallback;
  Meta's delivery callback reached **read**. This is a real text transport result,
  not a successful ledger answer or a claim from mocks.
- Follow-up verification uses the fixed assembled commit `cbd2ed2` in the separate
  managed `finboy-whatsapp-live` worktree, still API 8014 and database finboy_p4.
  No moving integration HEAD or other agent's runtime was changed. Its actual demo
  import processed all 42 synthetic emails; actual money APIs matched the truth
  table. The explicitly specified Hotel Arya correction was applied through the
  local review API; English/Hindi/Malayalam assistant HTTP answers each returned
  the correct corrected food fact. No WhatsApp ledger mutation was introduced.
- No audio receipt or successful WhatsApp ledger/audio answer has arrived yet.
  Actual incoming media/STT and delivered synthesized MP3 remain pending.

## Private settings

Secrets reside in `~/.config/finboy/secrets.env` and ignored `apps/api/.env`, mode
600. Never print them or put them in frontend variables. Settings do not implicitly
load the private secrets file: copy required values privately into the API env.
The historical prototype's credentials were migrated privately; its old standalone
application is not used.

Required when enabling the channel:

- `WHATSAPP_ENABLED=true`
- `WHATSAPP_APP_ID` (the existing app above)
- `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_GRAPH_API_VERSION=v26.0` after the actual capability check
- `WHATSAPP_SENDER_ALLOWLIST_JSON`: a private JSON object mapping the explicitly
  approved provider sender ID (country code and digits, no plus) to `LOCAL_USER_ID`.
  No identity is guessed or paired from inbound traffic. At most 100 mappings;
  currently only the local demo UUID is permitted. Outbound addressing adds the
  leading plus to avoid country-code ambiguity.
- Existing stable `TOKEN_ENCRYPTION_KEY`: domain-separated HMAC key for sender and
  content hashes. Preserve it across Meta token refreshes and restarts. Rotating it
  without migrating bindings loses consent identity and must be planned separately.

Optional: `WHATSAPP_TIMEOUT_SECONDS` (default 15),
`WHATSAPP_MAX_WEBHOOK_BYTES` (default 262144, upper bound 1048576).
The ingress has its own stricter fixed 256 KiB limit and 15-second body deadline.
The channel stays unavailable when disabled/misconfigured; health and imports remain
usable. App ID, WABA, phone, raw sender and credentials are never logged.

For this worktree use API 8014, web 3014, disposable database `finboy_p4`, exact
localhost/127.0.0.1 CORS origins, and `DEMO_TODAY=2026-10-28`. Migration
`0003_whatsapp` is additive with `down_revision=0002_phase1`. No ledger schema changes.

## Webhook-only HTTPS ingress and restart

Run from the owned worktree with its private API env already checked:

```sh
API_PORT=8014 pnpm dev:api
uv run python -m finboy.services.whatsapp.ingress --api-port 8014 --port 8094
ngrok http 127.0.0.1:8094 --inspect=false --log=false
```

The ingress is a stateless ASGI proxy, not a second FastAPI application or persistent
service. It binds loopback, uses a fixed loopback upstream, passes only the exact
GET/POST `/api/v1/whatsapp/webhook`, denies encoded/other paths and methods, bounds
request/response size and time, rejects redirects, strips unrelated headers, and
uses the redacted application log formatter. Ngrok inspection is disabled so it
does not retain raw webhook bodies in its local inspector. **Never tunnel 8014,
8000, the web app, or the PostgreSQL port.** No arbitrary send endpoint exists.

Read the current HTTPS URL from ngrok's local management API at 127.0.0.1:4040.
The current session's URL is also in `/tmp/finboy-whatsapp-ingress-url`; do not assume
it survives a tunnel restart. Keep the app/ingress/tunnel running together for a
demo. Stopping these processes closes access; keep shared PostgreSQL running.

Before registering/replacing the callback, prove over its **public HTTPS URL**:

1. GET `/docs`, `/api/v1/health`, `/api/v1/money/summary`, `/api/v1/transactions`,
   `/api/v1/privacy/imported-data`, `/api/v1/assistant/ask`, `/api/v1/whatsapp/send`,
   and `/api/v1/whatsapp/webhook/` return 404. PATCH/DELETE/OPTIONS webhook return 404.
2. GET exact webhook with correct `hub.mode=subscribe`, private verify token, and a
   bounded numeric challenge returns only that challenge. Wrong token/mode fails.
3. Signed unknown sender is admitted as a harmless no-op; tampering fails 403.

Register only `HTTPS_BASE/api/v1/whatsapp/webhook`, the private verification token,
and `messages` field for `whatsapp_business_account`, using the existing app's
Dashboard or official app-subscriptions API. A changed temporary URL needs a new
verification. No whole-API forwarding fallback is permitted. Agent 5 consumes this
same ingress for 8015/final 8000 only after checking the assembled environment.

## Token renewal, subscriptions, and approved live tests

The human finishes Meta login, 2FA, consent, recipient verification, and billing.
Reuse previous settings when Meta offers them; do not create a new app or repeat
recipient verification if the existing approved recipient remains valid.

Renew the temporary token in the existing app's **Step 1. Try it out → Generate
token**. Copy it directly into private env files without terminal/chat output.
Restart the API because settings are loaded at startup. Using official APIs:

1. Debug token with the app credential; check `is_valid`, matching app ID, expiry,
   and `whatsapp_business_messaging`/`whatsapp_business_management` grants. Keep all
   input-token query strings out of logs. Check the actual phone/WABA assets.
2. GET `/{WABA_ID}/subscribed_apps` must include the existing app; if missing, POST
   that edge with the authorized WhatsApp token, then GET again. App callback
   registration and app-to-WABA subscription are separate requirements.
3. GET `/{APP_ID}/subscriptions` must show active `whatsapp_business_account`, the
   current restricted callback, and `messages` under the verified version.
4. The human sends a **fresh inbound** question from the approved recipient. This
   opens the 24-hour service window; the channel sends free-form replies only in
   response to a fresh question inside that window. No unsolicited template or
   financial update is sent by this implementation.
5. After Agent 1/3 integration and real ledger import, test text plus a short voice
   question in each language. English: “How much did I spend on food this month?”
   Hindi: “इस महीने खाने पर कितना खर्च हुआ?” Malayalam: “ഈ മാസം ഭക്ഷണത്തിന് എത്ര
   ചെലവായി?” Also try Hinglish/Manglish and explicit `en`, `hi`, `ml` commands.
6. Inspect **actual received replies on the human's phone**, text and playable MP3.
   Record language, text/audio result, receipt state, and delivered/read status only.
   Do not retain question text, audio, full phone IDs, or financial screenshots.
7. `STOP` disables replies durably; ordinary questions then do not reach the
   assistant. `START` re-enables only an already private-allowlisted sender.
   Unknown senders never get access or a financial response. Language defaults to
   auto detection; explicit language commands persist the preference.

Graph 200 with a message ID means accepted for processing. Delivery requires
`delivered`/`read` webhooks plus the phone inspection. `sent`, missing callbacks,
provider errors, and a historical prototype send do not establish this channel's
successful delivery. A test account does not establish public production eligibility.

## Admission, privacy, failures, and retention

GET validates mode/token with constant-time comparison, rejects duplicate params,
and echoes only a numeric 1–128-character challenge. POST caps exact raw bytes and
verifies `X-Hub-Signature-256` **before JSON parsing**. It validates object, WABA and
phone context; the app secret proves app context. Unsupported message kinds/fields
are acknowledged safely; no image/OCR pipeline is called.

Only allowlisted senders create bindings. PostgreSQL retains user UUID, keyed sender/
content hashes, inbound/outbound provider IDs, language preference, enabled flag,
fixed processing/delivery states and timestamps. It never retains raw sender/phone,
webhook JSON, question, transcript, audio, or financial answer. No file/queue/cache
stores those payloads. Transport metadata currently remains in the disposable local
DB until explicitly removed; consent must be preserved when introducing a retention
job. Imported-ledger deletion does not implicitly re-enable a stopped WhatsApp binding.
Meta/WhatsApp retain content under their own policies; uploaded Cloud API media can
persist 30 days per Meta's media documentation. Local memory-only processing does
not imply deletion of messages from the user's phone or Meta.

Admission commits before 200 and scheduling FastAPI `BackgroundTasks`. Unique inbound
IDs prevent concurrent/retried admission. Atomic `admitted → processing` claims and
unique `(receipt, delivery kind)` prevent duplicate assistant calls/sends. STOP and
send admission serialize on the binding. This is **not exactly-once delivery**.
The transport records `sending` before network I/O, then `sent` (accepted), `failed`,
or `unknown`; unknown timeouts/5xx/malformed success are never blindly retried.
A delivery callback updates only a known outbound ID for its approved hashed sender;
provider status tracks sent/failed/delivered/read separately and monotonically.
A callback arriving before its provider ID was durably recorded can be missed; an
uncertain send remains unknown and requires a fresh inbound question.

Media is resolved by authenticated Graph media ID with the expected phone ID; webhook
or user-supplied URLs are never fetched. The returned URL must be HTTPS on the exact
allowlist (`lookaside.fbsbx.com`, `mmg.whatsapp.net`), without credentials/custom port
or redirects. Both metadata and streaming bodies are bounded, MIME/size/SHA-256 are
verified, and provider reads have deadlines. Incoming audio is at most 3 MiB; shared
Agent 3 transcription bounds decoding/duration to 30 seconds. OGG/Opus, MP3, MP4,
AAC and AMR route to that service; unsupported/invalid decode gives a truthful text
fallback. Synthesized MP3 is uploaded with `audio/mpeg`, then sent by media ID. If
TTS/upload/audio send fails, the already correct text reply is preserved. No fake audio.

A restart can interrupt memory-only work. `interrupt_stale(session, before=...)`
marks admitted/processing receipts older than ten minutes `interrupted` and stale
`sending` deliveries `unknown`. It runs before new admission; Agent 5 is asked to
invoke it at startup too. It never replays payloads that were not retained. Duplicate
old provider IDs stay suppressed; the user must send a fresh request. Failure logs
contain fixed operational events only, never exception messages or message content.

## Verification

- `uv sync --locked --all-packages`, `pnpm install --frozen-lockfile`, env setup passed.
- `pnpm db:migrate`, `pnpm db:check` passed on `finboy_p4`; no schema drift.
- WhatsApp unit/HTTP and local PostgreSQL tests cover signatures/tampering, challenge
  failures, context, body limits, unknown senders, language routing/commands, status
  events, duplicate/concurrent admission, actual concurrent HTTP→DB→shared-service
  fakes, atomic claims, schema constraints, restart interruption, provider auth/quota,
  expired/oversize/bad-MIME/redirected media, STT/TTS failure, send uncertainty, no
  retry, phone-safe review guidance and log redaction. Fakes never establish live TTS.
- `pnpm check` and `pnpm build` passed. Full `pnpm test:integration` is limited by
  inherited database-name guards, the old exact `0002_phase1` assertion, and one
  transient connection timeout; owned PostgreSQL tests pass. Shared requests are
  recorded in `docs/handoffs/agent-4-dependencies.md` for Agent 5.
- No Next.js changes or UI screen is owned by this channel; viewport/microphone UI
  QA belongs to Agent 2/3/5. No phone-delivery screenshot is claimed or fabricated.

## Official references inspected

Meta pages were read in Chrome on 24 October because the search fetcher returned 429:

- [Webhook endpoint and signature verification](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint)
- [Media APIs, expiry, MIME/codec limits](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media)
- [Getting started, tokens and service window](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started/)
- [Service messages and delivery status](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/send-messages)
- [App subscriptions API](https://developers.facebook.com/docs/graph-api/reference/app/subscriptions/)
- [Meta's WABA subscription API example](https://www.postman.com/meta/whatsapp-business-platform/request/26gui66/subscribe-to-a-waba)

## Post-handoff integration observations

The assembled service adds a fixed `InvalidAudio(ValueError)` input exception.
The channel's original frozen placeholder only raised ProviderUnavailable. Agent 5
is asked in the dependency handoff to catch the integrated InvalidAudio boundary for
both STT and TTS; otherwise invalid audio takes the generic interrupted-work failure
path without its helpful text fallback. This does not affect the verified text
round trip. No Agent 5 source was edited after ownership handoff.
