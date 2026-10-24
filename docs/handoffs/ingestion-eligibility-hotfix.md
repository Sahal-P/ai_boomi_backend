# F39 production eligibility hotfix

The human explicitly requested this fix and parallel verification after a job
advertisement's compensation became a needs-review transaction. This is an
isolated hotfix from `b572565`, alongside the active UX Backend/Product worktrees;
their files and uncommitted changes are untouched.

## Changes

- Shared bounded financial-claim eligibility and local amount/event/proof binding.
- Non-event ads/examples/negations/future instructions cannot enter the ledger via
  rules-only, live, cached or provider-unavailable paths.
- Model rejection suppresses weak rules; anchored settlements remain review-only
  on disagreement. Conflicting obligations fail for recovery without a deduction.
- Genuine transaction types and the original 42-message fixture oracles preserved.
- Versioned live cache policy; offline historical cassettes revalidated.
- Synthetic eligibility and actual pipeline/SQLite persistence regressions.

No new dependency, schema migration, frontend change, provider setting or HTTP
contract change. Existing privacy, authentication and OAuth handoff stay intact.

## Integration ownership

This hotfix must be merged from main into `feat/finboy-ux-backend` and the final UX
integration branch before their release. In particular retain `claims.py`, guarded
rules/classification/model validation, the cache policy key, conflict handling in
confidence and both new test modules. The UX branch changes pipeline cache names,
failed-source retry and financial datasets: preserve those independently while
retaining this common eligibility gate. Do not ship the old global paid/first-amount
parser again. No edits were made in the active owners' worktrees.

## Verification

Parallel read-only adversarial review and an independently authored synthetic test
suite covered false positives and genuine alerts. `pnpm check` passed 556 backend
unit tests and 19 web tests, Ruff, ESLint and strict TypeScript. This includes 179
new eligibility/persistence regressions and the unchanged rules/offline 42-message
oracles. The focused ingestion/persistence/oracle selection passed 221 tests.
`NEXT_PUBLIC_API_URL=/ pnpm build` passed. No schema changed; PostgreSQL integration
tests were not re-run for this hotfix. Persistence unit checks use the established
SQLite double with only PostgreSQL advisory locking replaced.

Code commit `988a731` was installed at `/opt/finboy/releases/988a731`. Before
promotion, a read-only shadow check re-fetched the reported email using its existing
Gmail grant, confirmed its source hash and returned non_financial / zero events
with no provider model request or write. A private backup succeeded; only
finboy.service restarted. Public proxied health returns 200 and unauthenticated
finance remains 401. Finind, nginx and PostgreSQL services stayed active.

The known false entry was non-destructively excluded from Review, with its source
classified non-financial/skipped and transaction rejected. Original values/source
evidence remain; system revisions and audit record the reason. Checks required
zero confidence, pending status, no payment proof, no human corrections/locks,
no linked/dependent financial records, the original model veto, and a matching
fresh message rejected by the new policy. Confirmed/user-corrected records were
untouched and nothing was deleted. Two older job-ad candidates were inspected
under the same guards; their final counts are recorded in the production note.

Any existing-record repair is non-destructive and narrowly guarded: preserve the
source, evidence and audit history; do not change confirmed or manually corrected
financial records. This hotfix does not authorize broad ledger deletion/reset.
