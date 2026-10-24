# UX remediation integration and release — 24 October 2026

Agent 1 assembled the full Backend and Product branches in the isolated backend-owned
worktree on `feat/finboy-ux-integration`. The human explicitly confirmed Product finished
at `5fd2467` and transferred integration ownership, then requested merge, push and deploy.
No additional agents were created. Original design, A2 and older production worktrees were
not edited. The clean primary main checkout was fast-forwarded only for final publication.

## Integrated source

- Required baseline: `b572565aa521a753fbee1271ca0c68e470ff15c8`.
- Contract-only bootstrap: `2e42622`; final backend handoff: `5dd6c6a`.
- Full Product branch through `5fd2467`; deployed eligibility fix/main through `c37d611`
  retained, including claim eligibility, cache policy and false-positive safeguards.
- Application assembly: `0af9ca2`; final release source: `3098a1484bc5735739b6115ab3f16a2abb70854a`.
  Later changes in that range concern browser synchronization and CI environment/runtime setup.
- Both existing GitHub repositories received the integration branch and fast-forwarded main,
  without force pushes, history rewriting or branch deletion.
- Contract v1.2.0. The integrated clients explicitly request `include_overdue_line: true`
  in assistant and simulation calls. The legacy default remains compatible with the old UI.
- Integration also localizes answer period/evidence/playback controls, protects scroll targets
  from phone chrome, avoids duplicate mobile Undo messages and records explanation clicks
  without claiming understanding. Review completion requires refreshed zero unresolved count.

## Executed local verification

Only loopback disposable `finboy_ux_api` was used. API 8031 / web 3031; rules extraction;
synthetic `.eml` files; temporary private TLS certificate trusted solely by Next's Node process.
No test/fixture evaluation was run against production. Google HTTP is mocked in provider-boundary
unit/persistence tests; the real UI suite has no API double.

| Command | Actual outcome |
| --- | --- |
| `pnpm install --frozen-lockfile` | Locked dependencies installed. |
| `pnpm check` | Ruff/format, ESLint, strict TypeScript, 584 backend unit tests and 37 web client tests passed. |
| `pnpm build` | Production Next.js build passed. Browser harness also rebuilt with the deployed same-origin `/` proxy shape. |
| `pnpm db:migrate` | Disposable schema upgraded through `0006_event_origins`. |
| `pnpm db:check` | No schema drift. |
| `pnpm test:integration` | 49 passed against disposable PostgreSQL. |
| `E2E_PORT=3031 pnpm test:e2e` | 131 passed, 46 intentional skips: 33 opt-in real tests plus 13 viewport-specific cases. Three widths, test-only contract double. |
| `E2E_LIVE_API=1 E2E_PORT=3031 E2E_API_ORIGIN=https://127.0.0.1:8031 NODE_EXTRA_CA_CERTS=<private temporary certificate> pnpm --filter @finboy/web exec playwright test e2e/live.spec.ts --workers=1` | 33 passed at 1440×1000, 390×844 and 320×740; actual API/PostgreSQL through HTTPS same-origin rewrite. |
| `git diff --check` | Passed. |

Real browser journeys stage/import the 42-message mailbox, reupload without adding new
records, inspect estimate/coverage/category links, decide/undo review, follow exact evidence,
preview deletion and explicitly download structured export, enter read-only sample, and require
a successful supported food answer with exact amount and evidence. They also correct a bill
to overdue without increasing the estimate, resolve/reopen/restore it, preview a deliberate
merge into a confirmed record and undo, and import 205 unique older synthetic alerts in five
source batches before reaching record 201. These operations occurred only in the disposable DB.

The final pass fixed actual mobile duplicate announcements/scroll spacing as well as test
races around hydration, hidden modal backgrounds and asynchronous undo navigation. Failed
acceptance attempts were corrected and rerun; they are not included as successful evidence.

## Continuous verification

Owned workflows `ux-backend.yml` and `ux-web.yml` install locked dependencies and test an
isolated PostgreSQL service without provider/production secrets. Backend checks unit contracts,
additive migrations, drift and real persistence. Web checks the complete build, three-width
contract suite and opt-in actual UI/API/PostgreSQL suite with private loopback TLS.

