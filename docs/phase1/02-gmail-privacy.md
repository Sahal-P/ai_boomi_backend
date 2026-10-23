# Prompt 2 — A2: Gmail connector, import modes, and privacy (full stack)

You are **A2** on FinBoy Phase 1, working in parallel with three other agents. You own
getting email *in* (live Gmail, `.eml` upload, demo mailbox) and the trust layer
(disconnect, revoke, delete, audit). This request authorizes Phase 1 work defined in
`docs/phase1/contract.md`.

**Read first:** `AGENTS.md`, `docs/phase1/contract.md`, `README.md`,
`apps/web/AGENTS.md` (read the bundled Next.js docs before writing Next.js code).
Do not delegate to subagents.

**Workspace:** branch `phase1/a2-gmail` in your own git worktree. API 8002, web 3002,
database `finboy_a2` (contract §3). You only write files A2 owns (contract §4). A1's
`ingest_messages` is a stub on your branch: call it exactly per contract §6 and use test
doubles in your tests.

## Browser / Google Cloud setup (Chrome + gcloud; human does logins and consent)

1. Use `GOOGLE_CLOUD_PROJECT` from `~/.config/finboy/secrets.env`.
   `gcloud services enable gmail.googleapis.com`.
2. In Cloud Console → **Google Auth Platform**: Branding (app "FinBoy Dev", support
   email = the human's choice); Audience: **External, Testing**, add the demo Gmail
   account as a test user; Data access: `gmail.readonly` (plus `gmail.insert`, used only
   by the seeding tool below).
3. Create an OAuth client (**Web application**) with redirect URIs
   `http://127.0.0.1:8000/api/v1/connections/gmail/callback` and
   `http://127.0.0.1:8002/api/v1/connections/gmail/callback` (plus a loopback URI for
   the seeding tool if needed). Write the client id and secret to
   `~/.config/finboy/secrets.env` and your `apps/api/.env`, then delete any downloaded JSON.
4. Generate `TOKEN_ENCRYPTION_KEY` (Fernet) into the secrets file.
5. Write `docs/gmail-setup.md` (no secrets): every step, scopes, test-user caveat, and the
   **7-day refresh-token expiry in Testing mode** (reconnect before the demo).

## Build — backend

1. **OAuth**: `authorize` creates single-use state + PKCE S256 (store state hash and
   encrypted verifier in `oauth_states`, 10-minute expiry) and redirects with
   `access_type=offline`, `prompt=consent`, scope `gmail.readonly` only. `callback`
   validates state, exchanges the code (httpx or official Google library; mockable),
   checks the granted scope, reads the address via `users.getProfile`, stores masked
   email + sha256, encrypts the refresh token (Fernet), keeps access tokens in memory
   only, starts the first import, and redirects to `{WEB_APP_URL}/import/{run_id}`.
   Errors redirect to `/connect?error=<fixed code>`. Never log codes or tokens.
2. **Gmail fetch** (`services/mail/`): `messages.list` with a financial query
   (`after:` = `today_ist()` − 30 days, financial keywords and known sender domains,
   excluding social/promotions), pagination with caps; `format=raw` for candidates;
   429/5xx backoff; token refresh; on `invalid_grant` set status `error` so the UI can
   prompt reconnect. Count `headers_checked` and `candidates_found`.
3. **Import runs** (`services/imports/`): `POST /imports/demo` (reads `*.eml` from
   `apps/api/fixtures/demo_mailbox/`), `POST /imports/eml` (multipart, ≤ 50 files,
   ≤ 2 MB each, RFC 822 only, parsed in memory, never written to disk),
   `POST /connections/{id}/sync`. All create an `import_runs` row and run
   `ingest_messages` in `BackgroundTasks`, updating counters through `on_progress`
   (own session per update). Failures set `failed` + a fixed `error_code`, never
   exception text. `GET /imports/{id}` returns progress.
4. **Privacy** (`services/privacy/`): list connections; pause/resume; disconnect =
   revoke at Google (token in POST body, not URL) → wipe the encrypted token → status
   `revoked` → optional data deletion; `DELETE /privacy/imported-data` removes
   email-derived ledger data (email_sources → source_events → orphaned transactions
   and commitments) and keeps audit events; `GET /privacy/audit-events`. Write
   allowlisted audit events for every connect, sync, revoke, and delete.
5. **Demo inbox seeder:** `pnpm seed:gmail-demo-inbox` runs its own one-time OAuth with
   `gmail.insert` only and inserts the rendered demo `.eml` files into the demo Gmail
   account (`users.messages.insert`, `internalDateSource=dateHeader`, INBOX label),
   idempotent by Message-ID. The app itself never requests `gmail.insert`. Until A1's
   fixtures land, test with 3 small synthetic emails.

## Build — frontend (presentational components; data in `lib/api/mail.ts` + hooks)

- `/connect`: the report's onboarding copy ("Your money already leaves a trail…") and
  three modes: **Connect Gmail** (top-level navigation to the authorize URL), **Upload
  .eml files**, **Load demo mailbox**. Show `?error=` codes as friendly text.
- `/import/[runId]`: polls every 1 s and shows the live checklist ("✓ 126 email headers
  checked · ✓ 38 possible financial emails · ✓ 31 transactions extracted · ✓ 4
  duplicates merged · ! 2 need your confirmation"), then CTAs to `/dashboard` and `/review`.
- `/privacy`: connected account (masked email, last scan), Pause, Disconnect (dialog:
  keep ledger vs delete imported records), Delete imported data (confirm dialog), audit
  list, plain statements of what is stored, what is not, and that financial emails are
  never used to train models.

## Design system

The UI is a light, 3D, premium system (docs/design-system.md, live at `/styleguide` in
dev). Build your screens from its tokens, `components/ui` primitives, motion primitives
and `<SceneSlot>` scenes; do not add colours, shadows, fonts, animation libraries or WebGL
canvases of your own. The app shell, landing page and primitives belong to D.
Suggested scenes: `inbox-slab` on /connect, `coin-swirl` (`loop`) while an import runs, `privacy-vault` on /privacy.

## Done when

- Live flow works in Chrome with the demo Gmail account: connect → consent → import
  run → progress screen (the human clicks through Google's consent and "unverified
  app" screens). Disconnect revokes the grant (confirm at myaccount.google.com/permissions).
- Demo and `.eml` modes produce import runs through the same entry point.
- Tests with mocked Google HTTP: state/PKCE (expired, reused, tampered), scope check,
  encryption round-trip, callback errors, revoke, upload limits and types, progress,
  deletion, CORS for POST/DELETE, and no tokens/codes/emails in logs or responses.
- `/connect`, `/import`, `/privacy` checked at 1440×1000 and 390×844, including loading,
  error, and offline states. `pnpm check` and `pnpm build` pass.

**Final report:** commands + real outcomes, setup state (no secret values), screenshots
taken, cross-boundary edits, new dependencies, known gaps.
