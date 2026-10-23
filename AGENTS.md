# FinBoy engineering guide

## Scope and architecture

- Phase 1 includes the authorized completion round in
  `docs/phase1/parallel-completion.md`, which supersedes conflicting scope,
  ownership, language, provider, and runtime sections of the original contract.
  All other boundaries in `docs/phase1/contract.md` remain binding.
- Keep one FastAPI application in `apps/api` and one Next.js App Router application
  in `apps/web`. PostgreSQL is the only persistent service.
- API routes own HTTP contracts, `services` own business logic, `db` owns SQLAlchemy
  sessions and metadata, and `core` owns settings, errors, and logging.
- Keep UI components presentational. Put backend communication and runtime response
  validation in `apps/web/src/lib/api/` (one module per domain, shared helper in
  `http.ts`) and connection state in a small hook.
- Prefer simple functions and explicit types. Avoid generic repositories, service
  containers, microservices, or shared packages until there is a real need.
- Use Alembic for schema changes; never call `metadata.create_all()` at startup.
  Import future model modules into Alembic's environment before autogeneration.

## Coding standards

- Use uv for Python and pnpm for JavaScript. Commit both lockfiles. Use stable
  releases and official documentation when changing dependencies.
- Python uses type annotations, Pydantic v2, Ruff, and SQLAlchemy 2-style APIs.
  Blocking database work belongs in synchronous routes/services, not async routes.
- TypeScript is strict. Avoid `any`, unchecked response casts, and disabling lint
  rules to hide problems. Use accessible HTML, Tailwind, shadcn/ui, and Lucide.
- Keep modules small, names descriptive, and comments focused on non-obvious intent.
  Add dependencies only when they solve a concrete problem.
- Do not delegate to subagents unless the user explicitly asks for delegation.

## Security and privacy

- Never commit `.env` files, real credentials, tokens, bank identifiers, or financial
  records. Examples must contain only clearly local development values.
- Every future OpenAI call runs on the backend. Never place an API key in a
  `NEXT_PUBLIC_*` variable, client component, browser bundle, or frontend request.
- Never log request/response bodies, query strings, authorization/cookie headers,
  database URLs, raw SQL parameters, exception messages, or financial information.
  Use structured, allowlisted operational fields and generated request IDs.
- Keep CORS origins explicit. Local services bind to loopback. Health responses and
  error envelopes must not reveal internal exception details or credentials.
- Parameterize database queries and validate external input. Future write services
  own their transaction boundaries; session dependencies do not auto-commit.

## Testing and delivery

- Run `pnpm check` and `pnpm build` before completing a code change.
- Add focused pytest/HTTPX coverage for behavior, failure modes, error redaction,
  and CORS when changing backend contracts. Unit tests must not require PostgreSQL.
- For database changes, run `pnpm db:migrate`, `pnpm db:check`, and
  `pnpm test:integration` against a local disposable database. Never use a production
  database for tests or run destructive migrations without explicit authorization.
- Verify frontend changes in a browser at desktop and mobile widths, including
  loading, connected, degraded, and offline behavior when relevant.
- Update setup/architecture documentation when commands, settings, or boundaries
  change. Report commands, actual outcomes, and any remaining verification limits.

## Parallel work

- Follow the ownership table, ports, and per-agent databases in
  `docs/phase1/parallel-completion.md` for this completion round.
- Never stop the shared PostgreSQL container (`db:down` or Compose down).
- Secrets live only in `~/.config/finboy/secrets.env` and gitignored env files.
