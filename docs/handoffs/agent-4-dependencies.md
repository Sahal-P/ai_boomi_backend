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