CI uses uv 0.13.5, whose official catalog contains Linux Python 3.15.1. Earlier uv 0.12.19
could use the already-installed local/server runtime but could not download it on a clean runner.
Tests unset the runtime WEB_APP_URL so independently constructed test settings own their origins.
The synthetic clock is scoped to the disposable API, preserving the clock-boundary unit test;
ffmpeg/ffprobe are explicitly installed. No production settings were weakened for CI.

Hosted CI passed for `907b5b5` in both repositories: 584 backend units, 37 web client
tests, build/static checks, 49 PostgreSQL integration tests, 131 contract browser checks
(46 intentional skips) and 33 actual UI/API/PostgreSQL checks. Evidence:
[backend trust](https://github.com/Sahal-P/ai_boomi_backend/actions/runs/40057582634),
[backend web journeys](https://github.com/Sahal-P/ai_boomi_backend/actions/runs/40057582640),
[frontend trust](https://github.com/Sahal-P/ai_boomi_frontend/actions/runs/40057584858),
[frontend web journeys](https://github.com/Sahal-P/ai_boomi_frontend/actions/runs/40057584850).
The Gmail continuation fixture now supplies its own synthetic web origin rather than
relying on a private local env file. This is test setup only; the deployed application source
is identical. Release-evidence documentation commits do not invalidate these source checks.

## Executed backend release

- Reviewed locked artifact extracted to `/opt/finboy/releases/3098a14`; private backup made by
  `finboy-backup` and validated with `pg_restore --list` before promotion.
- Immediate read-only preflight: zero queued/running imports; 26 demo-only transactions and
  four demo-only obligations; zero mixed records, cross-scope payment links or legacy merges.
- Stopped only `finboy.service`, rechecked no active import, applied additive migrations
  `0004_ux_trust`, `0005_scan_continuation`, `0006_event_origins` and checked no drift.
- Verified transaction, obligation, source, event and import counts were preserved; revisions
  and audit counts did not decrease. The post-migration scope inventory was 36 household and
  26 demo transactions, with zero household transactions carrying demo provenance.
- Atomically switched `/opt/finboy/current` to release `3098a14` and started only FinBoy.
  Loopback readiness returned 200. Public API and frontend-proxied health/demo returned 200;
  unauthenticated summary/transactions/privacy returned 401; docs/OpenAPI returned 404.
- Finind production, Finind Celery, nginx and PostgreSQL remained active. No provider grants,
  passwords/session keys, DNS, origins or other host applications changed.

The migration preserved existing records and corrections; no production reset, deletion,
fixture import or general mailbox rescan was performed. Existing grants/callback are retained.
The sample is now a public pure read-only response and cannot mutate household import history.

Vercel production `6BST4o7vdCJjU5GwoP3tnxUStGyh` became Ready for main `3098a14`
with `finboy.antlegs.in` assigned (42-second build). Actual existing-session browser checks
passed Sources/account/Scan now/upload controls, household estimate with last successful scan
and calculation explanation, exact transaction evidence, and focus restoration/no horizontal
overflow at all three required widths. The public read-only sample rendered at phone width;
only synthetic sample content was captured in the release screenshot. No household financial
fields or mailbox contents were printed or committed during browser verification.

Post-migration operational check found zero active imports and zero missing original source
links. Production permissions, provider settings and grants remained unchanged. Release-note
and test-fixture commits after `3098a14` do not change application/runtime/dependency source;
Git comparison against that deployed source passed.

## Recovery and limits

Do not downgrade the schema or restore pre-scope API `988a731` over migrated data: that code
ignores dataset boundaries. Recover forward with the scoped API and additive migrations;
retain the current reviewed release/backup. The old frontend is wire-compatible with the new
API because separate overdue response lines are opt-in. Backups remain private for seven days;
archive listing passed, while full restore drill/off-host recovery remains an operator task.

[F01–F38 matrix](../ux-round/implementation-map.md) distinguishes implementation and evidence
from remaining human acceptance. No observed household pilot/comprehension rate, physical
mid-range phone performance, screen-reader session or real phone microphone/playback result
is fabricated. Hindi/Malayalam fluency and pronunciation acceptance need the relevant users.
Production WhatsApp stays disabled. No public signup, payment action, investment recommendation,
new persistent service, external analytics or raw-email export was introduced.
