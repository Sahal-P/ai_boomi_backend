# WhatsApp ledger questions

This channel answers text and voice **questions** about FinBoy's email-derived
ledger. It calls the same assistant and speech functions as the web app. Since the
capture round it also accepts UPI/payment screenshots, which can only create records
waiting for review (see the screenshot section below). It cannot confirm or change
transactions, recommend securities, run broadcasts, or send unsolicited financial
updates. Uncertain transactions are reviewed in FinBoy on the demo computer; local web
URLs are removed from phone replies.

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
- Follow-up verification uses fixed assembled commit `cbd2ed2` plus Agent 5's narrow
  `b651d69` audio-error fix (local verifier head `249a1e8`) in the separate
  managed `finboy-whatsapp-live` worktree, still API 8014 and database finboy_p4.
  No moving integration HEAD or other agent's runtime was changed. Its actual demo
  import processed all 42 synthetic emails; actual money APIs matched the truth
  table. The explicitly specified Hotel Arya correction was applied through the
  local review API; English/Hindi/Malayalam assistant HTTP answers each returned
  the correct corrected food fact. No WhatsApp ledger mutation was introduced.
- Latest read-only metadata confirms a second real inbound text completed on the
  assembled shared-assistant runtime, language `en`, no error. Its text reply reached
  **read**. Together with the earlier fallback, two text deliveries are READ. Question
  and answer contents were not retained or printed.
- There is still **no audio receipt or audio delivery**. The human explicitly deferred
  voice acceptance. Actual incoming media/STT and delivered/playable synthesized MP3
  remain unverified; an ambiguous combined text/voice confirmation is not audio proof.

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
  approved provider sender ID (country code and digits, no plus) to `LOCAL_USER_ID`
  or, for the village pilot, to an enrolled pilot household's UUID (at most 10 pilot
  households; see [the pilot contract](pilot/contract.md)). No identity is guessed or
  paired from inbound traffic. At most 100 mappings. Messages from a mapping whose
  household does not exist or is not `LOCAL_USER_ID`/`pilot = true` are ignored.
  Outbound addressing adds the leading plus to avoid country-code ambiguity.
- Existing stable `TOKEN_ENCRYPTION_KEY`: domain-separated HMAC key for sender and
  content hashes. Preserve it across Meta token refreshes and restarts. Rotating it
  without migrating bindings loses consent identity and must be planned separately.

Optional: `WHATSAPP_TIMEOUT_SECONDS` (default 15),
`WHATSAPP_MAX_WEBHOOK_BYTES` (default 262144, upper bound 1048576),
`WHATSAPP_REMINDER_TEMPLATE` (the approved pilot reminder template's name, lowercase
letters, digits and underscores; blank means reminders follow replies instead).
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
   ചെലവായി?” Also try Hinglish/Manglish and explicit `en`, `hindi`, `ml` commands.
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
are acknowledged safely. Image messages go only to the screenshot capture flow below;
captions and webhook-supplied URLs are ignored.

