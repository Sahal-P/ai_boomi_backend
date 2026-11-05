# Admin round — contract (5 November 2026)

FinBoy gets an **admin panel** at `/admin` for the people who run it. An admin signs in with an
email and password and can see how FinBoy is used and act on households (Premium days, AutoPay,
pay links, sign-out, suspend and restore, erase), payments and sign-ups, without SSH.

It supersedes earlier statements only where it says so:
- "erasure stays operator-run" (pilot round): it stays operator-only, and an admin can now run
  the same erasure from the panel as well as from `pilot.cli` and the household's own "Delete my
  account";
- "every route needs a household session" (production round): `/api/v1/admin/*` needs an admin
  session instead (below), never a household one.

Everything else still binds: every no-storage rule, exact-origin CORS and Origin checks, `__Host-`
cookies, "WhatsApp never merges or deletes records" and every privacy promise to households.

## Human decisions (5 November 2026)

- **Activity, not money.** Admins see plans, dates, counts, usage, delivery states and which
  sign-in methods are linked. They never see a household's records or contact details (below).
- **Email and password only.** No authenticator codes. Sign-in is rate-limited, an account locks
  after repeated failures, and every admin action is in an audit log.
- **Live switches stay on the server.** The panel shows every flag and limit; changing one is
  still an edit to `/etc/finboy/production.env` and a restart, so startup safety checks apply.
- **Defaults chosen with the plan:** the panel lives on the same web app and API (no new domain,
  certificate or CORS origin); admin accounts live in the database and the first one is created
  on the server; erase and suspend are in the panel, confirmed by typing the household's short ID.
- **Where it lives:** branch `feat/finboy-admin` from `main` `1eadf04`; loopback API 8081 and web
  3081; disposable database `finboy_admin`; one additive migration, `0014_admin`; no new
  dependency.

## What an admin sees

| Page | Shows | Actions |
| --- | --- | --- |
| Overview | Households by kind and status; sign-ups against `SIGNUP_LIMIT` and the waitlist; active today, 7 and 30 days; plans; FinBoy's own payments and ₹ received this month; today's AI and voice use; WhatsApp deliveries and imports in 7 days by state | none |
| Households | Search by household ID (or its first characters) or an exact phone number; filters for kind, status, plan and last active | open a household |
| Household | Kind, status and dates; WhatsApp / Google linked; Google's already-masked email; plan, trial end, paid-through, renewal, grace; FinBoy payments; today's usage against the limits; counts of records and dues by status, budgets, whether a savings goal is set; imports, statement imports and Gmail by state; WhatsApp replies on/off (STOP), opt-ins and language | per kind, below |
| Payments | FinBoy's ₹299 sales records: date, household short ID, amount, state, kind, payment mode, our transaction ID, PayU's payment ID and error code | re-check one with PayU |
| Sign-ups | Agreed, pending and the limit; the waitlist by language and the oldest wait; stale pending sign-ups | tidy stale sign-ups |
| System | Environment, release, database, schema head, every flag and limit, providers as configured / missing / off, active imports, open payments | none |
| Admins | Admin emails, status and last sign-in; your own signed-in browsers | add (temporary password), disable, change your password, sign out other browsers |
| Audit log | Who did what, to which household, when | none |

**Never shown anywhere:** amounts, payees, categories, labels or notes of a household's records;
budgets' and goals' amounts; statement totals, bank names and card digits; message text, media
and transcripts; WhatsApp numbers (not even masked, because masking needs decrypting); the
billing email and phone; any household name (the owner shows as "Owner"); and every hash,
encrypted column, key and token. The response models in `services/admin/views.py` are the
boundary: none has a field for any of these, and a test walks every admin response model to keep
it that way. FinBoy's own ₹299 payments are the only money shown.

**Phone search** compares the typed number's keyed hash (`HMAC(TOKEN_ENCRYPTION_KEY, "sender"…)`,
the same one WhatsApp uses) with the stored one, so nothing is decrypted or listed. Ten digits get
India's 91 in front.

## Households and what an admin may do

| Kind | Allowed |
| --- | --- |
| Owner | view only |
| Pilot | suspend, restore, erase (through the pilot eraser) |
| Self-serve | sign out everywhere, suspend, restore, erase; with billing on: Premium days, pay link, cancel AutoPay (when on AutoPay) |
| Pending sign-up (never agreed) | erase (discarded entirely, as tidy does) |
| Former pilot, deleted | view only |

A suspended household allows restore and erase only. The API refuses anything else with
`action_not_allowed` (409), and the panel hides those buttons. Every action and its audit entry
commit together.

