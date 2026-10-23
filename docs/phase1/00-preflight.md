# Prompt 0 — Phase 1 pre-flight scaffold (run ALONE, before the 4 parallel agents)

You are the integrator for FinBoy Phase 1. Your job is a fast, precise scaffold so four
agents can then work in parallel without touching the same files. Target: ~45 minutes.
Do not implement features. This request authorizes Phase 1 scope as defined in
`docs/phase1/contract.md`, superseding the Phase 0 limits in `AGENTS.md`.

Read first: `AGENTS.md`, `README.md`, `docs/architecture.md`, `docs/phase1/contract.md`
(the source of truth), and `apps/web/AGENTS.md` (read the bundled Next.js docs before
writing Next.js code).

## Steps

1. **Baseline commit.** The repo has no commits. Confirm `git status` shows no env
   files or secrets staged (`.env`, `apps/api/.env`, `apps/web/.env.local` must be
   ignored). Commit everything as-is on `main`: "Phase 0 foundation".
2. **AGENTS.md → Phase 1.** Replace the Phase 0 scope bullet with: Phase 1 builds what
   `docs/phase1/contract.md` defines; everything in its out-of-scope list still needs a
   new request. Change the frontend rule to "backend communication and runtime
   validation live in `apps/web/src/lib/api/` (one module per domain, shared helper in
   `http.ts`)". Add a "Parallel work" section: follow the contract's ownership table,
   ports, per-agent databases, never stop the shared Postgres container, secrets only
   in `~/.config/finboy/secrets.env` and gitignored env files. Keep every other rule.
3. **Settings** (`core/config.py`) + `apps/api/.env.example` placeholders (blank values,
   comments, no secrets): `OPENAI_EXTRACTION_MODEL`, `OPENAI_ASSISTANT_MODEL`,
   `OPENAI_TRANSCRIBE_MODEL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
   (SecretStr), `GOOGLE_OAUTH_REDIRECT_URI`, `GOOGLE_CLOUD_PROJECT`, `TOKEN_ENCRYPTION_KEY`
   (SecretStr, Fernet key), `WEB_APP_URL` (must be one of the CORS origins), `DEMO_TODAY`
   (optional date, ignored in production). Add `core/clock.py` with `today_ist()` and
   `now_ist()` per contract §6. Add unit tests for validation and the clock.
4. **CORS + logging.** Allow methods GET, POST, PATCH, DELETE, OPTIONS (still explicit
   origins, no credentials). Add allowlisted log fields: `import_run_id`, `stage`,
   `count`, `provider`, `outcome`, `model`, `latency_ms`. Update existing tests.
5. **Dependencies (once, so agents don't fight over lockfiles).** API:
   `uv add --package finboy-api openai cryptography python-multipart httpx google-auth`
   (stable releases; check versions against official docs). Web:
   `pnpm --filter @finboy/web add zod`, then
   `pnpm --filter @finboy/web exec shadcn add card badge dialog alert-dialog sheet tabs input textarea label select separator skeleton progress alert tooltip sonner table switch scroll-area dropdown-menu radio-group checkbox`.
6. **Schema.** Create `db/models/` as a package: `core.py` (User), `ledger.py` (A1 tables),
   `mail.py` (A2 tables), `__init__.py` importing all; import it in `alembic/env.py`.
   Implement every table, column, FK, check constraint, unique constraint, and index
   from contract §5 with SQLAlchemy 2 typed mappings (useful indexes: user_id +
   occurred_at, user_id + status, fingerprint, reference_id). Write migration
   `0002_phase1` (down_revision `0001_phase0`), reviewed by hand, which also seeds the
   local user. Run `pnpm db:migrate`, `pnpm db:check`, `pnpm test:integration`.
7. **Backend stubs.** Create router modules `api/v1/{connections,imports,privacy,assistant,money,transactions}.py`,
   each an empty `APIRouter` with tags, all registered in `api/router.py`. Create
   `services/ingestion/pipeline.py`, `services/ledger/reconcile.py`, and
   `services/money/engine.py` with the exact signatures, dataclasses, and Pydantic
   models from contract §6 (bodies `raise NotImplementedError`). Add empty packages
   `services/{mail,imports,privacy,assistant,speech}/__init__.py`.
8. **Frontend scaffold.** Move the health client to `web/lib/api/health.ts` and the
   shared fetch logic to `web/lib/api/http.ts` (`requestJson` with zod, 5 s timeout,
   `credentials: "omit"`, `ApiError`; keep or port the existing tests, update the test
   script). Create `web/app/(app)/layout.tsx` with a minimal accessible nav (Dashboard,
   Transactions, Review, Assistant, Connect, Privacy) and placeholder pages for
   `/dashboard`, `/transactions`, `/review`, `/assistant`, `/connect`, `/privacy`,
   `/import/[runId]` (one heading each). Keep the landing page working.
9. **Scripts.** In root `package.json`: make ports configurable
   (`--port ${API_PORT:-8000}` for the API, `--port ${WEB_PORT:-3000}` for web) and add
   `eval:extraction` → `python -m finboy.services.ingestion.evaluate`,
   `demo:render-mailbox` → `python -m finboy.services.ingestion.render_demo_mailbox`,
   `seed:fixture-ledger` → `python -m finboy.services.money.seed_fixture_ledger`,
   `seed:gmail-demo-inbox` → `python -m finboy.services.mail.seed_demo_inbox`,
   `voice:benchmark` → `python -m finboy.services.speech.benchmark`
   (all via `uv run --package finboy-api`). Add `apps/api/fixtures/` to the docs.
10. **Docs.** Update `README.md` (Phase 1 status, new env vars, scripts, parallel setup
    pointer) and `docs/architecture.md` (Phase 1 boundaries, diagram). Keep it short.
11. **Verify and commit.** `pnpm check`, `pnpm build`, `pnpm db:check`,
    `pnpm test:integration` must pass. Commit on `main`: "Phase 1 scaffold: contracts,
    schema, stubs". Do not push unless asked.

## Final report

List commands run with real outcomes, the commit hashes, anything in the contract you
had to change (and why — update `contract.md` to match), and confirm no secrets are
tracked (`git ls-files | grep -E '\.env$|secrets'` returns nothing).
