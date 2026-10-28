# Sign-up round — one-tap sign-up with WhatsApp, Google as backup

The human approved this round on 27 October 2026 (IST) from main `e06ba9b`. It supersedes the
"no public multi-user signup", "single household" and "web routes stay `LOCAL_USER_ID`-only"
statements in `AGENTS.md`, `docs/production.md`, `docs/phase1/contract.md` and
`docs/pilot/contract.md` only as written here. Every other privacy, money, ingestion, pilot,
production and access rule stays binding.

## Human decisions

- **Sign-up:** WhatsApp first, on the website and straight from a WhatsApp link or QR code.
  Google sign-in is the backup. Both lead to the same household.
- **Who can join:** anyone, until `SIGNUP_LIMIT` (100) self-serve households have agreed to the
  terms. After that FinBoy says it is full and offers a WhatsApp waitlist (send JOIN).
- **First use:** new households add money by typing or speaking ("spent 500 on milk"), see a
  preview, and save it with one tap. Gmail stays limited to Google test users until Google
  verifies FinBoy, so it is hidden for new households (`GMAIL_FOR_NEW_ACCOUNTS=false`).
- **Languages:** WhatsApp replies in Hindi and English. Malayalam replies come later.
- **Off by default:** `SIGNUP_ENABLED=false`. Production behaves as before until the human
  turns sign-up on, after the human steps below.

## Households and sessions

- A self-serve household is a `users` row with `joined_via` `whatsapp` or `google` and no
  personal name ("Household"). It may use the web app and WhatsApp.
- The owner (`LOCAL_USER_ID`) keeps the household password. The owner's allowlisted WhatsApp
  number also signs the owner in. Pilot households (`users.pilot`) stay WhatsApp-only, and web
  routes answer them `403 web_not_available`. The owner's dogfood week is the only exception.
- Sessions are Fernet cookies. The password session keeps payload `finboy:household:v1` (12
  hours). Sign-ups get `finboy:user:v2:<household>:<epoch>` for `SESSION_DAYS` (30). Each
  request checks that the household exists, is not deleted and has the same `session_epoch`.
  Deleting the account or "sign out everywhere" bumps the epoch. In production the cookies are
  `__Host-`, Secure, HttpOnly, SameSite=Lax. Development uses unprefixed, non-Secure names so
  that loopback HTTP works. Outside production a request without a session still acts as
  `LOCAL_USER_ID`.
- Every household route resolves the household from the session (`CurrentUser`). An ID that
  belongs to another household is answered exactly like a missing one (404).

## WhatsApp

- **Sign-up inside WhatsApp:** a link or QR opens WhatsApp with "Hi FinBoy" typed. The website
  shows "Prefer WhatsApp? Say hi to FinBoy" on the landing page and `/login` while sign-ups are
  open; a printed QR can carry "नमस्ते" instead. When `SIGNUP_ENABLED` is on, a message from an
  unknown number creates a household that has not yet agreed, plus its binding. The reply
  language comes from the first message: Devanagari means Hindi, anything else English;
  "hi"/"en" switch it later. The existing consent card follows, in that language. Nothing else
  works until "Yes", and "No" erases the new household and keeps nothing.
- **Limits:** at most 200 households that haven't agreed exist at once; a newer unknown number is
  ignored. Households that never agree are removed after 7 days: each new admission tidies a
  bounded batch, and `python -m finboy.services.accounts.cli tidy` does the same on demand
  (`counts` prints only the agreed, pending, limit and waitlist counts). When `SIGNUP_LIMIT`
  households have agreed, a new number gets the "full" reply instead of the consent card. JOIN
  adds it to `signup_waitlist` and then removes the household.
