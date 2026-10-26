# Browser journeys (Playwright)

`pnpm test:e2e` builds the web app with the deployed proxy shape (`NEXT_PUBLIC_API_URL=/`),
starts `next start`, and runs every spec at 1440×1000 (`desktop`), 390×844 (`phone-390`) and
320×740 (`phone-320`) in the system Chrome channel (`PLAYWRIGHT_CHANNEL` overrides it).
Set `E2E_PORT` to pick the port (default 3032) when a dev server already uses it.

## What answers the API

`support/fake-api.ts` is a **test-only** in-memory double of API contract v1.2.0 with synthetic
data; `support/fixtures.ts` routes every same-origin `/api/v1/**` request to it and checks that
writes carry the app's exact Origin. It is never imported by application code.

These runs prove UI behaviour against the contract: sign-in return paths and in-place
re-authentication, Sources and import outcomes with recovery, staged uploads, the review queue
(decisions, merge preview, undo, conflicts, drafts, focus), >200-record paging, exact evidence
links, overview/obligations/simulation staleness, assistant pairing, voice states (synthetic
microphone stream; denied permission), playback states with a generated tone
(`fixtures/synthetic-tone.mp3`), privacy previews/export, the read-only sample, fixed-layer
obstruction at phone widths, navigation contrast, titles, offline and no-WebGL.

They do **not** prove live integration with the FastAPI backend, real Google consent, real
microphones, provider speech quality, or playback on a phone. `live.spec.ts` (below) covers the
UI-to-API part; record human-only checks separately.

## Theme checks and review tools

`theme.spec.ts` checks the glass theme on rendered pages: every visible text, placeholder and
form-control boundary against its composited background (ancestors, the nav's positioned ink
capsule, the field's darkest point, ink under floating chrome) on every route and empty state;
at most three blurred layers in view; real blur in Chromium; Reduce Transparency (via CDP),
Increase Contrast and forced-colours fallbacks; and the thinking orbs' dark-ink pin, hidden
status for assistive tech and resting behaviour. Two opt-in tools run only when asked:

```sh
cd apps/web
E2E_CAPTURE_DIR=/abs/dir pnpm exec playwright test e2e/capture.spec.ts   # every route and state, 3 widths
E2E_PERF=1 pnpm exec playwright test e2e/perf.spec.ts --workers=1        # scroll frame times, CPU 4x
```

Run a capture or a perf measurement on the baseline and on the change, on the same machine,
to compare them.

## Manual checks against the double

`support/mock-server.ts` serves the same double on loopback. The proxy only accepts an HTTPS
`FINBOY_API_ORIGIN`, so use a short-lived private certificate kept outside Git and trusted only
by Next's Node process:

```sh
mkdir -p /tmp/finboy-tls && openssl req -x509 -newkey rsa:2048 -nodes -days 3 \
  -subj "/CN=FinBoy local test API" -addext "subjectAltName=IP:127.0.0.1" \
  -keyout /tmp/finboy-tls/key.pem -out /tmp/finboy-tls/cert.pem
MOCK_TLS_CERT=/tmp/finboy-tls/cert.pem MOCK_TLS_KEY=/tmp/finboy-tls/key.pem \
  node apps/web/e2e/support/mock-server.ts           # https://127.0.0.1:8032, MOCK_AUTH=required optional
NODE_EXTRA_CA_CERTS=/tmp/finboy-tls/cert.pem NEXT_PUBLIC_API_URL=/ \
  FINBOY_API_ORIGIN=https://127.0.0.1:8032 pnpm --filter @finboy/web dev --port 3032
```

## Live journeys against a real API

`live.spec.ts` is skipped unless `E2E_LIVE_API=1`. It drives the production build through the
same-origin proxy to a real FinBoy API on a **disposable** database (never production): it
uploads the 42 synthetic `.eml` files in `apps/api/fixtures/demo_mailbox/`, re-uploads them
(idempotency), reads the overview, makes and undoes one review decision, opens an exact
record, previews deletion and downloads an export (it never deletes), opens `/demo` and asks
one question. Serve the API with `uvicorn … --ssl-keyfile key.pem --ssl-certfile cert.pem`,
allow the test origin in its `CORS_ORIGINS`, then:

```sh
cd apps/web
E2E_LIVE_API=1 E2E_PORT=3031 E2E_API_ORIGIN=https://127.0.0.1:8031 \
  NODE_EXTRA_CA_CERTS=/tmp/finboy-tls/cert.pem pnpm exec playwright test e2e/live.spec.ts --workers=1
```

Run it with one worker: the three viewports share one database.

The API must use the fixed synthetic clock `DEMO_TODAY=2026-10-24` and rules extraction.
The live harness rejects API origins outside the two allocated loopback ports. It requires
successful supported answers (a provider failure cannot satisfy the test), resolves/reopens
an overdue bill, previews/merges/undoes a deliberate duplicate mistake and uploads 205 unique
synthetic older bank alerts through five batches before reaching record 201. Runs are serial.
CI executes both the contract double and the real disposable PostgreSQL journeys; it receives
no production environment or provider credentials. No browser artifacts are uploaded from CI.
