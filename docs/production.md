# Authorized private production deployment

**Current migration, 29 October 2026:** finboy.io is served by a standalone Next.js
frontend on voxpay behind nginx, using a same-origin loopback API route. The previous
Vercel frontend is temporarily retained during cutover. Current progress, verification,
release automation and rollback are tracked in [voxpay frontend hosting](voxpay-hosting.md).
The older deployment descriptions below are historical unless that document says otherwise.

The human authorized GitHub publication, main integration, Vercel frontend and
voxpay backend on 24 October 2026, then chose private single-household access and
an antlegs.in subdomain. This supersedes the old prohibition on production for
this deployment only. Self-serve sign-up came later and stays off until `SIGNUP_ENABLED` is set
(see the [sign-up release procedure](#sign-up-release-procedure)).

Both requested repositories preserve the complete monorepo and all named branches,
including the immutable ready base. Vercel builds apps/web; voxpay runs apps/api.
Shared lockfiles/history remain intact. A complete design snapshot is committed
in a separate publication worktree; its original uncommitted worktree is untouched.
The integrated product already selectively incorporated that design. Snapshot
ancestry is recorded without replacing newer product routes, helpers or privacy copy.

## Access and network

Production refuses to start without a scrypt password hash, independent Fernet
session key, and exact HTTPS web origin. Login returns a 12-hour __Host cookie,
Secure/HttpOnly/SameSite=Lax. Passwords/session values never enter browser storage,
frontend config, Git or logs. Sign-out clears the browser cookie; rotating the
session key invalidates all sessions. There is no self-service password recovery.
Keep the generated password in the private local production-access.txt file.

All product/import/finance/assistant/privacy routes require a session. State-changing
requests require the exact Origin. OAuth callback remains independently protected by
single-use state/PKCE. WhatsApp's signed webhook is a separate public exception;
production WhatsApp stays disabled pending explicit renewed provider setup.
Health is public and safe. Production API docs/OpenAPI are disabled.

Vercel uses NEXT_PUBLIC_API_URL=/ and FINBOY_API_ORIGIN=https://finboy-api.antlegs.in
to proxy /api/v1 through an external rewrite. Cookies remain first-party. There is
no serverless API body parser in this path. API/provider keys stay only on voxpay.
Preview builds receive no production environment; do not add production credentials
or production-origin proxy settings to preview environments.

**Direct API calls (29 October 2026).** Vercel's proxy could not reach the API about 4 times in 10
(`502 ROUTER_EXTERNAL_TARGET_CONNECTION_ERROR`; the attempts never arrived at the host), while
direct requests always worked. So the browser now calls `https://finboy-api.antlegs.in` itself:
- Vercel's Production `NEXT_PUBLIC_API_URL` is that origin. It is not a secret.
- The web client sends `credentials: "include"` to that origin only, and the .eml upload does
  the same.
- The API allows credentials for the exact web origins only. State-changing requests still need
  that Origin.

The household cookies stay `__Host-`, host-only on the API host, Secure, HttpOnly and
SameSite=Lax. `finboy.antlegs.in` and `finboy-api.antlegs.in` are the same site, so browsers send
them. Everyone signs in once more after the switch. `FINBOY_API_ORIGIN` and its rewrite stay, so open
tabs keep working and `/` remains a rollback. Rate limits now see each visitor's own address
instead of Vercel's.

The Connect page uses the shared API URL helper, including the `/` proxy setting.
When the Gmail callback host differs from the frontend host, authenticated
authorization issues an encrypted 60-second, single-use handoff to the API host.
That host consumes the handoff before creating fresh OAuth state/PKCE and setting
its host-only callback cookie. The handoff route is public only to redeem this
capability; Gmail authorization and finance routes still require the household
session. Handoff and OAuth redirects are non-cacheable and suppress referrers.
No session or OAuth cookies are shared with sibling antlegs.in applications.

The API listens on 127.0.0.1:8020 under a dedicated unprivileged systemd service.
Nginx terminates HTTPS and turns off access/error payload logging and proxy body
buffering. Existing nginx sites, Finind services and databases remain untouched.
The existing PostgreSQL service hosts a separate finboy_prod database and role.
FinBoy uses loopback PostgreSQL; its role must be restricted from non-loopback
authentication in pg_hba.conf without changing other applications' rules.

## Releases and recovery

Install uv/Python 3.15, ffmpeg/ffprobe and nginx/certbot from official sources.
Extract a reviewed git archive into /opt/finboy/releases/COMMIT. Sync uv --locked
--no-dev with an isolated .venv and shared managed Python under /var/lib/finboy.
Load /etc/finboy/production.env without printing values, apply additive Alembic
migrations, check drift, switch current atomically, then restart only finboy.service.
Retain previous release and a PostgreSQL custom-format backup for rollback.
Migrations are never automatically downgraded. Do not run tests or fixture evaluation
against production. Backups are private and contain financial data; retain locally
on the server and apply a documented retention/restore check. The daily root-only
backup timer keeps seven days of custom-format archives and checks their directory
readability with pg_restore --list. This is not a full restore drill; record one
before relying on disaster recovery. Hosted Privacy discloses backup retention.

Nginx configuration templates are in deploy/. Test nginx -t before reload. Use
Certbot webroot/HTTP challenge and a renewal deploy hook that reloads nginx only
after nginx -t. Confirm the certificate and unattended renewal with a dry run.

Gmail uses a new explicitly registered direct HTTPS backend callback:
https://finboy-api.antlegs.in/api/v1/connections/gmail/callback. OAuth codes avoid the
frontend proxy; nginx access logs are disabled. Local callback registrations remain. Human handles
Google consent. Testing mode still expires refresh tokens after seven days.
Never claim production Gmail works until callback registration and live import pass.

Provider keys are reused privately without regenerating existing local credentials.
Production uses the real IST clock, not DEMO_TODAY. Synthetic demo mailbox remains
available through the same pipeline. Actual speech and all deferred WhatsApp voice,
microphone and Gmail acceptance limitations remain recorded in handoffs/agent-5.md.

## Verified live state — 24 October 2026

- Vercel project shl-s-projects/ai-boomi-frontend, apps/web, Node 24; Git connected
  to Sahal-P/ai_boomi_frontend. Production domain finboy.antlegs.in. Only the two
  origin/proxy settings are configured there; provider/access secrets stay backend.
- GoDaddy A finboy-api points to the authorized voxpay host; frontend CNAME uses
  Vercel's project-specific recommended target. Existing DNS records were preserved.
- Both repositories have all 12 named branches and main as default. All branch tips
  are ancestors of assembled main. No force push, history rewrite or branch deletion.
  Original design and A2 uncommitted worktrees remain unchanged. Snapshot ancestry
  commits explicitly retain newer integrated code instead of applying stale routes.
- Actual public HTTPS health returns 200; unauthenticated money/transaction/privacy
  requests return 401; docs/OpenAPI return 404. Proxy household login/cookie roundtrip
  and authenticated readiness passed. Cross-origin deletion returns 403.
- Actual production import processed 42 .eml, 36 candidates, 26 transactions, six
  merged duplicates, two review items and zero failures. Expected 62000/37420/9800/
  14780 tracked totals passed; category correction produced food 7860. No SQL seeding.
- Actual production EN/HI/ML assistant facts match; each speech API returned an MP3
  that decoded locally. Measured speech latencies were 3.666/3.454/8.914 seconds.
  This establishes production HTTP/media, not human microphone or phone playback.
- A >4.5MB invalid multipart request reached the backend and returned its fixed 400
  with a request ID, validating the rewrite path without importing invalid records.
- pnpm check passed 375 backend unit tests, 16 web tests, lint and strict TypeScript;
  pnpm build passed. Local PostgreSQL integration 28/28 and schema drift passed.
  Production applied only additive migrations to a newly isolated database; no test
  suite was run against production. Actual head is 0003_whatsapp, no drift.
- gitleaks full-ref history scan passed. Private local/server env files are mode 600.
- API runs on loopback 8020 as finboy.service; existing Finind services stayed active.
  Certificate expires 21 January 2027; Certbot renewal dry-run passed. Daily backup
  timer is active and initial pg_restore archive listing passed; full restore drill
  and off-host recovery copy remain operator follow-ups. Server retains ~10GB free.

Remaining human acceptance: live Gmail disconnect/revoke
on the deployed callback; browser microphone and chooser checks from the prior handoff.
WhatsApp remains deliberately disabled in production. English phone text acceptance
belongs to the previous local verifier; live voice remains explicitly deferred.
No public signup, Meta app publication, broad public tunnel or renewed WhatsApp grant
was performed by production deployment.

## Connect repair — 24 October 2026

The deployed Connect page crashed because its Gmail URL builder treated the `/`
production API setting as an absolute URL. A regression test reproduces that
configuration and the URL builder now shares the same validation as API requests.
Cross-host Gmail tests also exercise household login, the one-use handoff, callback
cookie domain, mocked Google exchange/import scheduling, replay/expiry rejection,
and unauthenticated finance-route rejection. These are automated checks; live Google
consent and actual Gmail import must still be recorded separately.

Repair verification: `pnpm check` passed 377 backend unit tests, 19 web tests,
lint and strict TypeScript. `NEXT_PUBLIC_API_URL=/ pnpm build` passed. The API
release is `/opt/finboy/releases/7bf4587`; only finboy.service was restarted after
a successful private backup. Public HTTPS health is 200, unauthenticated finance
and Gmail authorization requests remain 401, and existing Finind, nginx and
PostgreSQL services stayed active. No schema changes or production test suites.
The human signed in; the repaired live Connect page rendered at 1440×1000,
390×844 and 320×740, and Connect Gmail reached Google's account chooser with the
direct backend callback.

The human then completed Google consent. The live Privacy page showed Gmail active,
a last scan at 05:27 IST on 24 October 2026, and the Gmail-connected/import-completed
audit entries. A read-only operational metadata check confirmed 15 candidate emails
processed: four transactions created, all four awaiting review; nine emails skipped;
two emails normalized but yielded no usable transaction events and were marked
failed. The run completed with no run-level error. This verifies the live deployed
callback and first Gmail import, with partial message extraction explicitly recorded.
No revoke/delete action was performed and no mailbox content or financial fields
were printed during verification.

## Financial-event eligibility hotfix — 24 October 2026

Release `/opt/finboy/releases/988a731` requires a bounded, affirmative financial
claim with its own amount and proof before admitting a ledger event. Salary/job
advertisements, examples, balances/limits, negations and future payment instructions
cannot become transactions through global keyword matching. Explicit model rejection
suppresses weak rules; anchored settlements with model disagreement stay in review.
Conflicting bill/EMI claims fail extraction instead of silently becoming deductions.
The live cache policy is versioned. No dependencies, HTTP contracts or schema changed.

`pnpm check` passed 556 backend unit tests, 19 web tests, lint and strict TypeScript;
`NEXT_PUBLIC_API_URL=/ pnpm build` passed. There are 179 new synthetic eligibility
and persistence regressions; the prior rules/offline fixture oracles still pass.
No test suite or fixture evaluation ran against production.

A staged read-only check re-fetched the exact reported Gmail message using the
existing grant, matched its stored source hash and returned non_financial/zero
events. No model/provider extraction request or database write was used for that
shadow check. A private backup succeeded before promotion; only finboy.service
restarted. Public proxied health is 200, unauthenticated finance is 401, and existing
Finind/nginx/PostgreSQL services remain active.

Three proven old job-ad false positives were non-destructively reclassified:
sources are non_financial/skipped and transactions rejected with system revisions
and audit events. Checks required pending/zero-confidence state, no payment proof,
no human changes/locks, no financial links/dependents, the original cached model
veto, and a fresh matching message rejected by the new policy. Original evidence
and values remain. Zero confirmed or human-corrected records changed; no records
were deleted. Other review candidates remain available. This is not a guarantee
of perfect extraction for arbitrary future messages.

The ongoing UX Backend/Product integration must merge this hotfix from main before
release, preserving its eligibility policy alongside the new dataset/retry features.
See `handoffs/ingestion-eligibility-hotfix.md`.

## UX remediation release procedure

The UX round is authorized from b572565 under the implementation brief and
`docs/ux-round/api-contract.md`. Only Agent 1 releases after Agent 2's explicit handoff
and assembled real UI/API verification. Preserve the latest reviewed running release until
integration gates pass; check current again before promotion. API/schema support deploys before the dependent frontend.
The read-only `/api/v1/demo` is a new explicit public exception; it cannot access the
household database. The legacy household demo-import mutation is disabled.

Before migration, run the aggregate read-only source inventory described in
`ux-round/data-isolation-operations.md`, make/validate a private backup, and verify no
active import is being terminated. Stop/restart only finboy.service when necessary
to prevent old reconciliation code writing through a new scope migration. Apply
0004_ux_trust, 0005_scan_continuation and 0006_event_origins; preserve all data/revisions and quarantine
mixed provenance. Never reset the production ledger. No automatic schema downgrade
or old-code rollback that bypasses scope filters. Record any actual mixed-data
operator acceptance separately from passing synthetic preservation tests.

Keep the same session key/password hash, Gmail grants/callback, provider credentials,
proxy origins, DNS, nginx sites and other applications. Do not run tests or fixture
imports in production. Production checks are read-only health/access/schema/provider
configuration and human-session browser journeys, with consent/playback gaps explicit.

Read-only UX preflight on 24 October 2026: production provenance inventory returned
26 demo-only transactions, four demo-only obligations and zero mixed transactions
or obligations. Only aggregate operational counts were printed; no source/financial
fields were read into console output. The current service/release remained unchanged.
Repeat the inventory immediately around migration rather than assuming it is frozen.

The extended read-only UX preflight also found zero merged transactions. 0006 retains
original event lineage for later exact source deletion and removes derived private
review snapshots with the deleted evidence. Unknown older merge lineage fails closed
before deletion instead of guessing. No production privacy action was run for UX tests.

## UX release executed — 24 October 2026

The combined application source `3098a14` is deployed: voxpay current points to
`/opt/finboy/releases/3098a14`; Vercel production deployment
`6BST4o7vdCJjU5GwoP3tnxUStGyh` was Ready for main on `finboy.antlegs.in` (42-second build).
This supersedes the earlier runtime/schema observations above while preserving the eligibility
hotfix. Subsequent release-evidence/test-only commits preserve the same application source.

A fresh private backup passed archive listing. Immediate preflight found zero active imports,
26 demo-only transactions, four demo-only obligations, zero mixed records and zero invalid
cross-scope payment links. Additive 0004–0006 migrations preserved record/source/import counts;
revision/audit counts did not decrease. Current schema is `0006_event_origins`, no drift;
source origins are complete and household reads have zero demo-provenance contamination.
No production record reset/deletion, test suite, fixture import or general rescan was performed.

Only FinBoy stopped/started. Finind, Finind Celery, nginx and PostgreSQL remained active.
Public health and read-only demo return 200; unauthenticated finance/privacy return 401;
docs/OpenAPI return 404, both directly and through the frontend. The existing human household
session survived. Actual browser Sources controls, summary coverage/household identity and
exact evidence passed; evidence dialogs returned focus with no horizontal overflow at
1440×1000, 390×844 and 320×740. The public sample rendered its persistent read-only identity.
Provider keys, session/password settings, Gmail grants/callback, DNS and proxy origins stayed
unchanged. No new consent or microphone permission was requested for this release.

See `handoffs/ux-integration.md` for commands, verification boundaries and CI, and
`ux-round/implementation-map.md` for F01–F38 software completion versus human acceptance.
Never roll the pre-scope API back onto the migrated database; recover forward with scoped code.

## Capture and AI release configuration

The human authorized the coordinated release of the committed capture and live-AI
assistant changes after local verification. The release applies only additive migration
`0007_whatsapp_capture`, after a validated private backup and an active-import check.
Record counts must remain unchanged. Preserve household sessions, Gmail grants and
all unrelated host applications. Only FinBoy is stopped/restarted.

The reviewed assistant model remains `gpt-6-luna`; the newly supplied OpenAI key is
transferred privately from the operator's secrets file to `/etc/finboy/production.env`.
No other production credential or setting changes. Never copy it to Vercel or Git.

Deploying the capability does not activate unverified providers. Production speech
remains `openai` and WhatsApp remains disabled. Future Groq activation requires a
verified `GROQ_API_KEY`, `GROQ_TRANSCRIBE_MODEL=whisper-large-v3-turbo` and
`SPEECH_TRANSCRIBE_PROVIDER=groq`. Screenshot activation additionally requires a verified
`OPENAI_VISION_MODEL` and separately authorized WhatsApp acceptance. No such live
Groq/vision/WhatsApp acceptance is claimed by this release.

## WhatsApp production activated — 24 October 2026

The human explicitly requested activation after the coordinated release. Production
now has `WHATSAPP_ENABLED=true` with the same private one-sender allowlist, app and
phone context. The renewed token was validated for the existing app, required grants
and phone/WABA access, then exchanged server-side for a long-lived user token expiring
23 December 2026 at 06:37:10 UTC. No system user, new app/phone, recipient or billing
change was created. Credentials remain private; stable encryption/session/Gmail keys
and all unrelated provider settings are preserved.

Meta Dashboard verified and saved the exact production callback
`https://finboy-api.antlegs.in/api/v1/whatsapp/webhook`; fresh Graph reads confirm its
active `messages` subscription and the existing WABA/app subscription. Public exact
challenge succeeds; wrong verify token and invalid signature return 403. Finance
remains authenticated (401 without session), and health returns 200. Only FinBoy
restarted; Finind, Celery, nginx and PostgreSQL remain active.

`OPENAI_VISION_MODEL=gpt-6-luna` passed a synthetic image-input check through the real
reader: one grounded event, matching amount and review-only confidence; zero database
writes. Production speech remains OpenAI; Groq is not configured. Real production text
receipts completed without errors and an outbound reply reached Meta `read` status.
This is actual text transport; it does not establish phone voice playback or a real
image-to-review round trip. The earlier human-deferred voice acceptance remains pending.

Readiness now compares the database revision with the deployed Alembic head instead
of a hard-coded old revision. Current 0007 reports current; 0006 remains degraded.
`pnpm check` passed 733 backend unit and 39 web tests, lint and strict TypeScript;
the production-shaped build passed. No schema or dependency change accompanies this
readiness correction, and no test suite was run against production.

## Village pilot release procedure

The human authorized release of `feat/finboy-village-pilot` through `194c6e2` on 26 October
2026 and separately selected owner pilot mode. Release follows the steps above: validated private
backup, active-import check, additive migration `0008_village_pilot`, drift check, restart of
`finboy.service` only. Record counts must stay unchanged; with every `users.pilot` false the
owner's web app and WhatsApp question flow behave as before.

Then, in order and only as the human approves each step:

1. Dogfood week: `python -m finboy.services.pilot.cli owner on` switches the owner's own number
   to the pilot flows; `owner off` switches back.
2. Enroll each household: `pilot.cli enroll` prints "Pilot household N" and its UUID. The human
   registers the number as a Meta test recipient (at most 5 recipients on the test number),
   adds `"<number>": "<uuid>"` privately to `WHATSAPP_SENDER_ALLOWLIST_JSON` in
   `/etc/finboy/production.env`, and restarts only `finboy.service`.
3. Reminders: after Meta approves the template in [the pilot contract](pilot/contract.md#reminder-template-human-step),
   set `WHATSAPP_REMINDER_TEMPLATE`, restart, then install
   `deploy/finboy-pilot-remind.service` and `.timer` and enable the timer. The job runs every 30
   minutes and sends only 08:00–20:00 IST; it prints counts only. Without a template, leave the
   timer disabled: reminders then follow each household's next reply.
4. Weekly: `pilot.cli report --weeks 1` prints counts only for the pilot review.
5. Erasure on request: `pilot.cli erase <uuid> --confirm`, then remove the number from the
   allowlist and from Meta's test recipients.

Never run tests against production; real Hindi voice, phone taps, low-end Android playback and
reminder delivery are recorded as human acceptance, separately from automated checks.

## Sign-up release procedure

`feat/finboy-signup` adds self-serve households ([contract](signup-round/contract.md)). Release
follows the steps above: validated private backup, active-import check, additive migration
`0009_signup`, drift check, restart of `finboy.service` only. With the new settings unset,
production behaves as before: the owner signs in with the household password, the login page
shows no WhatsApp or Google button, and WhatsApp answers only the allowlist. Keep
`WEB_SESSION_KEY` stable: it also keys the login-code and nonce HMACs, so rotating it signs
everyone out and voids codes in flight. Vercel needs no change; the web app reads the public
sign-in settings from `GET /api/v1/auth/session`.

Then, in order and only as the human approves each step (settings go in
`/etc/finboy/production.env`, followed by a restart of `finboy.service` only):

1. **WhatsApp number:** move the Meta app to the real business number and a permanent System
   User token, then set `WHATSAPP_PUBLIC_NUMBER` (digits only). The test number replies only to
   its registered test recipients, so public sign-up must wait for this step.
2. **Google:** create the sign-in-only client, set `GOOGLE_SIGNIN_CLIENT_ID`, and complete brand
   verification with the reviewed `/privacy-policy` and `/terms`. Keep
   `GMAIL_FOR_NEW_ACCOUNTS=false` until Google verifies the Gmail scopes.
3. **Open sign-up:** set `SIGNUP_ENABLED=true` and `SIGNUP_LIMIT=100`. `SESSION_DAYS` (30),
   `DAILY_AI_LIMIT` (100) and `DAILY_VOICE_LIMIT` (60) have defaults.
4. **Daily:** `python -m finboy.services.accounts.cli counts` prints counts only (agreed,
   pending, limit, waitlist). `tidy` removes sign-ups that never agreed within 7 days; new
   sign-ups also tidy a bounded batch as they arrive.
5. **Closing:** `SIGNUP_ENABLED=false` stops new households only. Existing households keep
   signing in with WhatsApp or Google, and new numbers are ignored as before.

People delete their own household from Privacy → "Delete my account"; the owner household cannot
be deleted from the web. Reminders stay pilot-only until self-serve template sends exist. Real
phone sign-ups, Google sign-in and voice quick add are recorded as human acceptance, separately
from automated checks.

## Companion branding release — 28 October 2026

The human selected the yellow companion logo, then authorized merge, push and deployment.
Commit `65b05b6` adds the outlined FinBoy wordmark, twelve SVG variants, PNG/ICO/Apple/app
icons and the manifest; navigation, sign-in, legal pages, footer and README share the mark.
Main and the branding branch were pushed to both named repositories. Vercel production
`FDd7Y8VjAxvJARiUR9LhsDLQ9S4N` reached Ready, with `finboy.antlegs.in` assigned; fetched logo,
mark and 512 px icon match the committed bytes. Live public rendering passed at
1440/390/320 px. Health remains 200 and unauthenticated finance remains 401.

Only frontend identity changed. No backend code, database, provider, access or DNS setting
needed deployment or modification. Production test suites, fixture imports and financial
mutations were not used. Local resolver failures were worked around only in the verification
client using the actual public DNS address and normal HTTPS certificate validation.

A follow-up changes the pilot unit-test fixture to noon UTC on the configured business day,
fixing six existing CI failures caused by SQLite timezone loss and demo-date drift. It changes
tests only. UTC checks (908 API unit tests, 48 web tests, lint/types) and the production build
pass. See [branding release evidence](handoffs/finboy-branding.md) and [asset usage](branding.md).

## Sarvam speech release procedure

`feat/finboy-malayalam-voice` adds Sarvam speech and Malayalam
([contract](malayalam-round/contract.md)). It has no migration. With the new settings unset,
production behaves as before: OpenAI transcription and Gemini Malayalam speech.

**Before release:**
- In Sarvam's dashboard, turn off training on your content and set Data retention → Model APIs
  → "No retention". The privacy policy promises this.
- Pick the Malayalam voice by listening.

**Release.** With approval, add the settings to `/etc/finboy/production.env`, then restart
`finboy.service` only:

```
SARVAM_API_KEY=<from the private secrets file>
SPEECH_TRANSCRIBE_PROVIDER=sarvam
SARVAM_STT_MODEL=saaras:v3
MALAYALAM_TTS_PROVIDER=sarvam
SARVAM_TTS_MODEL=bulbul:v3
SARVAM_TTS_SPEAKER_ML=<chosen voice>
```

**Check:** signed in as the household (readiness needs a session, even on loopback),
`/api/v1/readiness` should report `transcription_configuration` and `malayalam_tts_configuration`
as `configured`.

**Rollback:** set `SPEECH_TRANSCRIBE_PROVIDER=openai` and `MALAYALAM_TTS_PROVIDER=gemini`, then
restart.

**Acceptance:** record real phone voice notes in Malayalam, Hindi and English, and playback of a
Malayalam reply, as human acceptance, separately from these checks.

## Malayalam voice release — 29 October 2026

The human asked to merge, push and deploy `feat/finboy-malayalam-voice`, which sits on the sign-up
round. Merge commit `21138dc` (main was `bcc9ca4`) and the branches `feat/finboy-malayalam-voice`
and `feat/finboy-signup` were pushed to both named repositories without force. GitHub Actions
passed in both.

**Before release:** Ruff clean; 1,011 API and 48 web unit tests; strict types; `pnpm build` and
the Vercel-shaped build (`NEXT_PUBLIC_API_URL=/`); `pnpm db:check` (no drift); 74 PostgreSQL
integration tests; 232 Playwright tests (119 skipped by design). The published commits hold none of
the local provider keys.

**Backend.** Release `/opt/finboy/releases/21138dc` (archive checksum verified, `uv sync --locked
--no-dev`); `574b4ca` stays for rollback. A fresh private backup (`20261028T190355Z.dump`) passed
`pg_restore --list`. Under the production env file, before the switch: head `0009_signup`, no
drift, settings unchanged (OpenAI speech, Gemini Malayalam speech), the app builds, zero active
imports and zero in-flight WhatsApp messages. `current` switched atomically and only
`finboy.service` restarted (19:06 UTC). Loopback and public health returned 200, finance and
privacy returned 401, docs 404, and the webhook refused a wrong token with 403. nginx, PostgreSQL
and both Finind services stayed active, and no error-level line was logged afterwards. There was
no migration; transactions (69) and WhatsApp receipts (25) were unchanged. One household joined
through Google after the release (the first self-serve sign-up).

**Sarvam is not active in production.** The release adds no Sarvam setting, so speech stays on
OpenAI and Gemini until the human completes the dashboard steps and picks the voice (above).

**Frontend.** Vercel deployment `C8wHYhKMN3Cg6v15SjQAuA7cyvQ3` is Ready for main `21138dc` on
`finboy.antlegs.in`. The served privacy policy names Sarvam AI, and the live sign-in page at 1440 px
shows the large, centred QR code.

**Open issue: intermittent connection failures from Vercel's proxy.** Found while verifying; not
caused by this release, onset unknown. Through the proxy, 22 of 56 timed requests (39%, seven
runs) failed after about 31 s with Vercel's `502 ROUTER_EXTERNAL_TARGET_CONNECTION_ERROR`; 32 of 32
direct requests to the API from the same machine succeeded in about 0.1 s. On the host:
- the failed attempts never arrive. A header-only capture on port 443 showed no packets for them,
  not even SYN retries, while every connection that did arrive was answered;
- the successful proxied connections came from only two Vercel addresses (43.205.236.141 and
  65.2.125.144);
- the kernel reported no listen drops or overflows, there is no firewall or fail2ban, and the load
  was 0.09;
- DNS is a single A record (no AAAA); `nginx` listens on IPv4 only for 443.

The live effect is the sign-in page, and any app call, showing "FinBoy took too long to respond"
about four times in ten. It needs the VPS provider to check inbound filtering from AWS
`ap-south-1` addresses, or a different path between Vercel and the API. Do not call the site
healthy for real users until it is fixed.

**Still human acceptance:** phone voice notes in Malayalam, Hindi and English, playback of a
Malayalam reply, and a native read of the Malayalam copy (`malayalam.py`).

## Reply language and direct API release procedure

`feat/finboy-language-and-access`
([reply language](whatsapp.md#reply-language-29-october-2026), [direct API calls](#access-and-network)):

1. **Backend first,** following the steps above:
   - validated private backup and active-import check;
   - additive migration `0010_whatsapp_last_language`, which adds `last_language` and clears the
     stored reply languages;
   - drift check, then restart `finboy.service` only.

   Browsers see no change yet: CORS also allows credentials for the exact web origins.
2. **Web:** push main and Vercel builds. Then set Vercel's Production
   `NEXT_PUBLIC_API_URL=https://finboy-api.antlegs.in` and redeploy (`NEXT_PUBLIC_*` values are
   fixed at build time).
3. **Check:**
   - the sign-in page and Overview load every time, and the sidebar stays "Service available";
   - signing in with WhatsApp and Google works;
   - Review, Ask, quick add, an .eml upload and Gmail connect work;
   - a login code from a number with no history gets an English card.

**Rollback:** set `NEXT_PUBLIC_API_URL=/` and redeploy; the proxy path still works. Migration
`0010` is not rolled back (cleared languages are not restored).
