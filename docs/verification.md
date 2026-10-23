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
