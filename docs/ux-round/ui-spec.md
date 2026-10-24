# UX round — product UI specification

Owner: Product (Agent 2), branch `feat/finboy-ux-frontend`. Consumes API contract **v1.2.0**
(`docs/ux-round/api-contract.md`: bootstrap `2e42622`, continuation `c05b44b`; v1.1.1 cancel and
v1.2.0 lineage changes read from the backend branch at `b14a9e9`, whose captured HTTP examples
parse through these clients). The UI never computes money: every
amount, total, deduction and preview comes from the API; the web app only formats paise and
converts typed rupees to paise.

## Information architecture

| Route | Title | Purpose |
| --- | --- | --- |
| `/dashboard` | Overview | Estimate beside its calculation, freshness, exclusions; exceptions; categories; obligations; simulation |
| `/transactions` | Transactions | Paginated records; `?selected=<id>` opens the exact record |
| `/review` | Review | All-month unresolved queue with a persistent decision panel (desktop) or sheet (phone) |
| `/assistant` | Ask FinBoy | Session-only question/answer pairs, voice capture, playback |
| `/sources` | Sources | Connected account, scan controls, coverage, staged upload, recent imports, sample link |
| `/import/<id>` | Import results | Outcome-led status of one import with issues and recovery |
| `/privacy` | Privacy & data | Disconnect, export, previewed deletion, separation inventory, activity |
| `/demo` | Sample household | Public read-only synthetic data (`GET /api/v1/demo` only) |
| `/login` | Sign in | Household password; `?next=` returns to a validated app path |
| `/connect` | — | Redirects to `/sources`, preserving a validated `?error=` (registered OAuth callback) |

Navigation: desktop sidebar (Overview, Transactions, Review, Ask, Sources, Privacy) with the
household identity, service status, Shortcuts and Sign out in its footer. Phones: compact header
with an **Account and settings** menu (Privacy & data, Keyboard shortcuts, Sign out) and a
five-tab bar (Overview, Transactions, Review, Ask, Sources). No account control floats over content.
The tab bar hides while a text field is focused so the on-screen keyboard can't push it over the
field or the form's action; `scroll-padding` keeps keyboard focus clear of fixed chrome.

## Page system

One `PageHeader`: a direct task title (28–32 px, semibold, −0.03em), one sentence of support
text, actions on the right. Daily screens use `surface` cards (28 px radius) and no WebGL; the
brand scenes stay on the marketing page. Status colours: amber tints for attention, `positive`
(#047857) for verified/income, `negative`/`destructive` (#c4262e) for destructive actions.

## State matrix

Each panel loads independently through `useResource`; a failed secondary panel never blanks the
primary task. Failures use one content map (`lib/messages.ts`): what didn't happen, whether
anything changed, the next action, plus the request ID as a reference.

| State | Source | Presentation | Recovery |
| --- | --- | --- | --- |
| Loading | first request for a key | `LoadingPanel` (polite status) | — |
| Refreshing | newer request, data kept | "Refreshing…/Updating…" label; stale rows dimmed | — |
| Stale | data from an earlier key or failed refresh | Title says "showing the last loaded …" | Try again |
| Empty | `total = 0`, no filters | Task-specific empty state with Sources/sample actions | — |
| Filtered-empty | `total = 0`, filters set | "No records match these filters" + remaining `unresolved_total` | Clear filters |
| Partial | coverage `partial`, import `partial`, `truncated` | Attention strip / outcome copy | Retry, continue, select files |
| Expired (401) | any household call | In-place **Sign in to continue** dialog; drafts stay in memory | Sign in, then retry |
| Wrong password | `invalid_credentials` | Field error with `aria-invalid` | — |
| Denied (403) | `origin_denied`/`origin_not_allowed` | "This page isn't allowed to make that change" | Reload |
| Missing (404) | `not_found` | "It may have been removed…"; never an upload error | Back to the list/Sources |
| Conflict (409) | `version_conflict`, `decision_conflict` | Nothing saved/overwritten; edits kept | Load the latest version |
| Read-only | `demo_read_only` | Sample never writes | — |
| Original files | `original_files_required` | Upload stager in retry mode | Select original files |
| Offline | `navigator.onLine === false` / network | Global banner; panels keep last view | Auto-reload on `online` |
| Unavailable / timeout | 5xx / client timeout | Task-specific copy | Try again |
| Invalid response | schema mismatch | Not displayed; reference shown | Try again |

## Session, return paths and drafts

- `HouseholdGate` checks `/auth/session` once per visit; signed-out visits go to
  `/login?next=<path+query>`. `safeReturnPath` accepts only allowlisted same-origin app paths
  (≤512 chars); anything else returns to `/dashboard`.
- Later 401s open the in-place re-authentication dialog. Passwords, session values, questions
  and recordings never touch browser storage. Only two UI preferences are stored: reply style
  (sessionStorage) and single-key shortcuts on/off (localStorage).
- Record corrections are kept per record in memory (`lib/drafts.ts`). Escape, outside click and
  Close ask "Discard your changes?"; in-app links ask "Leave without saving?"; reload/close uses
  `beforeunload`. Browser Back keeps the draft in memory and restores it with a notice.

## URL state

`/transactions`: `scope` (month|all), `year`, `month`, `status`, `category`, `kind`, `source`,
`q` (debounced 350 ms), `dataset=quarantined`, `offset`, `selected`. `/review`: the same filters
except status (always unresolved, any date unless a month is chosen), plus `selected`.
`/dashboard`: `year`, `month`. Paging pins the first page's `data_version`; a 409 asks to restart
from the first page instead of skipping or repeating records.

## Review decision model

Reason first (title, what it means, what resolves it), then payment verification and extraction
completeness as separate facts (no percentages), then only relevant actions:

- Unresolved, clean form → **Confirm**; dirty form → **Save and confirm** (one atomic decision
  with `correction`), **Save without confirming**, **Discard changes**. Reject is disabled while
  the form is dirty.
- Possible duplicate (or "It's a duplicate…") → side-by-side comparison against independent,
  compatible candidates (confirmed records included) → **Preview merge** → **Merge into …**, or
  **Not a duplicate — keep both**.
- Rejected → **Reopen for review**. Merged → link to the surviving record.
- Every decision shows its outcome and an **Undo** bar (version-checked); history lists decisions
  with backend `can_undo`. After a decision the queue advances and focus moves to the next
  record's heading; closing a record returns focus to its row.
- Editable facts: merchant, amount, date (IST), direction, type, category. A date the person
  types can't be in the future; an unchanged evidence date never blocks Confirm (emails can
  carry a later date, such as a scheduled debit). Direction/type contradictions (e.g. a refund
  marked money out) are blocked with a field error, matching the API's `invalid_decision`.

