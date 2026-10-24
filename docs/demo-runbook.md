# FinBoy complete-system demo runbook

Use `feat/finboy-integration`, never main for this acceptance round. Frozen source
base stays `feat/finboy-ready-base` (`fd618aef74336279e587748b216374d20cc892ad`).
See parallel-completion.md for ownership and isolation. The human authorized Agent 5
to finish the frontend because Agent 2 was not running. Original design source is
untouched; reviewed snapshot hashes are in handoffs/design-snapshot.json.

## Start and verify the environment

```sh
uv sync --locked --all-packages
pnpm install --frozen-lockfile
pnpm env:setup
pnpm db:up
# Create only your disposable database if it does not exist:
docker compose exec -T postgres createdb -U finboy finboy_p5
pnpm db:migrate
pnpm db:check
pnpm check
pnpm build
pnpm test:integration
pnpm eval:extraction
pnpm voice:benchmark
FINBOY_EXTRACTION_MODE=offline API_PORT=8015 WEB_PORT=3015 pnpm dev
```

Before those database commands check the ignored backend environment: local host
127.0.0.1:5433, database finboy_p5, nonproduction, DEMO_TODAY=2026-10-28, exact web
origins 3015, WEB_APP_URL=http://127.0.0.1:3015. The web's public API URL is 8015.
Never print a database URL/password. No db:down/Compose down/volume deletion.
Offline uses the existing actual structured-response recordings, with configured
OPENAI_EXTRACTION_MODEL matching their manifest. Never run --live or rerecord en masse.

`GET /api/v1/health` tests core/database availability. `GET /api/v1/readiness`
separates schema, tool availability and provider configuration. “Configured” does
NOT mean provider entitlement, live delivery, or worker completion. BackgroundTasks
are in-process and not durable; recorded active imports are not a worker heartbeat.
A restart abandons memory-only work; fresh import admission recovers stale runs.

Final 8000/3000/finboy requires an assembled-branch environment review first:

```sh
pnpm final:check-env
pnpm final:db:migrate
pnpm build:final-web
pnpm dev:final-api     # separate terminal
pnpm start:final-web   # separate terminal
```

The launcher rejects production, remote hosts, unexpected port/database settings.
It derives the local finboy URL privately, uses only registered callback 8000,
keeps WhatsApp disabled here until a separately reviewed ingress worker switch,
and leaves ignored p5 environment files untouched. Keep
p5 env intact; pass reviewed local finboy settings only to final verification
processes. Do not repoint another agent's environment or listeners.

## Reset only disposable imported records

On the checked local p5/final test environment open Privacy → Delete imported data,
review the dialog, and confirm. This removes email-derived source/events, orphaned
transactions/commitments/revisions and structured extraction cache. It preserves
audit history and unrelated manual records. It does not delete messages from Gmail,
revoke Gmail, remove WhatsApp consent metadata, or erase a database/volume.
Then use Connect → Load demo mailbox. This is the actual ingestion pipeline; never
write final expected totals directly into SQL. Restarting/re-importing alone preserves
user corrections and confirmations. Deletion is required to return to the original
synthetic scenario. Wait for an import to finish before deletion; an active lock
returns busy and should be retried after completion/pause.

## Email → records → correction → review

1. Open `/connect`. Try demo first; raw `.eml` bytes stay in memory. `/import/{runId}`
   should finish with 42 checked, 36 candidates, 26 created, 6 duplicate merges,
   2 review items, 6 nonfinancial skips, 0 failed. Counters are real cumulative work.
2. Dashboard: income ₹62,000, net confirmed outflows ₹37,420, upcoming ₹9,800,
   estimated unallocated ₹14,780. These are email-derived tracked amounts; actual
   bank balances may differ. Pending records stay excluded.
3. Transactions → Amazon ₹799 → evidence: three notifications, one canonical record.
   Inspect source snippets, rule/LLM method, confidence factors and revision history.
4. HOTEL ARYA starts as travel. Change Category to Food & dining and Save correction.
   Only changed fields are submitted/locked. Dashboard food changes ₹6,610→₹7,860;
   total net spending remains ₹37,420. Re-import must preserve the correction.
5. Model a ₹5,000 monthly SIP/commitment. Backend remaining = ₹9,780. Warnings stay
   visible. Exact disclaimer: “This models cash flow from FinBoy's tracked records.
   It is not a recommendation to purchase any security.” No funds/stocks are picked.
6. Review: inspect unknown ₹500 VPA and unverified ₹1,840 order. Confirm/reject only
   after checking evidence. Keep separate does not silently confirm. Merge only
   when two records describe the same payment. Review actions change totals as
   appropriate; reset/re-import to return to the original demo.
7. Re-import same demo: no new source/event/transaction rows. Upload the actual 42
   `.eml` files: same pipeline, same canonical records; mode-specific sources can be
   added and reconcile. Reject invalid type, >50 files, >2 MB each, truncated MIME.

## Questions and speech

