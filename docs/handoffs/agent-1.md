# Agent 1 — first implementation checkpoint

Branch: `feat/finboy-money-api`, based only on frozen `fd618ae`.
Worktree: `/Users/sahal/.codex/worktrees/finboy-money-api/ai_boom`.
API/web/database: 8011 / 3011 / `finboy_p1`.

Typed actual API examples are published in `agent-1-api-examples.json` for Agent 2
and Agent 3. GET transactions is an array. Details/mutations return exactly
`{transaction, sources, confidence_factors, revisions}`. Merge request is `{keep_id}`;
the path ID is merged into it and the returned detail is for the path ID.

Implemented deterministic money functions, money/transaction routes, typed evidence
details, validated corrections/review writes, and a development seeder using A1's
actual rendered mailbox through the existing A2 import orchestration. No dependency,
model, migration, lockfile, or shared-source changes. The ledger-only fixes reopen
invalid paid commitments after payment rejection/correction, reject merging terminal
records, and make repeated keep-separate idempotent.

Verified so far: locked uv/pnpm installs, private worktree environment, healthy shared
PostgreSQL, migration to 0002 in `finboy_p1`, real 42-message import (42 processed,
26 transactions, 0 failed), HTTP responses and Pydantic validation of examples.
Assertions passed for 6200000 / 3742000 / 980000 / 1478000 paise, proposal remaining
978000, food 661000 before / 786000 after, and Amazon's three actual source events.
Rules-mode pipeline and local PostgreSQL were real; no live extraction/provider calls.

New money audit events use fixed types and metadata `{action, fields}` (field names
only), inserted in the owning review transaction. No shared audit helper or DB
constraint changes. See `docs/money.md` for exact filtering/count/warning semantics.

Work remains: full focused HTTP/PostgreSQL tests, rollback/scoping/re-import checks,
`pnpm check`, `pnpm build`, `pnpm db:check`, and full integration/regression run.
This checkpoint is not the final handoff.
