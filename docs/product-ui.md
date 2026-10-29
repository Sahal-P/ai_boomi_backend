# Product UI

How the household web app is built after the UX remediation round (findings F01–F38).
Behaviour, states and copy rules are specified in `docs/ux-round/ui-spec.md`; visual tokens in
`docs/design-system.md`; the API it consumes in `docs/ux-round/api-contract.md` (v1.1.2).
Phase-1 integration history (design snapshot, package provenance) stays in
`docs/handoffs/agent-5.md` and `docs/handoffs/design-snapshot.json`.

## Shape

- Routes: `/dashboard` (Overview), `/transactions`, `/review`, `/assistant`, `/sources`,
  `/import/<id>`, `/privacy` inside the authenticated `(app)` shell; public `/`, `/demo`,
  `/login`, `/privacy-policy` and `/terms`. `/connect` only forwards the registered OAuth
  callback to Sources.
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
- Branding uses the approved sunflower companion tile (a **b** with a speech-bubble counter)
  and outlined **FinBoy** wordmark. Navigation, sign-in, footer, favicon and app icons share
  this identity; [brand assets and usage](branding.md) lists the standalone SVG variants.

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

## Sign-in and quick add (sign-up round)

Specified in the [sign-up contract](signup-round/contract.md). The web app learns which ways in
exist from `GET /api/v1/auth/session` (`sign_in`), never from build-time variables.

- **`/login`** (`sign-in-options.tsx`), in order of ease: **Continue with WhatsApp**, Google's
  button, then the owner's household password, collapsed unless it is the only way. The
  WhatsApp link opens a new tab with the login code typed in; wider screens also show it as a
  QR code. The page says it is waiting, checks every 2 seconds and again when the person comes
  back, and replaces an expired code quietly. No on the phone, a full FinBoy and failures each
  have their own state with a way to start again. On phones the options come before the
  illustration. The session-ended prompt reuses the same options.
- **WhatsApp only:** "Prefer WhatsApp? Say hi to FinBoy" on the landing hero and `/login`, shown
  only while sign-ups are open, opens the chat with "Hi FinBoy" typed.
- **Quick add** (`quick-add.tsx`): Overview's **Add** button and the empty state "Add what you
  spent today" open a sheet (right on desktop, bottom on phones). Type or **Say it** in
  English, Hindi or Malayalam, with an example in each (the Malayalam one marked `lang="ml"`);
  Enter works like Next. The editable card (money out, money in or
  to pay later; amount; date; to or for; category) saves with one tap. **Undo** rejects the
  entry (a due is dismissed) so it stops counting without waiting in Review, then **Add
  another** or **Done**. A question offers **Ask FinBoy instead**. The sentence is never
  stored; records show "Added by you".
- **Privacy → Your sign-in:** the masked WhatsApp number and Google email, Link WhatsApp or
  Google, **Sign out on every device** and **Delete my account** (one confirmation, then back to
  the landing page). Households that can't connect Gmail yet see "Gmail import is invite-only
  while Google reviews FinBoy" on Privacy and Sources instead of a Connect button.
- Overview's toolbar keeps one row at 320 px: Add, the period, and Refresh as an icon on phones.

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

The finboy.io frontend is built with `NEXT_PUBLIC_API_URL=/`. Nginx routes `/api/v1/*`
directly to the loopback API, so browser requests and host-only cookies are same-origin.
The optional HTTPS API-origin mode remains supported for the old frontend during migration;
plain-HTTP development uses `omit`. The sidebar's service dot checks every 30 s and
shows "Service unreachable" only after two failed checks in a row (`lib/health-check.ts`). The
optional Next rewrite origin must be HTTPS. No provider key, token or secret is ever in a `NEXT_PUBLIC_*` variable,
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
  (`E2E_PERF=1`) are opt-in review tools. `signup.spec.ts` covers WhatsApp sign-in (waiting,
  signed in, declined, full), the landing link, legal pages, quick add with undo, the
  Malayalam example, Gmail's invite-only state and account deletion.
- `apps/web/e2e/live.spec.ts` (`E2E_LIVE_API=1`): the core journeys through the same-origin
  proxy against a real API on a disposable database, with synthetic `.eml` files only.
- Human-only acceptance (real Google consent, microphones, phone playback, screen readers,
  device performance, observed comprehension) is recorded separately in the handoffs.
