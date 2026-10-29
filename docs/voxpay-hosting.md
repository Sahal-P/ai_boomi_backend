# Voxpay frontend migration — implementation status

Branch: `feat/finboy-voxpay-hosting`, based on remote main `1c724a4`.
This migration is incomplete and is not approved for promotion by this document.

## Implemented locally

- Next.js standalone output with monorepo file tracing.
- Dynamic `/healthz`: returns status/revision and no-store; fails with 503 when the
  process has no valid full `FINBOY_RELEASE_SHA`.
- `scripts/web-release.py`: packages the standalone runtime, public files and static
  assets, with a revision, backend compatibility digest and archive checksum. Environment
  files and escaping symlinks are rejected. No API credentials are packaged.
- Hardened two-slot systemd template and finboy.io Nginx template. These are not installed.
- Draft restricted SSH and root activation helpers with checksum, API compatibility,
  slot health, nginx reload/rollback and static asset retention checks.
- Draft CI workflow with a single build artifact, parallel backend and browser checks,
  isolated databases and a main-only frontend deployment gate.

## Verification so far

- `pnpm check`: passed lint, types, 1,066 API unit tests and 54 web tests.
- `NEXT_PUBLIC_API_URL=/ pnpm build`: passed, including standalone output and `/healthz`.
- Python compile and `git diff --check`: passed.
- Packaging a local macOS verification build succeeded (13.7 MB). It is a local check
  artifact only, not a Linux production release, and must not be installed on voxpay.
- Fourteen isolated deployment safety tests and `actionlint` passed. The new CI
  workflow and deployment helpers still require end-to-end verification.

## Remaining implementation

- Verify and repair the restricted SSH/activation helpers against disposable releases,
  including retry, failure and rollback cases, before installing them on voxpay.
- Exercise and repair the GitHub Actions pipeline on the feature branch; verify complete
  coverage and measured timing before permitting the production deployment job.
- Node 24 installation, accounts, slots, safe cache permissions, deployment credential,
  known-host pinning and Nginx configuration validation on voxpay.
- Hostinger DNS change, certificate issuance/renewal, Google authorized-origin update,
  drained API origin configuration changes and browser/auth acceptance.
- Publish/merge only after these are complete and validated. Production migration has
  not happened; existing Vercel frontend and API remain the live deployment.

## Human steering

The human subsequently signed into GoDaddy in the `sahlcyprus@gmail.com` Chrome profile.
The old `finboy` CNAME points to Vercel with a one-hour TTL. Preserve it until finboy.io
passes acceptance; only then remove that specific record and, after its TTL, detach the
Vercel domain assignment to avoid leaving a dangling CNAME.

Preserve the existing API callback hostname, sessions/encryption keys, other applications,
production database and all unrelated local files. No production test suites or fixture
imports are permitted. The frontend systemd template requires a writable cache directory
outside its protected release tree; activation tooling must establish this before use.
