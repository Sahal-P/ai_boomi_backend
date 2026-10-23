# Phase 1 pre-flight verification

Verified **23 October 2026 (IST)** on macOS arm64, Python 3.15.1, Node 26.8.1,
pnpm 12.15.0, and Docker PostgreSQL 18.6. This run stayed serial and on `main`.
The clean repository already had baseline `f640c08cd4acdad41d1b49ca8f896142679ced94`
(`phase 0`); it was preserved rather than creating a duplicate baseline commit.

## Commands and actual outcomes

| Command | Outcome |
| --- | --- |
| `git status --short` / `git log -1` | Initially clean on main; existing Phase 0 baseline |
| `git check-ignore .env apps/api/.env apps/web/.env.local` | All three ignored |
| `uv add --package finboy-api openai cryptography python-multipart httpx google-auth` | Passed; added runtime dependencies and updated uv.lock |
| `pnpm --filter @finboy/web add zod` | Passed; zod 4.6.7 recorded in package and lockfile |
| `pnpm --filter @finboy/web exec shadcn add card badge dialog alert-dialog sheet tabs input textarea label select separator skeleton progress alert tooltip sonner table switch scroll-area dropdown-menu radio-group checkbox --yes` | First request timed out; IPv4-first retry reached registry but prompted for existing button |
| Same shadcn command with `NODE_OPTIONS=--dns-result-order=ipv4first` and `--overwrite` | Passed; all 22 requested components present; original button restored to preserve landing UI |
| `open -a Docker` / `pnpm db:up` | Started the stopped daemon; shared Postgres healthy; never stopped the container |
| Alembic `revision --autogenerate --rev-id 0002_phase1` | Generated then reviewed/edited by hand: seeded Arun and finalized constraints |
| `docker compose exec -T postgres createdb -U finboy <test-db>` | Created disposable local migration databases |
| `DATABASE_URL=<local test-db URL> pnpm db:migrate` | Final migration passed from empty DB `finboy_preflight_verified`; revision 0002_phase1 |
| Same override + `pnpm db:check` / `pnpm test:integration` | No schema drift; 5 integration tests passed on the fresh final schema |
| `pnpm db:migrate` / `pnpm db:check` / `pnpm test:integration` | Default local finboy migrated; no schema drift; 5 tests passed |
| `uv sync --locked --all-packages` | Passed; lockfile/workspace reproducible |
| `pnpm install --frozen-lockfile` | Passed; package/lockfile consistent |
| `pnpm check` | Passed: Ruff lint/format, ESLint, 42 backend unit tests, 10 client tests, strict TypeScript |
| `pnpm build` | Passed: landing + six static app pages + dynamic import route |
| `API_PORT=8010 ... pnpm dev:api` / `WEB_PORT=3010 ... pnpm dev:web` | Both configurable ports worked, with explicit CORS and public API URL overrides |
| `git diff --check` | Passed |
| `git ls-files | grep -E '\.env$|secrets'` | No matching tracked paths (grep exit 1 is expected) |

During development, a test assertion matched the newly added setting name
`client_secret` rather than a leaked password; the assertion now checks a distinct
synthetic password. Generated Sonner code also failed exact optional property
checking; runtime theme narrowing fixed it without an unchecked theme assertion.
A new fresh-database test caught the missing fixed-code check in an intermediate
migration draft. It was added to 0002, then the entire upgrade was rerun on a new
empty database. The earlier default local trial received the same additive check
via SQLAlchemy `AddConstraint`; no destructive migration or downgrade was used.
Earlier test DBs `finboy_preflight` and `finboy_preflight_final` remain local trial
schemas; use `finboy_preflight_verified` for the final disposable schema.

