# Gmail, imports, and privacy — local Phase 1

FinBoy runs locally with one seeded user. This is not product login or a multi-user
OAuth deployment. Use the Phase 1 ports and database in `phase1/contract.md`.
For A2: API `127.0.0.1:8002`, web `127.0.0.1:3002`, database `finboy_a2`.

## Private configuration

Keep credentials only in `~/.config/finboy/secrets.env` and the gitignored backend
`apps/api/.env`. The secrets directory must be mode 700, both files mode 600.
Never commit credential JSON, `.env`, tokens, personal mailbox content, or screenshots
of credentials. Delete downloaded OAuth client JSON after copying its values.

Required backend settings:

```dotenv
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_OAUTH_CLIENT_ID=<web-client-id>
GOOGLE_OAUTH_CLIENT_SECRET=<web-client-secret>
TOKEN_ENCRYPTION_KEY=<generated-fernet-key>
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8002/api/v1/connections/gmail/callback
WEB_APP_URL=http://127.0.0.1:3002
CORS_ORIGINS=["http://127.0.0.1:3002","http://localhost:3002"]
```

Generate a Fernet key using `cryptography.fernet.Fernet.generate_key()` and write it
directly to the private files, without printing it. Preserve this key across restarts;
changing it makes stored refresh tokens unreadable. Access tokens never persist.
Set the API database name to `finboy_a2`, retaining the development database role.
Set `apps/web/.env.local` to `NEXT_PUBLIC_API_URL=http://127.0.0.1:8002`.
Use `127.0.0.1:3002` for the live OAuth flow so callback and browser hosts agree.

## Google Cloud setup

1. The human signs in to the intended Chrome profile and runs `gcloud auth login`.
   Ensure that CLI identity has access to the selected Cloud project. Read the
   project ID from the private `GOOGLE_CLOUD_PROJECT` setting.
2. Enable the Gmail API with
   `gcloud services enable gmail.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"`.
   An account mismatch or missing Service Usage permission must be resolved by the
   human; do not silently switch to a different project.
3. In **Google Auth Platform → Branding**, name the app **FinBoy Dev**. The human
   chooses the support and developer contact email. Save the branding setup.
4. In **Audience**, choose **External**, keep publishing status **Testing**, and add
   the demo Gmail address under **Test users**. Only listed test users can authorize.
5. In **Data Access**, configure `gmail.readonly` for the application and
   `gmail.insert` for the separately invoked demo inbox seeder. The application's
   authorize route requests **only**
   `https://www.googleapis.com/auth/gmail.readonly`.
6. In **Clients**, create a **Web application** OAuth client. Add these authorized
   redirect URIs exactly (scheme, hostname, port, and path must match):
   - `http://127.0.0.1:8000/api/v1/connections/gmail/callback`
   - `http://127.0.0.1:8002/api/v1/connections/gmail/callback`
   - `http://127.0.0.1:8767/callback` (seeding tool only)
7. Copy the client ID and secret directly into the private files. Delete any
   downloaded credential JSON. No OAuth client credentials belong in public web
   variables. The human performs Google login, consent, and any unverified-app steps.
8. Restart the API after changing settings. Open `/connect`, choose **Connect Gmail**,
   and complete consent. The callback redirects to `/import/{run_id}`. Reconnect
   when the connection shows an error or Google returns `invalid_grant`.

