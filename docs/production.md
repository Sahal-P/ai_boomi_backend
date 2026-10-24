# Authorized private production deployment

The human authorized GitHub publication, main integration, Vercel frontend and
voxpay backend on 24 October 2026, then chose private single-household access and
an antlegs.in subdomain. This supersedes the old prohibition on production for
this deployment only. Public multi-user signup is not implemented.

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