Installed runtime versions: openai 3.37.0, cryptography 50.0.2,
python-multipart 0.0.32, httpx 0.28.1, google-auth 2.62.0; shadcn also added
next-themes 0.4.6 and sonner 2.0.8. Installation/API guidance checked against
[OpenAI SDK docs](https://developers.openai.com/api/docs/libraries),
[cryptography](https://cryptography.io/en/latest/installation/),
[Google Auth](https://github.com/googleapis/google-auth-library-python),
[HTTPX](https://www.python-httpx.org/),
[python-multipart](https://github.com/Kludex/python-multipart),
[zod](https://zod.dev/), and [shadcn CLI](https://ui.shadcn.com/docs/cli).
No model IDs were guessed or provider calls made.

## Browser outcomes

- In-app browser inspected at desktop 1440×1000 and mobile 390×844. App navigation
  wraps without overflow; measured mobile document and viewport widths both 390.
- Dashboard, Transactions, Review, Assistant, Connect, Privacy, and the dynamic
  import route rendered the expected single heading. Navigation links worked.
- Keyboard Tab reached the visible skip link; Enter focused `main-content`.
- Existing landing remained intact. Actual API/CORS requests showed connected;
  manual refresh and the 30-second refresh both reached the backend.
- Checking, connected, degraded, and offline states were observed at both widths.
  A temporary ASGI wrapper outside the repo delayed health by two seconds to make
  checking visible. A separate API pointed at unused local DB port 1 to produce
  degraded; stopping only that API produced offline. Shared Postgres stayed up.
- Screenshots were inspected in tool output. Temporary browser sizing was reset,
  the verification tab closed, and verification web/API processes stopped.
- A non-blocking existing Next.js smooth-scroll attribute hint appeared in dev;
  root landing layout/style behavior was left unchanged.

## Contract clarifications and limits

Updated contract §6 to define missing supporting model fields, PeriodSpec,
confidence serialization, simulation signs/keys, model placement/nullability and
defaults, fixed import error codes, optional blank settings, real audit clock,
and health-specific status schemas. The Phase 1 scope and demo totals did not
change. These details avoid incompatible implementations by the four later agents.

No domain features, external provider integration, or synthetic mailbox/voice
fixtures were implemented. Domain service bodies raise NotImplementedError;
empty routers expose no domain endpoints. Evaluation/render/seed/benchmark scripts
are wired to modules their owners will implement and were not executed. No remote
push, worktree creation, or subagents were used. No env files or secret files are
tracked; examples contain only blank integration values and public local settings.

---

# Phase 0 verification

Verified locally on **23 October 2026 (IST)** using macOS arm64, Python 3.15.1,
Node.js 26.8.1, pnpm 12.15.0, and Docker PostgreSQL 18.6.

## Commands and outcomes

| Command | Outcome |
| --- | --- |
| `uv sync --locked --all-packages` | Passed; Python lockfile and workspace install reproducible |
| `pnpm install --frozen-lockfile` | Passed; JavaScript lockfile install reproducible |
| `pnpm env:setup` | Passed; created local files initially and preserved all three on rerun |
| `pnpm db:up` | Passed; Compose service healthy, bound to `127.0.0.1:5433` |
| `pnpm db:migrate` | Passed; baseline revision applied to PostgreSQL |
| `pnpm db:current` | `0001_phase0 (head)` |
| `pnpm db:check` | Passed; no new upgrade operations / schema drift |
| `pnpm check` | Passed; Ruff lint + formatting, ESLint, 17 backend unit tests, 5 frontend client tests, strict TypeScript |
| `pnpm test:integration` | Passed; 2 tests against real PostgreSQL and HTTPX ASGI health |
| `pnpm build` | Passed; optimized Next.js production build, static landing and icon |
| `pnpm start:web` | Passed; production frontend served on port 3000 |
| `pnpm dev:api` | Passed; FastAPI startup, health requests, and clean shutdown |
| `pnpm dev` | Passed; API and web started together, reload enabled |
| `pnpm peers check` | No peer dependency issues |

The backend unit tests use HTTPX's direct `ASGITransport` with the application
lifespan. They cover readiness, database failure, generated request IDs, OpenAPI,
CORS, redacted HTTP/validation/unexpected errors, the HTTP 405 `Allow` header,
settings validation, and log privacy. They do not require a running database.

The five client tests cover request options, a valid degraded response, malformed
or inconsistent payloads, unexpected HTTP/non-JSON responses, and network failure.

## Live browser checks

- Production and development landing pages rendered successfully.
- The browser called the actual FastAPI endpoint and displayed **Connected to
  FinBoy**, **API connected**, and **PostgreSQL connected**.
- Both `http://127.0.0.1:3000` and `http://localhost:3000` passed the real CORS flow.
- Desktop at 1440 × 1000, mobile at 390 × 844, and small mobile at 320 × 740:
  layout inspected, content fit, and document width matched viewport width.
- The refresh button made a live request; periodic refresh was observed.
- After `docker compose stop postgres`, the API returned `503` with the safe
  degraded contract and the page showed **Database unavailable**, **API connected**,
  and **PostgreSQL unavailable**.
- After `pnpm db:up`, the same running API and browser recovered to connected.
- After stopping the verification API, the page showed **Backend is offline**,
  **API unreachable**, and **PostgreSQL unknown** while the landing shell remained
  usable. Starting `pnpm dev` restored the healthy state.
- Temporary browser viewport overrides were reset after responsive checks.

Healthy response observed:

```json
{"status":"ok","service":"finboy-api","version":"0.1.0","database":"connected"}
```

PostgreSQL contains only the `alembic_version` table at this phase. No application
data was created. Environment files and generated dependency/build directories
were confirmed ignored by Git.

## Scope

Phase 0 only. No authentication, transaction capture, AI extraction, WhatsApp,
ledger, dashboards, forecasting, or OpenAI integration was implemented. No remote
deployment or hosted production environment was part of this verification.
