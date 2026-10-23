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
on the server and apply a documented retention/restore check.

Nginx configuration templates are in deploy/. Test nginx -t before reload. Use
Certbot webroot/HTTP challenge and a renewal deploy hook that reloads nginx only
after nginx -t. Confirm the certificate and unattended renewal with a dry run.

Gmail needs a new explicitly registered HTTPS callback on the deployed frontend:
/api/v1/connections/gmail/callback. Local callback registrations remain. Human handles
Google consent. Testing mode still expires refresh tokens after seven days.
Never claim production Gmail works until callback registration and live import pass.

Provider keys are reused privately without regenerating existing local credentials.
Production uses the real IST clock, not DEMO_TODAY. Synthetic demo mailbox remains
available through the same pipeline. Actual speech and all deferred WhatsApp voice,
microphone and Gmail acceptance limitations remain recorded in handoffs/agent-5.md.