**Testing-mode refresh tokens expire after seven days** for these Gmail scopes.
Reconnect before the demo. Do not publish the app to Production just to avoid expiry.
See Google's [OAuth token-expiration rules](https://developers.google.com/identity/protocols/oauth2#expiration)
and [web-server OAuth guide](https://developers.google.com/identity/protocols/oauth2/web-server).

## Seed the demo inbox

Render A1's synthetic mailbox first:

```sh
pnpm demo:render-mailbox --anchor 2026-10-28
pnpm seed:gmail-demo-inbox
```

The seeder opens a one-time, PKCE-protected consent for **gmail.insert only**, listens
on `127.0.0.1:8767`, and inserts only messages marked `X-FinBoy-Synthetic: 1` with a
Message-ID. It sets `internalDateSource=dateHeader` and the `INBOX` label. It stores
no OAuth token. Run it before connecting FinBoy; use the demo Gmail account at consent.
If Google combines previously granted scopes, revoke the previous FinBoy grant in
Google Account permissions and start the narrow-scope flow again.

Successful Message-ID hashes go into private
`~/.config/finboy/gmail-seed-manifest.json`. Re-running with the same client and
`--mailbox-label demo` skips those IDs. Use a distinct stable label for a different
demo account. **Insert-only scope cannot list or search Gmail**; therefore idempotency
uses this local manifest. Keep it. An uncertain network failure after Google accepted
an insertion cannot be reconciled with insert-only access. The seeder never retries
insertion requests automatically; inspect the demo inbox before rerunning after an
uncertain failure. This limitation follows the
[insert API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/insert)
and [list API scopes](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list).

While A1's fixture renderer is pending, tests use three small synthetic emails.
`uv run python apps/api/tests/mail/browser_fixtures.py` creates three `.eml` inputs
under the system temporary directory and clearly synthetic connection/progress rows
in **finboy_a2 only**. Those rows are UI test doubles, not a real Gmail grant or
extraction result. The seeder also accepts `--directory /absolute/fixture/path`.

## Import behavior and privacy

- Gmail uses an IST date window of `today_ist() - 30 days`, financial keywords and
  known sender domains, and excludes Social and Promotions. It checks candidate
  metadata before fetching raw content. Caps: ten list pages, 500 candidates, and
  2 MB per message. Header counts describe the matched candidates, not the entire inbox.
  HTTP 429/5xx and transient reads use bounded exponential backoff; expired access
  tokens refresh in memory. `invalid_grant` marks the connection `error`.
- Demo reads rendered `apps/api/fixtures/demo_mailbox/*.eml`. Upload accepts 1–50
  RFC 822 `.eml` files, up to 2 MB each. The multipart parser buffers in memory,
  rejects malformed/truncated requests, and never uses a disk spool. Browser uploads
  may use `message/rfc822` or `application/octet-stream`; content is parsed regardless.
- All modes create an `import_runs` row and call A1's `ingest_messages` interface in
  FastAPI BackgroundTasks. Each progress update opens its own session. The counters
  are cumulative and never decrease. Only the contract's fixed error codes persist.
- One import is admitted at a time for the local user. A database advisory lock
  prevents privacy deletion from racing pipeline commits. If a scan is running,
  wait or pause it, then retry disconnect/delete. Pause is checked between messages.
- BackgroundTasks are not a durable queue. Restarting the process interrupts work;
  Phase 1 does not resume imports automatically. A new import marks an abandoned
  run failed when no worker holds the advisory lock (queued jobs have a 30-second
  admission grace period). Raw upload bytes cannot be replayed.
- Disconnect posts the token in Google's revocation request **body**, then wipes
  the encrypted refresh token and marks the connection revoked. A provider failure
  retains the encrypted token so revocation can be retried. Already-invalid grants
  are treated as revoked. Optional deletion affects that connection's sources.
- Delete removes sources, their events and dependent commitments, orphaned
  transactions/revisions, and extraction cache. Transactions with another remaining
  source and manually created records remain. Self-links and payment links are cleared
  before deletion. Operational import counters and audit history remain.
- Audit metadata has a strict allowlist. No raw bodies, subjects, amounts, merchants,
  full account addresses, authorization codes, access tokens, or refresh tokens enter
  responses or logs. Only a masked account label and address SHA-256 persist.
- Financial emails are never used to train models. Relevant content can be processed
  by the backend extraction provider. The app keeps structured records and evidence
  snippets of at most 80 characters per field; A1 owns extraction and retention there.

To verify revocation, disconnect in `/privacy`, then have the human check
[Google Account connections](https://myaccount.google.com/permissions). FinBoy's grant
should no longer have Gmail access. Reconnecting after this starts a fresh consent.

## Validation and handoff

Run from the A2 worktree:

```sh
uv sync --locked --all-packages
pnpm install --frozen-lockfile
pnpm check
pnpm build
pnpm db:migrate
pnpm db:check
pnpm test:integration
API_PORT=8002 WEB_PORT=3002 pnpm dev
```

Mocked Google HTTP tests cover PKCE/state expiry/reuse/tampering, cookie binding,
scope checks, encrypted token storage, callback failures, refresh and pagination,
retry/caps, revocation, three-message seeding idempotency, uploads, progress, deletion,
audit redaction, and POST/DELETE CORS. SQLite is a unit-test double only. PostgreSQL
integration exercises deletion with real foreign keys and advisory-lock exclusion in
a rolled-back transaction. Browser verification must distinguish synthetic fixture
states from human-authorized live Gmail results. A1's unimplemented pipeline stub
correctly produces `failed / import_failed` until its implementation is merged.

### A2 verification observed on 23 October 2026

- `uv sync --locked --all-packages` and `pnpm install --frozen-lockfile`: passed.
- `pnpm check`: passed, including 92 backend unit tests and 10 web client tests,
  Ruff, ESLint, and strict TypeScript checks.
- `pnpm build`: passed; `/connect`, `/import/[runId]`, and `/privacy` compiled.
- `pnpm db:migrate`: passed against local `finboy_a2`, at `0002_phase1`.
- `pnpm db:check`: passed, no schema drift. No A2 schema migration was needed.
- `pnpm test:integration`: six passed, including source/ledger deletion under real
  PostgreSQL foreign keys and exclusion by the advisory lock. Test writes rolled back.
- Three synthetic `.eml` files submitted to the running API returned 202 and created
  an `eml_upload` run. It subsequently failed with the fixed `import_failed` code
  because A1's pipeline is still a stub on this branch.
- Chrome: `/connect`, `/import`, and `/privacy` checked at 1440×1000 and 390×844.
  Twenty screenshots cover the mode picker, OAuth error, loading, completed fixture
  checklist, active synthetic connection, disconnect/delete dialogs, and API timeout
  states. Pause/resume round-tripped through the real API and wrote audit events.
  Synthetic account/progress rows were removed afterward; audit events were retained.
- Browser upload automation was blocked by Chrome extension file access. The API
  upload path and file limits/types were verified separately. Enable **Allow access
  to file URLs** for the ChatGPT extension before repeating the browser file-picker
  test. No Chrome privacy settings were weakened during verification.
- No cross-boundary edits or new dependencies. The existing pre-flight packages
  provide httpx, cryptography, python-multipart, zod, and Radix primitives.

### External setup state at this checkpoint

The human completed Google Cloud SDK login with the requested account. Enabling
`gmail.googleapis.com` succeeded, and an explicit enabled-services query confirmed
it. The configured Cloud project is active. The Fernet key is present in the private
secrets file and A2 backend env; the secrets file is mode 600.

The human completed OAuth registration for **FinBoy Dev** with the chosen support
and contact address. Audience is **External / Testing**, and the chosen demo Gmail
account is saved as a test user. Data Access contains exactly `gmail.readonly` and
`gmail.insert`; the application's authorization URL requests only `gmail.readonly`.

The **FinBoy Dev local web** client was created with all three loopback callbacks
listed above. Its client ID and secret are in the private secrets file and A2 API
env, both mode 600. Two downloaded JSON copies were verified against those saved
credentials and callback URIs, then deleted. macOS blocked terminal access to Downloads;
Finder moved just those files into the private folder for verification and cleanup.
The initial Cloud Console loading problem resolved after project selection and
releasing Chrome's debugging connection; native controls completed the configuration.

The running API now returns a 307 to Google from the authorize endpoint, with an
HttpOnly state cookie and `Cache-Control: no-store`. The human completed insert-only
seeder consent and `pnpm seed:gmail-demo-inbox --directory <synthetic-inputs>` inserted
three synthetic messages successfully. The private manifest has three Message-ID
hashes and mode 600. A live callback issue exposed during this check was fixed: the
temporary receiver now waits for a validated callback, tolerating incidental browser
connections and favicon requests; six focused tests cover that behavior.

The human completed the application's separate read-only consent in Chrome. The
callback created an active connection with exactly `gmail.readonly`, a masked email,
and an encrypted refresh token, then redirected to a persisted Gmail import run.
That run correctly stopped at A1's current `NotImplementedError` stub with the fixed
`import_failed` code; no extraction completion or financial totals are claimed.

A separate live invocation of A2's Gmail fetch adapter refreshed the token and
fetched three matched raw candidates in memory; scan counts reached 3 headers and
3 candidates. No raw content was written to disk or printed. The actual progress
and connected Privacy screens were captured at 1440×1000 and 390×844.

Disconnect was then exercised through the real Privacy dialog with **Keep my
ledger** selected. It succeeded, marked the connection `revoked`, wiped the encrypted
refresh token, and wrote the audit event. Google rejected an attempted refresh with
the old token, which was held only in the verifier process's memory. Searching
`FinBoy` at Google Account's linked-apps/permissions page returned **No results
found**. The revoked Privacy state was also captured at both viewport sizes.

The final local connection is intentionally revoked after this verification.
Reconnect before the demo. A1's pipeline and fixture merge still remain necessary
for successful extraction and the full rendered demo mailbox. The upload API and
three-message demo entry point are tested with A1 interface doubles; the browser
file-picker test remains limited by the Chrome extension setting described above.