Use `/assistant`; choose Auto, English, Hindi, Hinglish, Malayalam or Manglish.
Record ≤30 s / 3 MB or type. The HUMAN handles microphone permission. Review the
editable transcript before Ask; there is no auto-submit or persisted recording.

- EN: “How much did I spend on food this month?”
- HI: “इस महीने खाने पर कितना खर्च हुआ?”
- ML: “ഈ മാസം ഭക്ഷണത്തിന് എത്ര ചെലവായി?”
- Manglish: “Ee masam foodinu ethra poyi?”
- Hinglish: “Is mahine food par kitna kharch hua?”
- Unallocated: “How much money is left from my tracked salary this month?”
- Simulation: “Can I set aside ₹5,000 each month?”
- Decline: “Which mutual fund should I buy?”

After correction, each food answer must cite ₹7,860 from the same engine. Listen to
answer requests actual MP3 separately; click play. A missing/failed speech provider
leaves text usable and reports unavailable. Verify number pronunciation with human
listening; do not infer this from HTTP success. Hindi/English use Resemble Ultra
(the human's final provider choice); Malayalam uses verified Gemini TTS. Model/voice
IDs and actual benchmark evidence are in voice.md. No cloning/training requested.

Test keyboard navigation, dialog Escape/focus return, browser mic denial, offline,
empty ledger and missing-provider states. Test at 1440×1000, 390×844, 320×740.
`?graphics=off` deliberately forces the app's no-WebGL fallback. Text and money
controls must work without a graphics context. Marketing's example figures and
animated voice preview are synthetic illustrations, never product live evidence.

## Live Gmail

Google callback URIs registered by A2: API 8000 and 8002, plus seeder-only 8767.
Use the assembled backend on registered 8000 with matching WEB_APP_URL/CORS; do not
invent 8015 callback. Do not stop the old A2 server just to steal its port.

The previous grant was deliberately revoked. Human reconnects in the approved Gmail
profile; human performs consent/unverified-app steps. App requests gmail.readonly
only, with one-use hashed state, PKCE and encrypted verifier/refresh token. Access
tokens stay in memory. Testing-mode refresh token expiry is seven days: reconnect
before a later demo. Seeder's insert-only consent is separate; its local manifest
prevents repeat Message-ID insertion, with the uncertainty caveat in gmail-setup.md.

On the assembled runtime connect → Gmail candidates → actual pipeline → completed
progress. Demonstrate Pause/Resume. Disconnect/Keep ledger must revoke at Google,
wipe encrypted token and keep records. Human verifies grant absent from Google
Account connections. Optional delete affects that connection's imported evidence;
full imported-data deletion keeps audit events. Never claim live import based on
the old stub failure or a mocked Google HTTP test.

## WhatsApp Q&A only

Existing Meta app ai_boom Messaging Demo / SAHAL remains in its existing state.
Use the sahlcyprus profile by stable account identity. No publishing or new billing.
Only approved private allowlist senders may reach the local user's ledger.

The only tunnel upstream is the restricted ingress, NOT the API or web:

```sh
API_PORT=8015 WHATSAPP_INGRESS_PORT=8095 pnpm dev:whatsapp-ingress
# Human-authorized tunnel setup, only after public denial probes:
ngrok http 127.0.0.1:8095 --inspect=false --log=false
```

The existing Agent 4 verification tunnel/8014 runtime must be coordinated before
switching; do not stop unrelated listeners. Check current ngrok management state;
`/tmp/finboy-whatsapp-ingress-url` may be stale. Verify public /docs, health/readiness,
money/transactions/privacy/assistant, encoded/trailing-slash paths and other methods
return 404. Only exact GET/POST /api/v1/whatsapp/webhook may forward. Keep signature,
WABA/phone context and allowlist checks active. Subscription and callback should be
changed only after these checks. Never print tokens/phone IDs/phone numbers.

Read token expiry from current private provider state and renew before expiry with
the HUMAN. A2-style no-login product routes must never be exposed to the tunnel.
A Graph 200 establishes acceptance only; provider delivered/read status and the
human's phone confirmation establish received replies. No automatic retry for an
unknown outbound result. Restart marks stale work interrupted without replaying it.

Approved test phone: send START, then one text and one short voice note per EN/HI/ML
script above. Check actual reply content/playable voice on phone. Language commands
en/hi/ml select preferred replies; STOP disables subsequent financial replies.
Unknown sender must get no ledger access. Duplicate delivery must not produce a
second answer. Metadata stores hashes/IDs/fixed states only, never message/audio or
financial answers. A UPI screenshot may only create a record waiting for review; no
WhatsApp confirmations, edits or deletions. Use only synthetic screenshots for demos.

## Required handoff truth

Record exact commands and outcomes, dependency/migration changes, source commits,
real-vs-mocked provider results, screenshot paths, token/tunnel state and every
unfinished criterion. Mark provider configuration separately from live acceptance.
Do not push, deploy, publish Meta, widen permissions, or merge into main.