- **Suspend** stops everything until restored: no web session (`account_suspended`, 403), no new
  sign-in, no WhatsApp reply (messages are recorded as `disabled`, as for a deleted household), no
  reminders or check-ins, no pay link, no renewal notice or charge. It ends every web session
  (session epoch +1) and turns AutoPay off at the bank (best effort, like erasure), so restoring
  never restarts charges silently. The WhatsApp binding's own on/off stays the person's STOP
  choice, so restoring never turns replies back on after a STOP.
- **Erase** runs exactly what the household itself or `pilot.cli erase` would
  (`services/accounts/erasure.py`, shared with "Delete my account"): AutoPay off, Gmail revoked,
  records erased, the household's own `account.deleted` / `pilot.erased` entry kept. It needs the
  short ID typed back (`confirmation_mismatch`, 422) and waits for a running import (`try_later`).
- **Premium days** (1–366) extend paid-through like `billing.cli grant`. **Pay links** last 7 days
  and are shown once, because anyone holding one can pay for that household.

## Sign-in and sessions

- Passwords are 12–256 characters and not the email, stored as scrypt hashes (the household
  password's helper). An unknown, disabled or locked account still costs one scrypt check, and
  every failure answers the same `admin_login_failed`.
- Five failures in a row lock the account for 15 minutes. Sign-in is also limited to 10 attempts
  a minute per address and per email in the API (production runs one worker), and nginx applies
  the household login's rate limit to the admin login.
- A session is a random 32-byte token in the cookie `__Host-finboy_admin` (Secure, HttpOnly,
  SameSite=Strict, `Path=/`, no Domain; `finboy_admin` on loopback HTTP); only its SHA-256 is
  stored, in `admin_sessions`. It lasts `ADMIN_SESSION_HOURS` (default 8). It is not signed with
  `WEB_SESSION_KEY`, which also signs household sessions, login codes and pay links, so that key
  can never mint an admin.
- The household cookie never opens admin routes, and the admin cookie never opens household
  routes. Admin routes have no loopback shortcut: they need an admin session everywhere.
- A new admin gets a temporary password, shown once to the admin who added them, and must change
  it first: until then only `/admin/session`, `/admin/password` and `/admin/logout` answer
  (`admin_password_change_required`, 403). Changing your password ends your other browsers.
  Disabling an admin ends all of theirs. Nobody can disable themselves or the last active admin.
- The server CLI manages accounts and recovers a lost, locked or disabled one:
  `uv run --package finboy-api python -m finboy.services.admin.cli create|list|disable|enable|reset-password --email …`.
  Only the CLI re-enables a disabled admin; the panel can disable but never re-enable.
  It asks for passwords without echo; `--password-stdin` exists for CI and tests only. No admin
  password ever goes into an env file, Git or the browser bundle.

## What gets stored (migration `0014_admin`, additive)

| Kept | Where |
| --- | --- |
| Admin email (lowercase), scrypt hash, must-change flag, failure count, lock end, last sign-in, who added them, disabled time | `admin_users` |
| Each signed-in browser: token SHA-256, a coarse device label ("Chrome · macOS"), created, last seen, expiry, revoked | `admin_sessions` |
| Each admin action: who, a fixed action name, the household ID (kept after erasure), allowlisted details (`days`, `payment`, `admin`, `removed`, `via`, `outcome`), request ID, time | `admin_events` |
| When a household was suspended | `users.suspended_at` |

A failed sign-in for an unknown email records no email. The admin audit log is separate from the
household's own `audit_events`, which households read on their Privacy page and which records no
actor. Downgrade refuses while admin accounts or suspended households remain.

Logs carry only `admin.login` with `outcome`, and `admin.action` with `code`; never an email,
password, token, phone number or body.

## API (additive)

Every route is under `/api/v1/admin`, needs an admin session except `login`, answers `no-store`
data from `views.py` only, and keeps the exact-Origin check on writes. Admin request bodies are
capped at 8 KB.

| Route | Purpose |
| --- | --- |
| `POST /login`, `POST /logout`, `GET /session`, `POST /password` | Sign-in, sign-out, who is signed in, change password |
| `GET /overview`, `GET /system` | Counts; flags, limits and providers |
| `GET /households?q=&kind=&status=&plan=&active=&offset=` | Search, 50 a page |
| `GET /households/{id}` | One household |
| `POST /households/{id}/sign-out`, `/suspend`, `/restore`, `/premium`, `/autopay/cancel` | Act; answer the updated household |
| `POST /households/{id}/erase` (`{"confirm": short ID}`), `/pay-link` | Erase; a 7-day pay link |
| `GET /payments?status=&offset=`, `POST /payments/{id}/reconcile` | FinBoy payments; ask PayU |
| `GET /signups`, `POST /signups/tidy` | Sign-up counts; tidy |
| `GET /admins`, `POST /admins`, `POST /admins/{id}/disable` | Admin accounts |
| `GET /sessions`, `POST /sessions/sign-out-others` | Your signed-in browsers |
| `GET /audit?offset=` | The audit log, 50 a page |

New fixed error codes: `admin_required` (401), `admin_login_failed` (401),
`admin_password_change_required` (403), `account_suspended` (403), `weak_password` (422),
`confirmation_mismatch` (422), `admin_exists` (409), `last_admin` (409), `action_not_allowed`
(409), `not_found` (404).

Also fixed in this round: the money and transaction routes now answer a stale, deleted or
suspended household's session with its own code (401 / 403) instead of a 500.

## Web

`/admin` is a separate area of the same Next.js app, outside the household `(app)` group:
`/admin/login` and the console pages Overview, Households, Payments, Sign-ups, System, Admins,
Audit log and Password. It reuses FinBoy's tokens, primitives, navigation pattern and review
two-pane layout. Admin pages are `noindex`, disallowed in robots.txt, left out of the sitemap,
sent with `X-Frame-Options: DENY` and `Cache-Control: no-store`. The browser only steers; the API
enforces every rule. Actions wait for the server (no optimistic updates); erase and suspend ask
for confirmation, erase with the short ID typed back.

## Release

With the human's approval at the time:
1. Backend first, as `docs/production.md` describes: validated backup, active-import check,
   `0014_admin`, drift check, switch `current`, restart `finboy.service` only.
2. nginx: the admin login rate limit on finboy.io; 404 for `/api/v1/admin/` on the antlegs.in API
   host, which serves only Gmail and Meta callbacks. `nginx -t`, then reload.
3. Push `main`; CI releases the web.
4. The human creates their own admin on voxpay with the CLI (it asks for the password). Nobody
   else types or receives a production admin password.

## Not in this round

Authenticator codes or passkeys, roles with fewer rights, changing flags from the panel, viewing
any household content, sending WhatsApp messages from the panel, refunds (PayU's dashboard),
exports.

## Verification

Recorded 5–6 November 2026 on `feat/finboy-admin` (uncommitted), against loopback API 8081, web
3081 and the disposable `finboy_admin` database with `OPENAI_API_KEY` blank.

**Automated:**
- `pnpm check`: Ruff and ESLint clean; 1419 API unit tests (sign-in, timing guard, lockout,
  throttle, session separation, cookie flags, Origin, 8 KB cap, temporary passwords, the
  response-model boundary, the action matrix, phone hashing, suspension gates, server re-enable),
  81 web unit tests and 13 SEO tests passed; typecheck clean. `pnpm build` passed with every
  `/admin` route.
- `pnpm db:migrate` (head `0014_admin`), `pnpm db:check` ("No new upgrade operations detected"),
  `pnpm test:integration`: 110 passed, including the admin flows (CLI create, list, reset, enable;
  lockout; sessions and password change; temporary passwords; disable; search by ID and exact
  number with no content in any response; suspend and restore across web, pay links and renewals;
  erase for self-serve, pilot and pending households, refused for the owner; Premium days,
  payments and re-check; tidy; overview and system; the downgrade guard, run down and up inside a
  rolled-back transaction). Run alone it passed 3 times out of 3. Run while the whole browser suite
  loaded the machine, the statement round's wall-clock budget (2,000 rows saved in under 10 s,
  `test_two_thousand_rows_are_saved_within_budget`) failed twice; it is load-sensitive, not
  affected by this round.
- Playwright against the API double at 1440, 390 and 320 px: `admin.spec.ts` (sign-in and return,
  the temporary-password detour, every page, each action's confirmation, typed short IDs, pay link
  shown once, session loss, titles, no sideways scroll, headers, robots and sitemap) and the admin
  pages in the contrast and three-blur budget, including an open erase confirmation, and the
  phones' More menu. The whole suite: 453 passed, 123 skipped (live-API only), 0 failed.

**Real API in a browser (local):** a CLI-created test admin signed in at
`127.0.0.1:3081/admin`; an exact-number search found the one synthetic household through the
stored hash; its detail showed counts and dates but none of its payees, amounts or number;
suspend (with the short ID typed) and restore round-tripped with their audit entries; a payment
re-check with billing off answered "Payments aren't available right now"; Overview, System,
Admins and Audit log rendered at 1440 px, and Households, the household sheet and the More menu at
375 and 320 px. Synthetic households were removed afterwards.

**Not verified yet:**
- Production: the release, nginx's 429 on the admin login, and the first real admin account.
- The CI live job's admin journey (`e2e/live.spec.ts`) runs only in GitHub Actions.
- Billing-on actions (Premium days, pay links, AutoPay off) against the real API in a browser:
  covered by database tests and the browser double only.
