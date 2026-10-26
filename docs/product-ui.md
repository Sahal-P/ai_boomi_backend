# Product UI

How the household web app is built after the UX remediation round (findings F01–F38).
Behaviour, states and copy rules are specified in `docs/ux-round/ui-spec.md`; visual tokens in
`docs/design-system.md`; the API it consumes in `docs/ux-round/api-contract.md` (v1.1.2).
Phase-1 integration history (design snapshot, package provenance) stays in
`docs/handoffs/agent-5.md` and `docs/handoffs/design-snapshot.json`.

## Shape

- Routes: `/dashboard` (Overview), `/transactions`, `/review`, `/assistant`, `/sources`,
  `/import/<id>`, `/privacy` inside the authenticated `(app)` shell; public `/`, `/demo` and
  `/login`. `/connect` only forwards the registered OAuth callback to Sources.
- Desktop has a glass sidebar with household identity, service status, Shortcuts and Sign out.
  Phones have a compact header with an **Account and settings** menu and the reference's
  floating five-tab bar (black active capsule, every tab labelled) that steps aside while a
  text field is focused. Nothing else floats over content.
- Every page has one task title (`<title>` "Task · FinBoy") and one `PageHeader` heading;
  Import results adds the glass back button to Sources.
- The theme (`docs/design-system.md`): glass cards on a fixed field, the estimate on a solid
  sunflower card with the reference's action tiles below, records as glass cards under month
  headings, and yellow moments with drawn illustrations for sign-in, empty and all-done states
  and the landing hero. Dotted thinking orbs appear only while FinBoy's AI is working (an answer,
  a transcription, a spoken answer, an import) and resting on Ask's empty state.
- Daily screens carry no WebGL (orbs are 2D canvases). The 3D brand scenes stay in the landing
  page's lower sections, honour reduced motion, and fall back to DOM with `?graphics=off` or a
  failed context probe.

## Data and state

- `apps/web/src/lib/api/` is the only place that talks to the backend: one module per domain,
  each response validated with zod before it reaches a component. `http.ts` adds timeouts,
  classifies failures (session, conflict, offline, unavailable, invalid response, …) and keeps
  only the error `code` and `request_id` from envelopes — never bodies or messages.
- Hooks own request lifetimes: `use-resource` loads each panel independently so a failed
  secondary panel never blanks the primary task; `use-import-run` polls with backoff and
  survives dropped polls; voice and speech hooks own microphone and audio lifetimes.
- Components are presentational. `lib/messages.ts` is the single failure-copy map (what didn't
  happen, whether anything changed, what to do next, plus a reference ID);
  `lib/import-outcome.ts` turns an import run into its title, details and next actions.
- Money is never computed in the browser. Totals, deductions, previews, simulations and
  answers come from the API as integer paise; the UI only formats them and converts typed
  rupees to paise for corrections. Corrections send only changed fields with the record's
  `expected_version`; save-and-confirm is one atomic decision, and every decision can be undone
  while the backend allows it.
- URL state carries filters, period, paging and the selected record (in the list and the
  review queue), so evidence links (`/transactions?selected=<id>`) and Back work exactly.

## Session, drafts and storage

- A 401 opens **Sign in to continue** in place; unsaved corrections stay in memory and the
  failed request can be retried after signing in. Signed-out deep links return through
  `/login?next=` to an allow-listed app path only.
- Unsaved corrections are kept per record in memory (never browser storage) and leaving with
  one asks first. Browser storage holds only the reply-style choice (session) and whether
  keyboard shortcuts are on (local) — never records, questions or answers.
- Assistant turns live in module memory (at most 20) so evidence links and Back keep them.
  Microphone audio is memory-only, stops before 30 seconds or 3 MB, and tracks stop on
  unmount; transcripts are editable and never sent automatically. Speech audio is fetched
  per tap, MIME/size checked, played from a Blob URL that is revoked on replacement or
  unmount; a speech failure keeps the text answer.

## Production configuration

The deployed web app uses `NEXT_PUBLIC_API_URL=/`; Next rewrites `/api/v1/*` to the HTTPS
`FINBOY_API_ORIGIN`, so the browser sends same-origin requests with the host-only household
cookie (`credentials: "same-origin"`; cross-origin development uses `omit`). The origin must be
HTTPS; local proxy checks use a temporary private certificate trusted only through
`NODE_EXTRA_CA_CERTS`. No provider key, token or secret is ever in a `NEXT_PUBLIC_*` variable,
client component or browser request. Product outcome events (`evidence_opened`,
`overview_understood`, `review_completed`) go only to the backend's allowlisted audit endpoint.

## Verification

- `pnpm test:web`: client contract tests (synthetic contract states, phase-1 shapes rejected,
  the backend's captured HTTP examples once that fixture is present, error redaction,
  timeouts, uploads, speech), import outcomes, auth return paths and date formatting.
- `pnpm test:e2e`: Playwright at 1440×1000, 390×844 and 320×740 against a test-only contract
  double (`apps/web/e2e/support/`). It proves UI behaviour, not live integration.
  `theme.spec.ts` checks the theme on rendered pages: WCAG contrast for every text,
  placeholder and form-control boundary, the three-blurred-layer budget, accessibility-setting
  fallbacks and the orbs' behaviour. `capture.spec.ts` (`E2E_CAPTURE_DIR`) and `perf.spec.ts`
  (`E2E_PERF=1`) are opt-in review tools.
- `apps/web/e2e/live.spec.ts` (`E2E_LIVE_API=1`): the core journeys through the same-origin
  proxy against a real API on a disposable database, with synthetic `.eml` files only.
- Human-only acceptance (real Google consent, microphones, phone playback, screen readers,
  device performance, observed comprehension) is recorded separately in the handoffs.
