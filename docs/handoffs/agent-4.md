# Agent 4 handoff — WhatsApp ledger questions

Branch: `feat/finboy-whatsapp`.
Frozen base: `fd618aef74336279e587748b216374d20cc892ad`.
Implementation head: `238b1611d836b47459232a577f306dd20e33d3b1`.
This documentation is committed afterward; resolve final branch HEAD with git.
Managed worktree: `/Users/sahal/.codex/worktrees/finboy-whatsapp/ai_boom`.
Runtime: API 8014; ingress 8094; web 3014 reserved; disposable DB `finboy_p4`.
No main merge, other worktree edits, lockfile changes, or dependency additions.

## Owned changes

- Signed/bounded GET+POST `/api/v1/whatsapp/webhook`, app-secret/WABA/phone context
  validation, private approved-sender mapping; unknown sender never queries the ledger.
- Metadata-only binding, inbound receipt and outbound delivery models; additive
  `0003_whatsapp` on `0002_phase1`. Schema proposal was recorded before implementation.
- Durable admission/atomic claims, duplicate/concurrent suppression, STOP/START and
  language commands, fixed states/errors, stale interruption without replay, separate
  accepted-vs-delivered tracking and unknown outbound results without automatic retry.
- Text→shared Agent 3 assistant. Audio→authenticated bounded Meta media→shared STT→
  same assistant→text plus shared TTS MP3 upload/send-by-ID. Text survives audio failure.
  No new assistant, finance engine, provider integration, WhatsApp mutations or OCR.
- Exact-path stateless ASGI ingress with redacted logs, default deny, time/size limits,
  no redirects/arbitrary upstream, and actual public HTTPS denial verification.
- `docs/whatsapp.md` setup, renewal, retention/restart semantics, official sources,
  real/mock evidence and approved recipient testing instructions.

Shared requests live in `docs/handoffs/agent-4-dependencies.md`: startup stale-work
hook, integration test database/revision guards, and consumption of this single
restricted ingress. No shared source changes were made independently.

## Exact executed checks

| Command / probe | Actual outcome |
| --- | --- |
| `uv sync --locked --all-packages` | Passed |
| `pnpm install --frozen-lockfile`, `pnpm env:setup` | Passed |
| Local `createdb ... finboy_p4` | Created disposable database; shared container left running |
| `pnpm db:migrate` | Passed, head `0003_whatsapp`; first attempt exposed local env password mismatch, corrected from existing private config |
| `pnpm db:check` | Passed twice, no upgrade operations |
| `uv run pytest apps/api/tests/whatsapp -q --tb=line` | 85 passed: 76 unit/HTTP + 9 real PostgreSQL tests |
| `pnpm check` | Passed: Ruff/format, ESLint, 210 Python unit tests, 10 web tests, strict TypeScript |
| `pnpm build` | Passed production build, including final code changes |
| `pnpm test:integration` | Initial complete run: 11 passed, 1 failed, 5 errors; 7 then-existing WhatsApp PG tests passed. Two additional concurrent HTTP PG tests subsequently passed; final owned PG suite 9/9 |
| Baseline schema assertion targeted rerun | Fails only because it still expects `0002_phase1` instead of `0003_whatsapp` |
| `git diff --check` | Passed |
| Local and public ingress denied-path/method probes | All denied 404; valid challenge 200, exact challenge only |
| Public synthetic signed unknown sender/tamper | 200/no receipt; tampered exact bytes 403; no sends |

Full integration blockers: four old A1 tests permit only finboy/finboy_a1/finboy_test,
so reject mandated `finboy_p4`; the shared schema test expects the old revision;
A2 privacy integration encountered a transient local connection timeout during
concurrent machine load. These files remain with their owners/Agent 5. Do not switch
tests to the shared finboy DB to bypass the guards.

Coverage includes provider 401/429/5xx/timeout, no automatic send retry, MIME/size/SHA/
redirect/host validation, expired media, STT/TTS failures, fixed-error/log redaction,
three-language and romanized input, commands, actual concurrent HTTP→PostgreSQL→
shared-service fakes, uniqueness/claim constraints, stale receipts and delivery status.
Mocked audio bytes are synthetic transport doubles and never prove playable audio.

