# Voxpay frontend hosting — migration and operations

The frontend is served from voxpay at finboy.io. The former Vercel custom domain has
been retired; the API remains on its existing host and callback domain.

**Latest release:** main `b4c331c736c06b33e703d4fab3a08452e16b0ed9` passed
GitHub Actions run `40806816672`, including full backend and six browser jobs, and the
automatic release switched to the green slot. The public `/healthz` reports that exact
revision. Run duration was 4m50s. The green service is enabled for reboot; API, nginx,
and PostgreSQL are active. Vercel automatic Git deployments are already disabled.

The first main deployment `10d3c18` hit an nginx reload race in its revision check;
automatic rollback kept the previous slot active. `b4c331c` adds a bounded wait for
the new nginx worker and its subsequent full pipeline and production deployment passed.
Google and WhatsApp sign-in and AI speech were confirmed by the human; Gmail Connect
was not tried. The certificate renewal dry run passed. GoDaddy confirmed removal of
the old `finboy` CNAME on 29 October at approximately 02:46 UTC; both authoritative
nameservers subsequently returned NXDOMAIN. After the earlier one-hour DNS TTL elapsed,
the Vercel domain assignment was removed and the API was restricted to the new origin
following a drained, validated restart. Production health and CORS checks passed.

## Implemented and verified

- Node 24 was installed only under `/opt/finboy-web/node`, with the official distribution
  checksum verified. The `finboy-web` and `finboy-deploy` accounts are separate from the
  API account. The deploy SSH key is forced-command-only, host-key pinned and restricted
  to the frontend repository's `production` GitHub environment on `main`. A separate,
  repository-scoped GitHub deploy key permits only publication to the backend mirror; a
  non-fast-forward mirror push fails the release instead of overwriting history.
- Standalone builds are packaged on Ubuntu CI, with no environment files, an API runtime
  digest and an archive checksum. A staging helper validates the archive, disk capacity,
  API compatibility and candidate revision; activation switches the nginx upstream,
  verifies public health, auth rejection and assets, and restores the old upstream if
  verification fails. Services use loopback ports 3100/3101 and separate web permissions.
- Hashed static assets are shared across retained releases. The helper retains the current
  and two prior web releases, enables the active slot on reboot, and schedules a guarded
  two-minute drain without holding the release job open. A later release waits before reusing
  a draining slot. It never touches
  API releases, other applications, database migrations or production backups.
- The first feature-branch run, `40802736199`, passed backend, full contract browser and
  real API browser checks at all three widths, using disposable CI databases. It finished
  in 5m58s versus the earlier 8m16s web workflow. Run `40804058903` split contract and real
  browser jobs, passed all six and finished in 4m48s without removing coverage.
- `pnpm check`, `NEXT_PUBLIC_API_URL=/ FINBOY_API_ORIGIN= pnpm build`, `actionlint` and
  19 isolated deployment-safety tests passed locally. The Linux artifact staged and its
  revision-matched `/healthz` passed on the server.
- Hostinger apex A now points to 147.93.108.162 with TTL 60 (the UI rejected the previous
  TTL 50); the existing www CNAME is unchanged. Let’s Encrypt issued a certificate for
  both names. Renewal dry run passed. The existing Google Sign-in client now includes
  `https://finboy.io`.
- Nginx sends `/api/v1/` to the existing loopback API, and frontend routes to the active
  web slot. Public landing at 1440/390/320 px, logo, manifest, API health (200), protected
  finance (401), and www redirect (308) were verified. The new web origin is allowed and
  `WEB_APP_URL` points to finboy.io, the only remaining allowed web origin.
- The human confirmed Google sign-in, WhatsApp sign-in and AI speech on finboy.io.
  Gmail Connect was not tried; no Gmail acceptance is claimed.

## Remaining acceptance

- Gmail callback return remains unverified. Never record login codes, real messages or
  financial screenshots.
- Keep `finboy-api.antlegs.in` for Gmail and Meta callbacks, all provider credentials
  and encryption/session keys, and the existing Vercel project as rollback evidence.
  Users sign in once on the new host. Main-only frontend releases deploy after all
  required checks, with serialized activation and a push to the backend mirror.

The user signed into GoDaddy in the `sahlcyprus@gmail.com` Chrome profile. Preserve the
`finboy-api` A record and all unrelated domain records. Never stop shared services, run
production test suites, or import fixtures into the production database.
The old `finboy` CNAME's TTL was reduced from one hour to ten minutes at 02:09:55 UTC;
both authoritative nameservers confirmed the new TTL by 02:12:52 UTC. The Vercel
assignment was removed after 03:12:52 UTC, more than ten minutes after DNS deletion.

Manual rollback uses `sudo /usr/local/sbin/finboy-web-control rollback <full-revision>`
with one of the retained revisions in `/var/lib/finboy-web/state.json`. The helper refuses
rollback if the target's API compatibility digest differs from the currently deployed API.