- **Web sign-in with WhatsApp:**
  1. "Continue with WhatsApp" creates a login request bound to that browser by a random nonce
     cookie (`__Host-finboy_login`, 10 minutes). It returns a wa.me link with
     "FinBoy login code XXXX-XXXX" typed in. The code is 8 characters from a 32-character
     alphabet (no 0/O or 1/I), stored only as an HMAC, valid for 10 minutes and used once. On a
     computer the page also shows the link as a QR code; the page polls every 2 seconds and
     checks again as soon as the person comes back to it, and an expired code is quietly
     replaced.
  2. The person sends it from their WhatsApp. FinBoy answers with a card naming the browser
     ("Chrome · Android"): a known household gets [✅ Yes, it's me] [❌ No]; a new number gets the
     consent text with [✅ Yes, create it] [❌ No] (Hindi cards for Hindi households).
  3. Yes confirms the request. The waiting browser then completes it with its nonce and receives
     the session. A wrong browser, an expired or reused code, or No all fail closed.
  4. A pilot household's code is refused with "web isn't part of the pilot".
- **Linking:** "Link WhatsApp" uses the same code with purpose `link`. Its card asks
  "Link this WhatsApp to your FinBoy account?" [✅ Yes, link it]. Only a number whose household
  never agreed (a pending sign-up) moves to the signed-in household; a number that belongs to
  any other household stays there, and FinBoy answers that it is already linked. Two households
  are never merged.
- **Diary:** self-serve WhatsApp households get the voice diary that pilot households have:
  voice or text records through review, ✅/✏️/❌ with undo, dues and हिसाब ("summary" in
  English). Pilot caps, enrollment, consent visits and `pilot.cli report` stay pilot-only.
- **Reminders stay pilot-only for now.** The reminder job sends templates only to allowlisted
  pilot numbers, and reply-time reminders select pilot households too, so self-serve households
  are never offered "🔔 Yes, remind me". Reaching them needs the real business number, an
  English template, and template sends to the encrypted number.
- **Replies:** FinBoy replies to the env allowlist (as before) or to an enabled database binding
  whose HMAC matches the sender. Self-serve bindings keep a Fernet-encrypted copy of the number,
  used only to show it masked ("WhatsApp •••• 0071") and for messages the household asks for (the
  JOIN waitlist, and reminders once they reach self-serve households). Raw numbers never enter
  logs or reports.

## Google

`POST /api/v1/auth/google` accepts the ID token from Google Identity Services. FinBoy verifies
it against Google's public certificates (fetched with httpx and cached by max-age): audience
`GOOGLE_SIGNIN_CLIENT_ID`, issuer `accounts.google.com`, expiry, `email_verified`, and a nonce
that must be the HMAC of the browser's login cookie (`POST /api/v1/auth/google/start` hands the
page that HMAC, never the cookie). FinBoy keeps only `sha256("google:" + sub)` and a masked
email. Google's script loads only where a Google button is shown (sign-in, the session-ended
prompt and Privacy's "Link Google") and only when `GOOGLE_SIGNIN_CLIENT_ID` is set. Google's
basic sign-in scopes need brand verification, not the restricted-scope security assessment that
Gmail needs.

## Quick add

- `POST /api/v1/entries/preview` reads one typed or transcribed sentence with the WhatsApp
  statement reader, in English or Hindi. It returns kind, amount, direction, counterparty,
  category, date and due day, and nothing is stored. Amounts must be grounded deterministically,
  as on WhatsApp.
- `POST /api/v1/entries` saves the fields the person saw and may have edited. Money in or out
  becomes one `manual_entry` line through the import pipeline and is confirmed with the existing
  versioned decision: Save is the explicit confirmation. A due becomes an `upcoming` `loan`
  obligation. Quick adds are labelled "Added by you" and never appear in the imports list.
- **Undo** in the sheet rejects the entry (a due is dismissed), so it stops counting and never
  waits in Review; it stays listed as Rejected and can be reopened from the record. Undoing the
  Save decision itself would only send the entry back to Review.
- Enter in the sentence box works like Next (Shift+Enter and input-method composition still
  type). Without a model (development), the reader takes only the verb and the amount; the
  person fills in the name and category. Production reads them with the OpenAI model, as on
  WhatsApp.

## Open-beta safety

- **Daily limits:** `usage_counters` caps AI use (questions, quick-add previews, WhatsApp text
  messages) and voice use (transcription, speech, WhatsApp voice notes) per self-serve household
  per IST day, at `DAILY_AI_LIMIT` (100) and `DAILY_VOICE_LIMIT` (60). The owner and pilot
  households are exempt. Hitting a limit gives a friendly message and the fixed code
  `usage_limit` (429). Counters are deleted with their household.
- **Throttles:** WhatsApp and Google sign-in starts share one per-process limit of 120 a minute
  (production runs a single worker). It is global, not per visitor, so a flood can delay
  sign-ins for everyone; a per-address limit at the proxy is the next step.
- **Delete my account** (website Privacy page): erases the household's records, sources, dues,
  decisions, prompts, reminders, receipts, deliveries, bindings, identities and login requests.
  It revokes Gmail, bumps the epoch and keeps only the numbered user row (marked deleted) and
  audit counts. WhatsApp still never deletes anything; people delete on the website or ask the
  operator.

## Data kept and never kept

- **Kept:** household rows without names, Google subject hashes and masked emails, WhatsApp
  sender HMACs and encrypted numbers, login-request metadata (code and nonce HMACs, state,
  browser label, timestamps), consent timestamps, daily usage counts, waitlist numbers
  (encrypted), and everything earlier rounds keep.
