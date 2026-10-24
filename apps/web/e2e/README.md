# Browser journeys (Playwright)

`pnpm test:e2e` builds the web app with the deployed proxy shape (`NEXT_PUBLIC_API_URL=/`),
starts `next start`, and runs every spec at 1440×1000 (`desktop`), 390×844 (`phone-390`) and
320×740 (`phone-320`) in the system Chrome channel (`PLAYWRIGHT_CHANNEL` overrides it).
Set `E2E_PORT` to pick the port (default 3032) when a dev server already uses it.

## What answers the API

`support/fake-api.ts` is a **test-only** in-memory double of API contract v1.1 with synthetic
data; `support/fixtures.ts` routes every same-origin `/api/v1/**` request to it and checks that
writes carry the app's exact Origin. It is never imported by application code.
`support/mock-server.ts` serves the same double over loopback HTTP for manual checks:

```sh
node apps/web/e2e/support/mock-server.ts            # 127.0.0.1:8032, MOCK_AUTH=required optional
NEXT_PUBLIC_API_URL=/ FINBOY_API_ORIGIN=http://127.0.0.1:8032 pnpm --filter @finboy/web dev --port 3032
```

These runs prove UI behaviour against the contract: sign-in return paths and in-place
re-authentication, Sources and import outcomes with recovery, staged uploads, the review queue
(decisions, merge preview, undo, conflicts, drafts, focus), >200-record paging, exact evidence
links, overview/obligations/simulation staleness, assistant pairing, voice states (synthetic
microphone stream; denied permission), playback states with a generated tone
(`fixtures/synthetic-tone.mp3`), privacy previews/export, the read-only sample, fixed-layer
obstruction at phone widths, navigation contrast, titles, offline and no-WebGL.

They do **not** prove live integration with the FastAPI backend, real Google consent, real
microphones, provider speech quality, or playback on a phone. Run the same suite against the
assembled backend during integration and record human-only checks separately.
