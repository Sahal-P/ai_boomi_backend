# FinBoy

An AI-powered personal finance copilot for Indian users. This repository contains
the **Phase 1 scaffold**: reviewed schema, shared service contracts, empty domain
routers, and placeholder app pages. The landing page and live health check work;
Gmail, ingestion, ledger calculations, voice, and product UX await their owners.
The source of truth is [the Phase 1 contract](docs/phase1/contract.md).

## Stack

- Python 3.15.1, FastAPI, Pydantic v2 / pydantic-settings, uv
- Next.js 16.4.2 App Router, React 19.3, strict TypeScript, Tailwind CSS 4
- shadcn/ui (Radix Nova), Lucide, locally served Geist variable font
- PostgreSQL 18.6, SQLAlchemy 2.1, psycopg 3, Alembic
- Ruff, pytest + HTTPX ASGI transport, ESLint 10, Node's built-in test runner

Exact dependency versions are recorded in `uv.lock` and `pnpm-lock.yaml`.
TypeScript 6.0.3 is the current stable compiler line supported by typescript-eslint;
TypeScript 7 is intentionally deferred until that parser supports it.

## Prerequisites

- Node.js **24 LTS** recommended (`.node-version`); Node 22.18–26 is supported.
- **pnpm 12.15.0**, pinned in `package.json`. Install using the
  [official pnpm instructions](https://pnpm.io/installation), or use Corepack if
  available: `corepack prepare pnpm@12.15.0 --activate`.
- A current [uv installation](https://docs.astral.sh/uv/getting-started/installation/).
  uv installs the pinned Python interpreter. If an older uv cannot find Python
  3.15.1, upgrade uv through the package manager that installed it.
- Docker Desktop / Docker Engine running with the Compose v2 plugin.

## First run

Run from the repository root:

```sh
uv python install
uv sync --locked --all-packages
pnpm install --frozen-lockfile
pnpm env:setup
pnpm db:up
pnpm db:migrate
pnpm dev
```

`pnpm env:setup` copies the three environment examples to their local counterparts
with private file permissions. It preserves files that already exist. The example
values work together without editing; they are public local development values.

Open [FinBoy](http://127.0.0.1:3000). The connection panel calls FastAPI directly
from the browser and checks PostgreSQL, on load, on manual refresh, and every
30 seconds. The page remains usable if the API or database is unavailable.

- Web: <http://127.0.0.1:3000> (also accessible as `localhost:3000`)
- API health: <http://127.0.0.1:8000/api/v1/health>
- Interactive API docs: <http://127.0.0.1:8000/docs>
- PostgreSQL: `127.0.0.1:5433`, database/user `finboy`

All services bind to loopback. PostgreSQL uses port 5433 to avoid an existing local
server on 5432. Ctrl+C stops the development servers. `pnpm db:down` stops
PostgreSQL and preserves the named data volume.

## Environment

| File | Purpose |
| --- | --- |
| `.env` | Compose: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` |
| `apps/api/.env` | Backend: database, CORS, clock, and optional integration settings (below) |
| `apps/web/.env.local` | Public frontend setting: `NEXT_PUBLIC_API_URL` |

The API loads its `.env` from `apps/api` regardless of the current directory.
Process environment variables take precedence. `DATABASE_URL` must use the
`postgresql+psycopg://` scheme. `CORS_ORIGINS` is a JSON array of exact origins.
Both `localhost:3000` and `127.0.0.1:3000` are allowed by the example.

Integration placeholders are blank in `apps/api/.env.example` and optional until
features are enabled. `OPENAI_API_KEY`, `OPENAI_EXTRACTION_MODEL`,
`OPENAI_ASSISTANT_MODEL`, and `OPENAI_TRANSCRIBE_MODEL` configure the backend SDK;
no API calls are implemented in the scaffold. Verify model IDs in official docs.
`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
`GOOGLE_OAUTH_REDIRECT_URI`, and `GOOGLE_CLOUD_PROJECT` configure Google services.
`TOKEN_ENCRYPTION_KEY` must be a valid Fernet key when set. Secrets are masked types.
`WEB_APP_URL`, when set, must match an exact CORS origin. `DEMO_TODAY` is an optional
ISO date for business dates in IST and is ignored in production; real timestamps
always use the actual clock. Keep secrets in `~/.config/finboy/secrets.env` (chmod
600) and gitignored env files; setup does not read that secrets file automatically.

 Never put secrets into `NEXT_PUBLIC_*`: Next.js embeds
those values into browser JavaScript at **build time**. Restart development or
rebuild production after changing the public API URL.

If changing the database user, password, database, or port, update both the root
Compose settings and the backend URL. PostgreSQL initialization variables apply
only when the volume is first created; changing `.env` does not modify existing
database roles. Stop the service before changing its host port.

## Development commands

| Command | Purpose |
| --- | --- |
| `pnpm dev` | Run API and web together; stop both if either exits |
| `pnpm dev:api` / `pnpm dev:web` | Run one server; `API_PORT` / `WEB_PORT` default to 8000 / 3000 |
| `pnpm db:up` / `pnpm db:down` | Start / stop local PostgreSQL, keeping data |
| `pnpm db:migrate` | Apply Alembic migrations to head |
| `pnpm db:current` / `pnpm db:check` | Show revision / check ORM schema drift |
| `pnpm check` | Backend/frontend lint, unit tests, frontend type checks |
| `pnpm test:api` / `pnpm test:web` | Backend unit tests / typed health-client tests |
| `pnpm test:integration` | Local disposable PostgreSQL schema/constraint tests (writes roll back) |
| `pnpm lint:api` / `pnpm lint:web` | Ruff lint + format check / ESLint |
| `pnpm format:api` | Format Python sources and tests |
| `pnpm typecheck` | Generate Next route types, then run strict TypeScript checks |
| `pnpm build` / `pnpm start:web` | Build / serve the production frontend |

Backend unit tests require no running database. Integration tests require a local
disposable database with migrations applied; synthetic constraint probes roll back.
The shared Compose container must stay running during parallel work.
Follow [parallel setup, ownership, ports, and databases](docs/phase1/contract.md#3-runtime-isolation-for-parallel-agents)
before starting agents. For example: `API_PORT=8001 WEB_PORT=3001 pnpm dev` after
updating that worktree's database URL, CORS origins, web URL, and public API URL.

The following commands are wired to owner modules that are **not implemented yet**;
they intentionally fail with module-not-found until the corresponding agent adds them:

| Command | Owner / purpose |
| --- | --- |
| `pnpm eval:extraction` | A1 / extraction evaluation |
| `pnpm demo:render-mailbox` | A1 / render synthetic email fixtures |
| `pnpm seed:fixture-ledger` | A4 / seed the development ledger |
| `pnpm seed:gmail-demo-inbox` | A2 / populate the dedicated demo inbox |
| `pnpm voice:benchmark` | A3 / voice evaluation |

To add a future database migration after defining/importing models:

```sh
uv run --package finboy-api alembic -c apps/api/alembic.ini revision --autogenerate -m "Describe the change"
# Review the generated migration before applying it.
pnpm db:migrate
pnpm db:check
pnpm test:integration
```

No tables are created by application startup. Migration `0002_phase1` creates the
11 contract tables and seeds Arun (`00000000-0000-0000-0000-000000000001`). There
is no product login. Domain service bodies raise `NotImplementedError`; empty
routers expose no domain endpoints yet. App navigation links to placeholder pages
at `/dashboard`, `/transactions`, `/review`, `/assistant`, `/connect`, `/privacy`,
and `/import/[runId]`.

Add a shadcn component only when needed:

```sh
pnpm --filter @finboy/web exec shadcn add <component>
```

## Health and errors

```sh
curl -i http://127.0.0.1:8000/api/v1/health
```

Healthy (`200`):

```json
{"status":"ok","service":"finboy-api","version":"0.1.0","database":"connected"}
```

Database unavailable (`503`):

```json
{"status":"degraded","service":"finboy-api","version":"0.1.0","database":"unavailable"}
```

The frontend distinguishes checking, connected, database unavailable, and offline
states. Requests have a five-second timeout and validate the response at runtime.
Health responses are uncached. HTTP, validation, and unexpected errors use:

```json
{"error":{"code":"http_error","message":"Not Found","request_id":"generated-request-id"}}
```

API responses include `X-Request-ID`, also exposed through CORS. Logs are JSON
with allowlisted operational fields. Request bodies, raw URLs, query strings,
headers, SQL parameters, exception messages, and financial data are not logged.

## Repository

```text
apps/api/
  src/finboy/
    api/             # Versioned HTTP routes
    core/            # Settings, logging, errors, request context
    db/              # SQLAlchemy metadata and sessions
    services/        # Application logic
  alembic/           # Reviewed schema migrations
  tests/             # Unit/HTTP contracts and local integration tests
  fixtures/          # Synthetic demo_mailbox/, llm_cassettes/, voice/ (owners add data)
apps/web/
  src/app/           # Next.js routes, layout, styles, icon
  src/components/    # Landing UI and owned shadcn components
  src/hooks/         # Connection state and refresh lifecycle
  src/lib/api/       # Domain clients; shared zod requestJson helper
docs/architecture.md
AGENTS.md
compose.yaml
```

See [architecture](docs/architecture.md) and [engineering rules](AGENTS.md).
Completed checks and observed results are recorded in [verification](docs/verification.md).
The contract defines the remaining Phase 1 work and its out-of-scope list.
This pre-flight implements no domain features.

## Troubleshooting

- Docker socket unavailable: start Docker Desktop and rerun `pnpm db:up`.
- Database unavailable: inspect `docker compose ps` and `docker compose logs postgres`,
  confirm port 5433 is free, and check the backend URL matches the Compose values.
- Offline in the browser: confirm the API is running on port 8000, the public API
  URL is correct, and the page's exact origin appears in `CORS_ORIGINS`. If Next.js
  chooses another port because 3000 is busy, free 3000 or explicitly update CORS.
- Build or lint failure after dependency edits: rerun both package-manager installs
  and review compatibility. Do not suppress TypeScript or ESLint errors.
