# Source isolation inventory and recovery

Run `uv run --package finboy-api python -m finboy.services.ux.isolation` using the
reviewed environment before and after deployment. It opens a read-only transaction
and outputs only four provenance counts, with no IDs, bodies or financial fields.
It works before migration 0004 because it reads original provenance columns only.
Do not print an environment file, database URL, source body or full SQL parameters.

0004 adds scope metadata, recovery metadata and a generation trigger. It does not
remove/reset sources, records, corrections, locks or revisions. Source-only demo
records are tagged demo. Mixed demo/live canonical values are quarantined; hiding
a source alone would not validate them. Same-scope matching prevents new mixing.
0005 adds encrypted Gmail continuation state and last-attempt source provenance.

Before production migration, make and validate the existing private PostgreSQL backup.
Keep the previous release and the reviewed new archive. The migration preservation
regression constructs a pre-0004 schema with pure demo, pure live and mixed sources,
then asserts canonical values, revisions and source counts survive unchanged. Its
schema and operations roll back only inside the assigned disposable database.

After migration, `GET /privacy/isolation` returns stored scope counts. Inspect mixed
records explicitly through `/transactions/page?dataset=quarantined&scope=all` and exact
detail IDs. Their household source evidence is inspectable, but ordinary confirm,
correction, merge and assistant/summary operations cannot trust their canonical values.
Never make a blanket `dataset='household'` update or delete/reimport the ledger.

Forward recovery of a mixed record requires a reviewed source-to-canonical mapping:
identify surviving household claims; preserve the old canonical row, every user revision
and all source IDs; separate sample claims; rederive a pending household record using
only household evidence; then let the human review its facts. Keep old user corrections
as history until their intended household applicability has been established. This is
operator work rather than an automatic migration guess. If the production inventory
contains mixed records, record the count as unresolved acceptance and prepare the exact
mapping before making further data changes. No destructive cleanup is authorized.

The scope tagging is non-destructive and transactionally reversible while upgrading:
a failed migration rolls back. After successful release, use forward recovery and the
private backup for a reviewed recovery into a separate database. Do not automatically
downgrade migrations or restore old code that ignores scope: that would expose the old
mixed estimate. Preserve the upgraded schema and fail-closed household boundary while
repairing an application release. Never run fixture/test suites against production.