Only allowlisted senders create bindings, except unknown numbers while self-serve sign-up is on
(see [self-serve households](#self-serve-households-27-october-2026)). PostgreSQL retains user UUID, keyed sender/
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
Agent 5 fixed its STT/TTS text-fallback handling in narrow commit `b651d69`. That
explicit shared fix was consumed only in the temporary live verifier (`249a1e8`),
without changing the original frozen-base source branch. Focused processor tests
22/22 and assembled `pnpm check` (365 backend unit tests, 10 web tests, strict TS)
pass. No Agent 5 checkout/runtime/source was edited after ownership handoff.

## Human decision — voice verification deferred

On 24 October 2026 the human explicitly selected **Keep the voice check pending**.
Do not wait for or request another voice recording in this round. WhatsApp incoming
audio, STT/TTS response and actual phone audio playback remain unverified. The real
text fallback round trip remains verified through Meta READ status; actual local
ledger/assistant answers in en/hi/ml passed in the isolated assembled verifier.
Existing approved ingress/runtime/ports are left intact for integration coordination;
no further live voice message was sent or synthesized by this deferred check. Resume
the human phone voice acceptance only when the human requests it.

## Feature status — 24 October 2026

Recorded from code and the evidence above, before the capture round changes anything.

| Capability | Status |
| --- | --- |
| Text questions | Implemented. One allowlisted test number reached Meta READ through the local restricted ingress and tunnel. Production WhatsApp is disabled. |
| Voice notes | Implemented in code: Graph media download, shared transcription, shared assistant, text reply, then an MP3 reply. Never verified on a real phone; the human deferred voice acceptance. |
| Live voice calls | Not implemented. The channel is message-based questions and answers. |
| UPI/payment screenshots | Not implemented. The webhook acknowledges and ignores image messages; this was a documented non-goal. |
| Speech-to-text provider | OpenAI `gpt-transcribe`, shared with the web microphone. No Groq integration. |

The capture round (`docs/capture-round/contract.md`) adds Groq transcription for
English/Hindi and screenshot capture into the review queue. Its outcomes are recorded
in that document, not assumed here.

## Screenshot capture (capture round)

An allowlisted, enabled sender inside the 24-hour window may send a JPEG/PNG payment
screenshot. The webhook admits it as an `image` receipt; only the Graph media ID and MIME
are read. The processor downloads it through the same bounded Graph media path (5 MiB,
host allowlist, MIME/size/SHA-256 checks), validates and re-encodes it through
ffprobe/ffmpeg pipes, and asks OpenAI vision (`OPENAI_VISION_MODEL`, `store=false`) for a
verbatim transcript plus proposed payment fields.

Code accepts a proposed field only when it appears in the transcript, refuses pending,
failed, requested or reversed screens, and writes one line such as
`Rs. 500.00 paid to Ravi Kumar via UPI on 24-10-26 10:42, UPI Ref: 612345678901`. That
line runs through the `.eml` import pipeline as source/mode `whatsapp_image`, so the UPI
reference is pseudonymized before storage. A screenshot-only record cannot exceed 0.706
confidence and always waits for review; a matching bank alert merges with it by reference.

Replies (en/hi/ml): saved for review with amount and payee, already in FinBoy, no
completed payment found, busy importing, unreadable image, or capture unavailable.
Receipt error codes: `invalid_image`, `capture_busy`, `capture_unavailable`. Captions,
images, transcripts and proposed fields are never stored or logged. Capture is
unavailable when `OPENAI_VISION_MODEL` is unset or extraction runs offline/rules-only.

Not verified live: no real Meta image webhook, no live OpenAI vision call, and no phone
reply. Production WhatsApp stays disabled.

## Subsequent production activation

The human explicitly enabled production on 24 October 2026. This supersedes the
disabled status above: the existing private allowlist is active, Meta's verified
callback points to `finboy-api.antlegs.in`, and actual production text replies have
reached `read`. See [production activation](production.md#whatsapp-production-activated--24-october-2026)
for the verified token expiry, configuration and operational checks.

The screenshot reader's real OpenAI synthetic-image capability check passed with
`gpt-6-luna`; screenshot-only records remain review-only. Real phone image capture and
voice playback are still unverified, and the prior voice deferral remains in effect.

## Village pilot households (26 October 2026)

The human approved a Hindi, WhatsApp-first village pilot; [the pilot contract](pilot/contract.md)
is binding and supersedes this document only as written there. Everything below applies only
to households with `users.pilot = true`. The owner's household keeps the question flow above
unless the owner switches the dogfood flag on (`pilot.cli owner on`).

- A consent card (text and voice) gates every pilot household, in English unless the first
  message shows Hindi or Malayalam ("Reply language" below); बंद/शुरू work like STOP/START.
- Voice or text statements ("दूधवाले को 500 दिए") become one `whatsapp_voice` line through the
  import pipeline, always into review. FinBoy replies with a confirm card and reply buttons
  (हाँ, रकम बदलें, नहीं) plus a Hindi voice readback. Taps go through the versioned review
  decisions with undo. Screenshots use the same card.
- Spoken dues, the paid and next-month flows, opt-in reminders (an approved template, or a card
  after the next reply) and the "हिसाब" weekly summary are described in the contract.
- New receipt kind `button`; new delivery kinds `interactive` (a reply with buttons) and
  `reminder` (a due card after the reply), each at most once per inbound message. Template
  reminder statuses update `whatsapp_reminders` only for the matching household's number.
- Prompts keep only IDs, a keyed fingerprint, state and expiry. No message text, transcript,
  audio or image is stored, as before.

## Self-serve households (27 October 2026)

[The sign-up contract](signup-round/contract.md) is binding and supersedes this document only as
written there. Everything below applies only while `SIGNUP_ENABLED` is on, plus to households
that joined while it was.

- **Admission:** a message from an unknown number creates a household that has not agreed yet
  and its binding: the sender HMAC as before, plus a Fernet-encrypted copy of the number. At
  most 200 such households exist at once (newer numbers are ignored), and any that never agree
  are removed after 7 days. When `SIGNUP_LIMIT` households have agreed, FinBoy says it is full;
  JOIN keeps a place in `signup_waitlist` (encrypted number) and removes the new household.
- **Language:** replies follow each message ("Reply language" below). `english.py` mirrors `hindi.py` name for name, and English amounts
  ("five hundred", "2.5k", "1,250") are read like Hindi ones. STOP/START and बंद/शुरू both work.
- **Consent:** the self-serve consent card gates everything; No erases the new household.
- **Login codes:** "FinBoy login code XXXX-XXXX" from a self-serve, owner or new number gets a
  card naming the browser that asked; ✅ confirms the waiting web login, ❌ declines it. Pilot
  households are told the web isn't part of the pilot. Codes are stored only as HMACs.
- **Diary:** the pilot flows above (records, confirm cards with undo, dues, हिसाब/summary).
  Reminders stay pilot-only, so self-serve households are not offered them.
- **Daily limits:** each text or voice message from an agreed self-serve household counts
  toward `DAILY_AI_LIMIT` or `DAILY_VOICE_LIMIT`; over the limit FinBoy replies "try again
  tomorrow". Button taps never count.
- New receipt error codes: `signup_full`, `login_expired`, `usage_limit`,
  `web_not_available`. Nothing new is stored about messages: no text, audio, image, transcript
  or login code.

## Malayalam households (28 October 2026)

[The Malayalam voice contract](malayalam-round/contract.md) applies.

- **Language:**
  - a text in Malayalam script, or in Manglish, is answered in Malayalam ("Reply language"
    below);
  - `ml`, `malayalam` or `മലയാളം` chooses it at any time. Before agreeing, a choice brings the
    consent card in that language; afterwards, a short "chosen" note.
  - The owner's question flow keeps its own language replies.
- **Copy:** `malayalam.py` mirrors `english.py` and `hindi.py` name for name (a test checks
  this). It covers consent, cards, buttons of at most 20 characters, dues, the "കണക്ക്" week
  summary, and the sign-in, sign-up and link cards. നിർത്തുക/നിർത്തൂ and തുടങ്ങുക/തുടങ്ങൂ work
  like STOP/START.
- **Voice:**
  - voice notes get a language hint only after a choice; otherwise speech-to-text detects
    the language (Sarvam when `SPEECH_TRANSCRIBE_PROVIDER=sarvam`);
  - spoken replies use Bulbul when `MALAYALAM_TTS_PROVIDER=sarvam`;
  - amounts arrive as digits; a Malayalam number typed as words gets "എത്ര രൂപ?".
- **Unchanged:** buttons, undo, daily limits, the pilot's Hindi reminder template and the
  no-storage rules. WhatsApp never merges or deletes.

## Reply language (29 October 2026)

The human asked for English by default, replies in each person's own language, and a way to choose.
This supersedes the language rules in the sections above (`services/whatsapp/language.py`).

- **Someone new gets English.** Nothing is assumed from a voice note or photo: the consent card goes
  out before anything is transcribed. Village pilot households start in English too (the human's
  choice).
- **Each message decides:**
  - typed text, by its script or its Hinglish/Manglish words. This is the web assistant's "Match my
    question" detector, which now also knows everyday money words such as diye, kharcha, koduthu and
    kitti;
  - a voice note, by what speech-to-text heard.
- **No language in the message:** a greeting ("Hi", "Hi FinBoy"), a single word like "ok", digits,
  emoji, a button tap, a photo, STOP/START or FinBoy's prefilled login line. These get the language
  FinBoy last used with that person (`whatsapp_bindings.last_language`).
- **A choice sticks** until the person picks another:
  - `en` or `english`;
  - `hindi`, `हिंदी` or `हिन्दी`;
  - `ml`, `malayalam` or `മലയാളം`.

  A bare `hi` is a greeting, not Hindi. Voice notes get a language hint only after a choice. The
  consent cards name the words ("हिंदी: hindi · മലയാളം: ml").
- **Questions** in the diary are answered in the question's own language unless one was chosen.
- **Migration `0010_whatsapp_last_language`** cleared the languages stored earlier. They came from
  code defaults (Hindi for diary households) or from "hi" greetings, not from choices.

## Money manager (29 October 2026)

Diary households' money is saved at once, and FinBoy asks first only when it is unsure (₹50,000 or
more, a possible duplicate, or a typed entry matching a screenshot, bill, SMS or email record). The
[money manager contract](money-manager-round/contract.md) has the full behaviour. In short:
- several items per message, photos of bills and pasted bank SMS (numbers masked before the model);
- saved cards with Undo (then Put it back), Amount and Category; Category is a WhatsApp list
  message (`interactive.list_reply`, the same `fb1:<prompt>:<choice>` IDs) and typing a category
  works too;
- the category chosen for a payee is remembered for its next entries;
- "today", "this week" and "this month" are calculated replies, with budgets ("food budget 5000")
  and a savings goal ("save 5000 a month");
- an opt-in monthly check-in template (`WHATSAPP_CHECKIN_TEMPLATE`), sent by
  `finboy.services.pilot.cli checkin` from `deploy/finboy-checkin.timer`.

**Self-serve replies.** Until this round the Meta client refused every number outside the private
allowlist, so self-serve households got no reply. `send_reply` now vouches for a number only after
matching it to its own self-serve binding, and only for that message's client.

## Fast decisions (30 October 2026)

With `TRIAGE_ENABLED`, Liquid AI's d1-ultra sorts each diary message and photo while the OpenAI call
runs ([contract](triage-round/contract.md)). When it is sure:
- one payment with no payee named ("chai 20", "salary 30000 aayi"), a budget or a savings goal is
  read by code, with d1-ultra's category, and saved as before;
- a check-up in other words ("aaj ka kharcha batao", "is hafte ka hisaab dikhao") gets the today,
  week or month check-up;
- a greeting gets the "not sure" reply;
- a photo that is neither a payment screen nor a bill gets the existing "send a payment screenshot
  or a bill photo" reply without a vision read.

A named payee, several items, a pasted bank SMS or a due still go to the statement model, as does
anything d1-ultra is unsure of. d1-ultra gets the masked text and a small JPEG of the cleaned photo;
nothing is stored. `whatsapp.processed` logs each message's reply time.