## Import outcomes (`lib/import-outcome.ts`)

| Outcome | Title | Primary action |
| --- | --- | --- |
| queued/running | Getting ready / Importing… (`n of m` checked) | Cancel import |
| complete, nothing new | No new records found | Back to Sources (or Continue scanning) |
| complete, all new need review | N new records need review | Review N records |
| complete, some need review | N new records added · M need review | Review M records |
| complete, all confirmed | N new records added | See your overview |
| partial | M records need review · F emails couldn't be read | Review, else retry |
| failed / interrupted | Import stopped / was interrupted | Retry F emails · Select the original files again |
| cancelled | Import cancelled | Review saved records / Back to Sources |

Truncated scans add a note and **Continue scanning this window** when `can_continue`. Allowing
scans never claims to resume a job; Scan now starts a new one.

## Assistant and voice

A turn = submitted question + reply style + state (pending, answered, failed, cancelled) +
answer. Turns live in module memory (≤20) so evidence links and Back keep them. One request at
a time, with Cancel. Answers show the resolved period in the product's date style ("October
2026", or "1 Oct 2026 – 24 Oct 2026") formatted from `resolved_period.start`/`end`, because
the API's `label` is an ISO range; then `fact.label`, `warning_labels`, and
evidence links to `/transactions?selected=<id>` with date, type and source count; sampled
evidence says "showing n of total — a sample". Display text uses `lang` from
`display_language`/`display_script` (`hi-Latn`, `ml-Latn`, `hi`, `ml`, `en-IN`).

Voice: idle → requesting (Cancel) → recording (elapsed, time left, live level from the real
microphone, Stop and transcribe, Discard; auto-stop before 30 s, 3 MB cap) → transcribing
(Cancel) → review (edit, Discard transcript, Record again; never auto-sent). Errors distinguish
blocked permission, missing device, busy device, unsupported browser, empty audio and transcription
failure. Playback: Play answer prepares audio under the tap and plays; if autoplay rules block it,
**Audio ready — play**; failures show an alert with **Try audio again**; text always stays.

## Privacy

Disconnect (revoke Google access) and deletion are separate. Deletion and "also delete" both show
`POST /privacy/deletion-preview` first: removed records/obligations with date range, retained
shared records (kept but possibly on hold), activity history retained, 7-day backup retention,
and an export option; one confirmation sends `expected_version`; a 409 refreshes the preview.
Export (`POST /privacy/export`) runs only on click and saves the validated JSON.

## Accessibility contract

Text plus icons everywhere; WCAG AA contrast measured on rendered surfaces (tab labels 11 px,
`ink-soft` on ≥94% white); 44 px targets; field errors linked with `aria-describedby` and
`aria-invalid`; dialogs trap and return focus; outcome and decision messages use polite live
regions, failures use `role="alert"`; skip link; keyboard help (`?`), search (`/`), queue
(`j`/`k`) shortcuts that are inactive while typing and can be turned off.

## Product outcome events

Only `POST /privacy/task-outcomes` with `evidence_opened` (citation → record, with the record
ID), `overview_explanation_opened` (following an overview explanation link) and `review_completed`
(the refreshed server response reports zero unresolved records). No amounts, merchants, questions, URLs or mailbox content; failures are ignored.

## Browser harness

`pnpm test:e2e` builds with `NEXT_PUBLIC_API_URL=/` and runs Playwright (system Chrome) at
1440×1000, 390×844 and 320×740. `/api/v1/**` is answered by the **test-only** contract double in
`apps/web/e2e/support/fake-api.ts` (synthetic data). These runs prove UI behaviour against the
contract — not live integration, real Google consent, microphone hardware or phone playback.
`e2e/live.spec.ts` (opt-in, `E2E_LIVE_API=1`) repeats the core journeys through the same-origin
proxy against a real API on a disposable database; the proxy origin must be HTTPS, so local runs
use a temporary private certificate trusted only via `NODE_EXTRA_CA_CERTS`
(`apps/web/e2e/README.md`).

## Integration clarifications

The human transferred integration ownership after Product finished at `5fd2467`. Both
assistant questions and cash-flow simulations send `include_overdue_line: true` for
contract v1.2.0; older deployed clients retain the compatible four-line response by default.
The answer unit also localizes policy, period, supporting-record headings/count qualifiers
and playback controls across native and romanized Hindi/Malayalam. Provider speech remains
native. This establishes UI behavior, with fluent-user comprehension still requiring a pilot.
Opening an explanation is a click event, never a claim of comprehension.
