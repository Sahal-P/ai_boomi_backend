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
suite covered false positives and genuine alerts. Focused eligibility, persistence,
model-boundary and fixture tests passed before final check/build. Final command
outcomes and live shadow/deployment results will be recorded after execution.

Any existing-record repair is non-destructive and narrowly guarded: preserve the
source, evidence and audit history; do not change confirmed or manually corrected
financial records. This hotfix does not authorize broad ledger deletion/reset.
