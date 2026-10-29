# Voxpay frontend hosting — migration and operations

The migration is in progress on `feat/finboy-voxpay-hosting`, based on remote main
`1c724a4`. The first Linux artifact `ac1e939` is running on voxpay's blue slot, with
finboy.io already served over HTTPS. The old Vercel frontend stays available during
acceptance; it has not yet been retired.

## Implemented and verified

- Node 24 was installed only under `/opt/finboy-web/node`, with the official distribution
  checksum verified. The `finboy-web` and `finboy-deploy` accounts are separate from the
  API account. The deploy SSH key is forced-command-only, host-key pinned and restricted
  to the frontend repository's `production` GitHub environment on `main`.
- Standalone builds are packaged on Ubuntu CI, with no environment files, an API runtime
  digest and an archive checksum. A staging helper validates the archive, disk capacity,
  API compatibility and candidate revision; activation switches the nginx upstream,
  verifies public health, auth rejection and assets, and restores the old upstream if
  verification fails. Services use loopback ports 3100/3101 and separate web permissions.
- Hashed static assets are shared across retained releases. The helper retains the current
  and two prior web releases and drains the old slot before stopping it. It never touches
  API releases, other applications, database migrations or production backups.
- The first feature-branch run, `40802736199`, passed backend, full contract browser and
  real API browser checks at all three widths, using disposable CI databases. It finished
  in 5m58s versus the earlier 8m16s web workflow. The next run splits contract and real
  browser jobs to improve the critical path without removing coverage.
- `pnpm check`, `NEXT_PUBLIC_API_URL=/ FINBOY_API_ORIGIN= pnpm build`, `actionlint` and
  14 isolated deployment-safety tests passed locally. The Linux artifact staged and its
  revision-matched `/healthz` passed on the server.
- Hostinger apex A now points to 147.93.108.162 with TTL 60 (the UI rejected the previous
  TTL 50); the existing www CNAME is unchanged. Let’s Encrypt issued a certificate for
  both names. Renewal dry run passed. The existing Google Sign-in client now includes
  `https://finboy.io`.
- Nginx sends `/api/v1/` to the existing loopback API, and frontend routes to the active
  web slot. Public landing at 1440/390/320 px, logo, manifest, API health (200), protected
  finance (401), and www redirect (308) were verified. The new web origin is allowed and
  `WEB_APP_URL` points to finboy.io; previous origins remain temporarily allowed.
- The human confirmed Google sign-in, WhatsApp sign-in and AI speech on finboy.io.
  Gmail Connect was not tried; no Gmail acceptance is claimed.

## Remaining cutover work

- Run the updated feature-branch pipeline and verify its six browser jobs, actual duration
  and exact Linux artifact. Update the installed root-owned helper to the reviewed version.
- Gmail callback return remains unverified. Never record login codes, real messages or
  financial screenshots.
- Merge and push reviewed changes to both repositories. The frontend repository's main-only
  release job deploys only after all required checks pass, with a non-cancellable serialized
  activation. The backend repository is a mirror and does not run duplicate CI.
- Verify that the final deployment revision matches both main branches and the public
  `/healthz`. Only after acceptance, remove the `finboy` CNAME in GoDaddy, wait its one-hour
  TTL, then detach the old Vercel custom domain and disable its automatic deployment.
- Remove the temporary old frontend origins from the API through a drained, validated
  configuration restart. Keep `finboy-api.antlegs.in` for Gmail and Meta callbacks, all
  provider credentials and encryption/session keys, and the existing Vercel project as
  rollback evidence. Users sign in once on the new host.

The user signed into GoDaddy in the `sahlcyprus@gmail.com` Chrome profile. Preserve the
`finboy-api` A record and all unrelated domain records. Never stop shared services, run
production test suites, or import fixtures into the production database.

Manual rollback uses `sudo /usr/local/sbin/finboy-web-control rollback <full-revision>`
with one of the retained revisions in `/var/lib/finboy-web/state.json`. The helper refuses
rollback if the target's API compatibility digest differs from the currently deployed API.