## Real Meta setup and evidence

Existing **ai_boom Messaging Demo** / **SAHAL** reused; App ID 953180210789448.
No new app/phone/production publishing/billing. Profile resolved by the requested
account/stable identity, not cached numeric browser profile IDs. Human completed
login and previous-settings token renewal. The token was copied directly into
mode-600 private files, then clipboard cleared; never displayed or committed.

Live Graph v26.0 token debugger: valid, matching existing app, WhatsApp management/
messaging scopes. Expected phone and WABA reads returned 200. Token expires
**24 October 2026, 03:30 IST**. Renew before a later demo.

App callback was registered **only after** public non-webhook routes were proven
blocked. Actual app subscription POST succeeded; GET verified active
`whatsapp_business_account`, correct restricted callback and `messages` field.
WABA subscription was initially missing; POST succeeded and fresh GET verified the
existing app. Graph acceptance does not establish message delivery.

API, ingress and temporary ngrok tunnel were started for phone verification.
Ngrok is `--inspect=false --log=false`; its only upstream is 127.0.0.1:8094, never
8014/the full API. Current URL is ephemeral, stored in
`/tmp/finboy-whatsapp-ingress-url`; use live management state before registering it
again. Restart instructions and public denial checks are in `docs/whatsapp.md`.

## Remaining verification and ownership

- Approved human phone START + short voice note checks pending at handoff.
  No phone delivery, actual received audio, or financial answer is claimed yet.
- This branch retains frozen Agent 3 unavailable placeholders. After owners hand off,
  Agent 5 assembles the same shared services and verifies English/Hindi/Malayalam
  text+voice questions against the actual imported ledger, with phone inspection.
- No provider feature is marked complete on mocks. Actual STT/TTS/MP3 and six phone
  question cases remain mandatory after integration/account permission permits.
- No frontend changed; no viewport/microphone-denied screenshots are claimed. Those
  screens and their browser QA stay with Agents 2/3/5. Credential screens were not
  saved as artifacts. Public transport checks used HTTP probes, not financial screenshots.
- Metadata stays in disposable PostgreSQL; no payload replay exists. Invoke
  `interrupt_stale` at startup as requested, preserve consent on any future retention
  cleanup, and never blindly resend an unknown outbound delivery.

Agent 5 may take final integration edit ownership after consuming this handoff.

## Follow-up live evidence after 37556b0

Human initiated the phone test. One real allowlisted text question arrived and the
signed webhook acknowledged it; frozen assistant unavailable was recorded truthfully.
Its fallback text was accepted and a real provider callback advanced to READ. No
raw question/phone/response was retained. No audio receipt has arrived yet.

For the remaining voice check, created a separate managed verification worktree at
**fixed assembled commit cbd2ed2**, finboy-whatsapp-live/ai_boom. It uses Agent 4's
8014/3014/finboy_p4 isolation and refreshed private credentials. The original source
branch and Agent 5's running 8015/finboy_p5 checkout were not changed. Migration and
drift checks pass. Actual imports/demo processed 42 emails using existing offline
recordings; actual summary matched the truth table; the authorized synthetic Hotel
Arya correction was applied through the local review API. Actual assistant HTTP en,
hi, ml responses each returned the corrected food fact with policy=answer. This
proves the assembled ledger/assistant connection, not WhatsApp audio delivery.

A new assembled boundary issue (InvalidAudio exception adaptation) is requested in
agent-4-dependencies.md for Agent 5, which now owns final integration source edits.
Voice note and six language text/voice phone cases remain pending; no fake success.

Agent 5 coordination follow-up: consumed explicitly supplied narrow InvalidAudio
fix b651d69 only in the isolated live verifier (local 249a1e8 on cbd2ed2). Processor
22/22 and assembled pnpm check pass (365 Python unit + 10 web + strict TS). Source
branch is unchanged; no moving integration HEAD was followed. Fresh English text/
voice phone question remains awaited; only the earlier fallback reply is READ.

Assembled verifier `pnpm build` also passed after the narrow audio-error fix.
