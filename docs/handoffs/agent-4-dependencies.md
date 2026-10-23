# Agent 4 shared requests and schema proposal

Frozen base: fd618aef74336279e587748b216374d20cc892ad. Branch feat/finboy-whatsapp.
No Python/npm dependency changes required (httpx, Pydantic, SQLAlchemy, stdlib).

## Essential additive schema (recorded before implementation)

0003_whatsapp, down_revision 0002_phase1 adds only:
- whatsapp_bindings: UUID, user FK, unique keyed sender hash, enabled, language
  nullable auto or en/hi/ml, created/updated/last inbound timestamps. Allowlist remains private settings.
- whatsapp_receipts: UUID, binding FK, globally unique inbound provider ID, content
  keyed hash, kind text/audio/command, language, admitted/processing/completed/failed/
  interrupted/ignored fixed state, fixed nullable error code, received/provider/claim/
  completed timestamps. No raw question, transcript, sender, webhook or audio.
- whatsapp_deliveries: UUID, receipt FK, unique (receipt, kind text/audio), fixed
  pending/sending/sent/failed/unknown transport state, nullable unique outbound provider
  ID, nullable sent/delivered/read/failed provider status, created/updated timestamps.
  Graph acceptance is not delivery. No financial answer text retained.

Do not change ledger tables. FK delete cascade applies only within these metadata
records; User FK restricts. Privacy imported-data deletion may preserve this consent/
transport metadata; full future user deletion must delete bindings first.

## Agent 5 requested integration work

- Bootstrap already registers WhatsApp router/module and reserves settings.
- Prepare a stateless loopback-only ingress proxy forwarding exactly GET/POST
  /api/v1/whatsapp/webhook to 127.0.0.1:8014 (integration 8015 later); default deny
  all other paths/methods, redirects, docs, assistant/money/privacy routes. Never tunnel
  the main API. Keep ngrok inspection disabled to avoid raw payload persistence.
- Stale task reconciliation hook: services.whatsapp.receipts.interrupt_stale(session,
  before=<aware datetime>) commits interrupted work; run on startup with a conservative
  cutoff (10 minutes), and optionally before admissions. Never replay memory-only data.
- Existing test_postgres asserts exact 0002_phase1; update shared integration test to
  current Alembic head after consuming migration, not in Agent 4 owned files.
- Please consume this file at handoff; no shared source edited by Agent 4.

Sender/content HMAC hashes use the existing stable TOKEN_ENCRYPTION_KEY with domain
separation. Preserve that key across restarts/credential refreshes; no additional
setting is needed. Never use rotating Meta access token as the hash key.

## Local verification update

Agent 4 implements the stateless restricted ASGI ingress in owned
`services/whatsapp/ingress.py`. Run `uv run python -m
finboy.services.whatsapp.ingress --api-port 8014 --port 8094`; no new FastAPI app.
It is locally verified to deny all product routes/other methods. The temporary
ngrok tunnel points only to this proxy, with `--inspect=false --log=false`.
Agent 5 should review/consume this implementation and use --api-port 8015 or 8000
only after environment verification; do not create a duplicate ingress.

`pnpm check` passed (207 Python unit tests, 10 web tests, strict TS). Build passed.
`pnpm test:integration`: 11 passed; 1 failed/5 errors in baseline tests. Four A1
fixtures reject finboy_p4 via the old database-name allowlist; baseline revision test
expects 0002_phase1; A2 integration hit a local connection timeout under concurrent
machine load. All seven Agent 4 PostgreSQL tests pass. Please update allowed
finboy_p1–p5 database guards and head checks in shared integration work. Agent 4
will not modify old owners' test files.

## Live transport state update

Existing Meta app's restricted callback is active and app-to-WABA subscription is
verified. Human renewed the temporary token; both WhatsApp permissions and expected
assets are valid. Actual expiry: 24 October 2026 03:30 IST. Credential values remain
only in private files. Phone checks pending. The frozen branch intentionally retains
Agent 3 placeholders; assembled-runtime STT/TTS/ledger answer QA must follow its
handoff. Final owned checks: 76 unit/HTTP tests + 9 PostgreSQL tests pass.

## Post-handoff assembled-service exception adaptation

Read fixed assembled commit cbd2ed2. Agent 3's service now exposes
`InvalidAudio(ValueError)` from services/speech/media.py, while the bootstrap only
raised ProviderUnavailable. Please adapt owned final integration WhatsApp processor
STT catch and TTS catch to include that exact exception (or an explicit shared
input-error boundary) and add a regression test. Currently malformed/over-duration
audio falls to the generic processing_failed handler rather than the helpful text
fallback. No simultaneous source edit was made by Agent 4 after handoff.

Actual text phone transport now verified: one signed inbound text question, fixed
assistant_unavailable fallback from frozen runtime, Meta provider status READ. No
audio receipt yet. A separate managed verification worktree at fixed cbd2ed2 now
serves 8014/finboy_p4 with the actual assembled assistant/speech. Its private config
uses Agent 3's verified model/stock voice IDs and the refreshed Meta token; financial
routes remain loopback-only behind the same restricted 8094 ingress. All 42 synthetic
emails imported through the actual demo endpoint; summary truth and corrected food
facts verified via actual assistant HTTP for en/hi/ml. No moving HEAD or Agent 5
checkout/runtime was modified. Voice-note request is pending with the human.

### InvalidAudio request resolved

Agent 5 provided narrow b651d69 and explicitly requested consumption in the temporary
live verifier. Cherry-picked onto fixed cbd2ed2 as local verifier head 249a1e8;
22 focused processor tests and assembled pnpm check (365 backend unit, 10 web, TS)
pass. Original feat/finboy-whatsapp source stays frozen-base; no source refresh.

Additional test isolation observation: after a real phone receipt exists in the
disposable DB, old WhatsApp integration assertions select/count whole tables rather
than the synthetic binding/receipt. They should scope to each test's keyed binding
hash/known receipt IDs before rerunning against a DB that contains live transport
metadata. Teardown already deletes only synthetic metadata. Do not delete real
phone receipts just to satisfy the empty-table assumptions. No PG suite was run
against the active imported ledger/phone metadata during these live follow-ups.

Assembled verifier `pnpm build` also passed after the narrow audio-error fix.
