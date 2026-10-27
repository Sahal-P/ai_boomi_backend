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

- **Sign-up inside WhatsApp:** a link or QR opens WhatsApp with "Hi FinBoy" (or "नमस्ते FinBoy")
  typed. When `SIGNUP_ENABLED` is on, a message from an unknown number creates a household that
  has not yet agreed, plus its binding. The reply language comes from the first message:
  Devanagari means Hindi, anything else English; "hi"/"en" switch it later. The existing
  consent card follows, in that language. Nothing else works until "Yes", and "No" erases the
  new household and keeps nothing.
- **Limits:** at most 200 households that haven't agreed exist at once; a newer unknown number is
  ignored. Households that never agree are removed after 7 days by
  `python -m finboy.services.signup.cli tidy` (run by the reminder timer). When `SIGNUP_LIMIT`
  households have agreed, a new number gets the "full" reply instead of the consent card. JOIN
  adds it to `signup_waitlist` and then removes the household.
- **Web sign-in with WhatsApp:**
  1. "Continue with WhatsApp" creates a login request bound to that browser by a random nonce
     cookie (`__Host-finboy_login`, 10 minutes). It returns a wa.me link with
     "FinBoy login code XXXX-XXXX" typed in. The code is 8 characters from a 31-character
     alphabet, stored only as an HMAC, valid for 10 minutes and used once.
  2. The person sends it from their WhatsApp. FinBoy answers with a card naming the browser
     ("Chrome · Android"): a known household gets [✅ Yes, it's me] [❌ No]; a new number gets the
     consent text with [✅ Yes, create my account] [❌ No].
  3. Yes confirms the request. The waiting browser then completes it with its nonce and receives
     the session. A wrong browser, an expired or reused code, or No all fail closed.
  4. A pilot household's code is refused with "web isn't part of the pilot".
- **Linking:** "Link WhatsApp" uses the same code with purpose `link`. Its card asks
  "Link this WhatsApp to your FinBoy account?". A number already bound to another household that
  has records cannot be moved.
- **Diary:** self-serve WhatsApp households get the voice diary that pilot households have:
  voice or text records through review, ✅/✏️/❌ with undo, dues, opt-in reminders and हिसाब
  ("summary" in English). Pilot caps, enrollment, consent visits and `pilot.cli report` stay
  pilot-only.
- **Replies:** FinBoy replies to the env allowlist (as before) or to an enabled database binding
  whose HMAC matches the sender. Self-serve bindings keep a Fernet-encrypted copy of the number,
  used only for opted-in reminder templates. Raw numbers never enter logs or reports.

## Google

`POST /api/v1/auth/google` accepts the ID token from Google Identity Services. FinBoy verifies
it against Google's public certificates (fetched with httpx and cached by max-age): audience
`GOOGLE_SIGNIN_CLIENT_ID`, issuer `accounts.google.com`, expiry, `email_verified`, and a nonce
equal to the browser's login cookie. FinBoy keeps only `sha256("google:" + sub)` and a masked
email. The Google script loads only on `/login`. Google's basic sign-in scopes need brand
verification, not the restricted-scope security assessment that Gmail needs.

## Quick add

- `POST /api/v1/entries/preview` reads one typed or transcribed sentence with the WhatsApp
  statement reader, in English or Hindi. It returns kind, amount, direction, counterparty,
  category, date and due day, and nothing is stored. Amounts must be grounded deterministically,
  as on WhatsApp.
- `POST /api/v1/entries` saves the fields the person saw and may have edited. Money in or out
  becomes one `manual_entry` line through the import pipeline and is confirmed with the existing
  versioned decision (Save is the explicit confirmation, and it can be undone). A due becomes an
  `upcoming` `loan` obligation.

## Open-beta safety

- **Daily limits:** `usage_counters` caps AI use (questions, previews, WhatsApp statements) and
  voice use (transcription, speech) per household per IST day, at `DAILY_AI_LIMIT` (100) and
  `DAILY_VOICE_LIMIT` (60). Hitting a limit gives a friendly message and a fixed code.
- **Throttles:** sign-in starts are throttled per process, sized for an event crowd.
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
- `whatsapp_bindings.encrypted_sender`; `signup_waitlist`; `usage_counters`.
- Widened CHECKs: source and import mode `manual_entry`; prompt purposes `signup`,
  `web_login`, `link`; receipt error codes `signup_full`, `login_expired`, `usage_limit`.

## Settings

`SIGNUP_ENABLED` (false), `SIGNUP_LIMIT` (100), `SESSION_DAYS` (30), `DAILY_AI_LIMIT` (100),
`DAILY_VOICE_LIMIT` (60), `GOOGLE_SIGNIN_CLIENT_ID` (public client ID, separate from the Gmail
client), `WHATSAPP_PUBLIC_NUMBER` (the business number people message, digits only; public),
`GMAIL_FOR_NEW_ACCOUNTS` (false). None of them is a secret, and none goes into a `NEXT_PUBLIC_*`
variable: the web app reads them from `GET /api/v1/auth/session`.

## Human steps

1. **Meta:**
   - add a real WhatsApp Business number (a SIM not on WhatsApp) and have the display name
     approved;
   - replace the user token that expires on 23 December 2026 with a permanent System User
     token;
   - add an English version of the reminder template.
2. **Google:** create a sign-in-only OAuth client (separate from Gmail) with JavaScript origin
   `https://finboy.antlegs.in`. Complete brand verification: domain in Search Console, plus
   links to `/privacy-policy` and `/terms`.
3. **Release:** approve the production release. Then set the settings above and turn
   `SIGNUP_ENABLED` on.

## Runtime

Branch `feat/finboy-signup`, loopback API 8061 / web 3061, disposable database `finboy_signup`.
Tests mock Meta, Google and providers, and no test suite runs against production.