- **Never kept:** login codes, ID tokens, Google names or photos, message text, transcripts,
  audio, images, quick-add sentences.

## Schema (migration `0009_signup`, additive)

- `users`: `joined_via`, `consented_at`, `session_epoch` (default 0), `deleted_at`.
- `user_identities`: household, provider `google`, unique (`provider`, `subject_sha256`),
  `email_masked`.
- `login_requests`: `code_digest` (unique), `nonce_digest`, `purpose` (`sign_in`/`link`),
  `state` (`pending`/`confirmed`/`declined`/`used`), household, binding, `device`, timestamps,
  expiry.
- `whatsapp_bindings.encrypted_sender`; `signup_waitlist`; `usage_counters` (deleted with their
  household).
- Widened CHECKs: source and import mode `manual_entry`; prompt purposes `web_login` and `link`;
  receipt error codes `signup_full`, `login_expired`, `usage_limit`, `web_not_available`.

## Settings

`SIGNUP_ENABLED` (false), `SIGNUP_LIMIT` (100), `SESSION_DAYS` (30), `DAILY_AI_LIMIT` (100),
`DAILY_VOICE_LIMIT` (60), `GOOGLE_SIGNIN_CLIENT_ID` (public client ID, separate from the Gmail
client), `WHATSAPP_PUBLIC_NUMBER` (the business number people message, digits only; public),
`GMAIL_FOR_NEW_ACCOUNTS` (false). None of them is a secret, and none goes into a `NEXT_PUBLIC_*`
variable: the web app reads them from `GET /api/v1/auth/session`.

## Human steps

1. **Meta:**
   - add a real WhatsApp Business number (a SIM not on WhatsApp) and have the display name
     approved. The test number only replies to its registered test recipients (at most 5), so
     strangers cannot sign up until this is done;
   - replace the user token that expires on 23 December 2026 with a permanent System User
     token;
   - add an English version of the reminder template (needed before reminders reach self-serve
     households).
2. **Google:** create a sign-in-only OAuth client (separate from Gmail) with JavaScript origin
   `https://finboy.antlegs.in`. Complete brand verification: domain in Search Console, plus
   links to `/privacy-policy` and `/terms`. Both pages are plain-language drafts with bracketed
   placeholders (grievance officer, contact address); a lawyer should review them and fill the
   placeholders before launch.
3. **Release:** approve the production release. Then set the settings above and turn
   `SIGNUP_ENABLED` on.

## Runtime

Branch `feat/finboy-signup`, loopback API 8061 / web 3061, disposable database `finboy_signup`.
Tests mock Meta, Google and providers, and no test suite runs against production.

## Verification — 27–28 October 2026

Both sign-in options reuse the same browser nonce cookie. Their frontend startup requests must
run sequentially: on a fresh browser, parallel WhatsApp and Google starts can issue different
cookies and invalidate Google's signed nonce. Regression tests cover simultaneous starts and
allow the second provider to proceed when the first provider fails. This does not relax token
verification or enable account creation while `SIGNUP_ENABLED=false`.

- **Automated:** 908 API unit tests; 74 integration tests on `finboy_signup` at head
  `0009_signup` with no drift; 46 web unit tests, lint, typecheck and `pnpm build`; Playwright
  229 passed (119 skipped by design) at 1440×1000, 390×844 and 320×740 against the contract
  double.
- **Live, loopback:** the real API over HTTPS on 8061 behind the web app's same-origin proxy on
  3061, on `finboy_signup`. The phone was a local stand-in that ran the real WhatsApp processor
  for the synthetic number 919000000071 with Meta faked, so nothing was sent. `/login` showed
  the code and QR, and quietly replaced a code the API no longer knew. The English consent card
  named the browser ("Chrome · Mac"). After Yes, the page signed in by itself and opened the new
  household's empty Overview. Quick add in English and Hindi saved and undid entries, labelled
  "Added by you". Privacy showed "WhatsApp •••• 0071". Layouts were checked at 1024×768,
  375×812 and 320×740, and the synthetic household was removed afterwards.
- **Fixed after the live check:** Undo now rejects instead of returning entries to Review;
  Enter works like Next; the WhatsApp button comes before the illustration on phones; the
  Overview toolbar keeps one row at 320 px; Privacy shows the invite-only Gmail line; the
  landing page has "Say hi to FinBoy"; self-serve households are no longer offered reminders.
- **Not verified:** real Meta delivery and taps on a real phone, Google Identity Services with
  a real client, voice quick add with a real microphone and provider, and "Delete my account"
  in a live browser (covered by the integration test and the e2e double). Nothing was deployed.
