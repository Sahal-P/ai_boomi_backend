# Subscription round — contract (2 November 2026)

FinBoy gets a paid plan: **FinBoy Premium, ₹299 a month**, paid through **PayU India**. Every
household gets 30 days of Premium, then chooses whether to subscribe. Households that do not
subscribe keep a Free plan; nothing they recorded is ever locked away.

It supersedes earlier statements only where it says so:
- "every finance route needs a session": the PayU return, webhook and mandate endpoints are
  public, and are protected by PayU's SHA-512 hash and by FinBoy's own records instead. The pay
  link endpoints are protected by a short-lived capability token (below);
- Origin checks on state-changing requests: the three `/api/v1/payu/*` endpoints are exempt, like
  the WhatsApp webhook, because PayU (not the web app) posts to them;
- "everything is free during the open beta": Premium features need Premium after the trial.

Everything else still binds: every no-storage rule, "WhatsApp never merges or deletes records",
the daily limits, exact-origin CORS and `__Host-` cookies.

## Human decisions (2 November 2026)

- **Price:** ₹299 a month, the final price. Receipts are payment receipts, not GST invoices.
- **Trial:** 30 days of Premium from sign-up (when the household agrees to the terms).
  Households that signed up before launch get 30 days from `BILLING_LAUNCH_DATE`.
- **After the trial without paying — the Free plan:** typed entries (web quick add, WhatsApp
  text), Home, Transactions, Reports, budgets, the savings goal and the "today / this week / this
  month" check-ups. **Premium** unlocks voice notes and spoken replies, Ask FinBoy (AI answers),
  reading payment screenshots and bill photos, and Google Pay statement import. The daily limits
  (`DAILY_AI_LIMIT`, `DAILY_VOICE_LIMIT`) stay as they are for everyone.
- **Renewal:** launch with one-tap ₹299 payments, each adding one month. UPI AutoPay and card
  auto-renew ("Pay and Subscribe") turn on with `PAYU_AUTOPAY_ENABLED=true` once PayU enables
  Subscriptions on the account.
- **Always included:** the owner's household and the village pilot households never pay.
- **Contact details:** PayU requires a real email and phone with every payment. The phone comes
  from the household's WhatsApp number when linked; the email is typed once. Both are kept
  encrypted (Fernet, `TOKEN_ENCRYPTION_KEY`) for receipts and renewals, and erased with the
  account.
- **Defaults chosen with the plan:** paying during the trial never wastes trial days (the paid
  month starts when the trial ends); AutoPay can be turned off at any time and Premium then lasts
  to the end of the paid month; partial months are not refunded; a failed AutoPay renewal keeps
  Premium for 3 days of grace while FinBoy retries.
- **Where it lives:** branch `feat/finboy-subscriptions` from `main` `9fe4274`; loopback API 8071
  and web 3071; disposable database `finboy_billing`; one additive migration, `0013_billing`;
  no new dependency.
- **Release:** `BILLING_ENABLED` defaults to false. While it is false every household has every
  feature and no billing UI shows, so production is unchanged until the human enables it with
  live PayU keys.

## Plans

`services/billing/plans.py` decides one household's plan from the clock and its rows:

| State | When | Premium |
| --- | --- | --- |
| `included` | the owner (unless `BILLING_OWNER_INCLUDED=false`, for local testing), a pilot household, or billing off | yes |
| `trial` | before `max(consented_at, launch) + 30 days` | yes |
| `active` | before `paid_through` | yes |
| `grace` | an AutoPay renewal is being retried, before `grace_until` | yes |
| `free` | otherwise | no |

- A payment adds one calendar month (IST) to `max(now, trial end, paid_through)`.
- `can_pay` is false while AutoPay is on, and when the household is already paid more than 35
  days ahead.
- The plan rides on `GET /api/v1/auth/session` as `plan` (null while billing is off), so every
  gate in the web app is decided without another request.

## Payments (PayU Hosted Checkout)

Read from docs.payu.in on 2 November 2026.

- **Checkout:** the web app asks the API for a signed form and submits it to
  `https://test.payu.in/_payment` (test) or `https://secure.payu.in/_payment` (production).
  Fields: `key`, `txnid` (`fb` + 23 hex characters), `amount=299.00`,
  `productinfo=FinBoy Premium 1 month`, `firstname=FinBoy` (households have no personal name),
  `email`, `phone`, and `surl`/`furl`/`curl` = `<API_PUBLIC_URL>/api/v1/payu/return` (PayU allows
  50 characters; settings check it). `hash =
  sha512(key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||SALT)`.
- **AutoPay ("Pay and Subscribe"):** adds `si=4`, `api_version=7` and `si_details` (monthly,
  ₹299.00, start = the first renewal date, end = five years on); the hash then ends
  `...udf5||||||si_details|SALT`. PayU's page offers "Register AutoPay" on UPI and cards; a person
  who declines makes an ordinary payment.
- **Results** (the browser's return POST and PayU's Successful/Failed webhooks) are checked with
  the reverse hash `sha512([additional_charges|]SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)`
  in constant time, and must name our key, a known `txnid` and the stored amount. A mandate exists
  only when `status=success` and `payment_source=sist`; its ID is that payment's `mihpayid`.
- **Server calls** (`/merchant/postservice.php?form=2`, `hash = sha512(key|command|var1|salt)`):
  `verify_payment` (reconciliation), `pre_debit_SI` (3 days before a renewal; PayU requires at
  least 48 hours and at most 30 days), `si_transaction` (on the renewal date, outside the NPCI
  peak hours 10:00–13:00 and 17:00–21:30 IST), `upi_mandate_status`/`check_mandate_status`
  (before each pre-debit) and `upi_mandate_revoke`/`mandate_revoke` (turning AutoPay off, a PayU
  requirement before AutoPay may go live).
- **Renewal worker** (`python -m finboy.services.billing.cli run`, a 15-minute systemd timer):
  abandons unpaid checkouts after 2 hours, reconciles anything pending or unanswered for 10
  minutes with `verify_payment`, sends pre-debits, charges renewals, retries a failed renewal
  once during the grace (each debit needs its own pre-debit 48 hours ahead) and then revokes the
  mandate.

## What gets stored

| Kept | Where |
| --- | --- |
| Paid-through time, renewal method, mandate ID and kind, UPI sequence, next charge date, grace end | `subscriptions` |
| Each attempt: our `txnid`, amount, state, PayU's payment ID, the payment mode's category (UPI, CC, DC, NB…), PayU's error code, the period it covers, renewal timing | `billing_payments` |
| The payer's email and phone, Fernet-encrypted; which trial nudge was last sent | `billing_profiles` |

**Never kept:** the PayU salt anywhere outside the backend's private settings; card numbers
(even masked), card tokens, UPI IDs, bank reference numbers, PayU's error messages, request or
response bodies, hashes. None of these is logged either.

**Deleting an account** revokes any AutoPay mandate first (best effort), then deletes
`billing_profiles` and `subscriptions`. `billing_payments` rows stay as FinBoy's own sales
records: amounts, dates, states and PayU IDs, with no contact details.

## API (additive)

| Route | Access | Purpose |
| --- | --- | --- |
| `POST /api/v1/billing/checkout` | household | Optional email, phone, AutoPay; returns `{payment_id, action, fields}` |
| `POST /api/v1/billing/receipt` | public, unguessable payment ID | Status and covered-to date only |
| `GET /api/v1/billing/payments` | household | Payment history |
| `PATCH /api/v1/billing/contact` | household | Update the receipt email |
| `POST /api/v1/billing/autopay/cancel` | household | Revoke the mandate; Premium lasts to the end of the paid month |
| `POST /api/v1/billing/link` | pay-link token | The plan summary for `/pay` |
| `POST /api/v1/billing/link/checkout` | pay-link token | The signed form, as above |
| `POST /api/v1/payu/return` | PayU hash | Settle, then `303` to the web app with only our payment ID |
| `POST /api/v1/payu/webhook` | PayU hash | Settle Successful/Failed events; JSON refund and dispute events are logged and ignored |
| `POST /api/v1/payu/mandate` | confirmed through PayU's mandate-status API | Bank cancellations and modifications |

New fixed error codes: `premium_required` (402), `already_paid` (409), `link_expired` (410),
`billing_unavailable` (503).

**Premium gates:** `/assistant/ask`, `/assistant/transcribe`, `/assistant/speak` and
`/imports/gpay` answer `premium_required` on the Free plan. `/entries/preview` (typed quick add)
stays free.

## Web

- The plan comes with the session. The account menu gains **Plan** (`/plan`): status, what is
  included, Pay ₹299, Turn off AutoPay, the receipt email and payment history.
- One upgrade sheet is mounted in the app shell. Premium controls (the quick-add mic, Ask, speak
  buttons, statement upload) open it on the Free plan, and so does any `premium_required` answer.
- Home shows a quiet strip from 7 days before the trial ends, and an amber chip when a renewal
  fails.
- Returning from PayU lands on `/plan?payment=<id>`: paid (a yellow moment), pending (polling a
  tiny status endpoint) or failed (Try again).
- Pages that submit to PayU set `<meta name="referrer" content="strict-origin">` so PayU's domain
  check sees `https://finboy.io` despite the site-wide `no-referrer`.
- Public pages for PayU's website check: `/pricing`, `/refund-policy`, `/contact`; `/terms` and
  `/privacy-policy` gain subscription terms and PayU as a processor. The business details they
  show live in one file, `apps/web/src/lib/business.ts`; its bracketed values are the human's to
  fill in. Privacy & data says what billing keeps, and deleting an account says when paid
  Premium ends with it.

## WhatsApp

- On the Free plan, a voice note, a photo or screenshot, a statement PDF or an AI question gets a
  short reply in the person's language (English, Hindi, Malayalam) explaining that it is part of
  Premium, with a pay link — and, for voice, how to type it instead. Nothing is downloaded,
  transcribed or metered first. Typed entries and check-ups stay free.
- Inside the 24-hour window, the next reply gains one line when the trial has 3 days left, on
  its last day, and after it ends — once per stage.
- **Pay link** `<WEB_APP_URL>/pay#<token>`: the token is in the fragment, so no server or link
  preview sees it. It is a Fernet token under the session key naming purpose `pay`, the
  household, its session epoch and language, valid 7 days; "sign out everywhere" and deletion
  void it. The page needs no sign-in and shows only the price, the trial date and contact fields.
- Pilot households and the owner never see any of this.

## Release

Human steps, none needed to build or test in test mode:
1. Fill in the business name, address, phone and grievance officer in
   `apps/web/src/lib/business.ts` (the email is `support@finboy.io`), release the web, then finish
   PayU activation and website verification for finboy.io.
2. PayU dashboard → Developers → Webhooks → Payments → Successful and Failed →
   `https://finboy.io/api/v1/payu/webhook`.
3. Ask the PayU account manager to enable Subscriptions and Pay and Subscribe for UPI and cards,
   set the mandate-cancellation webhook to `https://finboy.io/api/v1/payu/mandate`, and whitelist
   finboy.io.
4. Put the live key and salt only in `/etc/finboy/production.env` with
   `PAYU_ENVIRONMENT=production`, `API_PUBLIC_URL=https://finboy.io` and `BILLING_LAUNCH_DATE`;
   migrate; enable `finboy-billing.timer`; set `BILLING_ENABLED=true`; restart `finboy.service`
   only. Add `PAYU_AUTOPAY_ENABLED=true` when PayU confirms Subscriptions.

## Not in this round

Refunds in the app (the operator uses PayU's dashboard and `billing.cli grant`), GST invoices,
WhatsApp reminders outside the 24-hour window (they need a Meta-approved template), yearly plans
and coupons, PayU Payment Links and Zion.

## Verification

Recorded 2 November 2026 on `feat/finboy-subscriptions` (uncommitted), against loopback API 8071,
web 3071 and the disposable `finboy_billing` database, with PayU's **test** key.

**PayU sandbox (real test-mode payments, synthetic household):**
- A ₹299.00 card payment with PayU's published test card returned to the local return URL, and the
  reverse hash of PayU's real response matched (`hash_valid`), before anything was built on it.
- From the app: Pay ₹299 → PayU (UPI `anything@payu` and PayU's UPI simulator) → back on
  `/plan?payment=…` with "You're on Premium · Paid through 2 Jan". Paying during the trial kept the
  trial: the paid month ran 2 Dec – 2 Jan. History showed "₹299 · UPI · covers 2 Dec – 2 Jan ·
  Paid"; no console errors at desktop and 375 px.
- A Hindi pay link (`/pay#…`, no sign-in) opened PayU's page in Hindi (`display_lang`) and returned
  to a Hindi result.
- `si=4` showed PayU's "Register for subscription" page with the mandate details, but the test
  account answered E755 (mandate not registered) and settled an ordinary payment, as designed.

**Live Free plan (local API, owner's trial ended by hand in the disposable database, then
restored):** `/plan` showed "Free plan · Premium ended on 18 Oct"; Ask kept the typed question and
opened the upgrade sheet; `POST /api/v1/assistant/ask` answered 402 `premium_required`.

**Automated:**
- `pnpm check`: Ruff and ESLint clean, 1336 API unit tests and 77 web unit tests passed, typecheck
  passed. `pnpm build` passed, with `/plan`, `/pay`, `/pricing`, `/refund-policy` and `/contact`.
- `pnpm db:migrate` (head `0013_billing`), `pnpm db:check` ("No new upgrade operations detected")
  and `pnpm test:integration` (101 passed) on `finboy_billing` with `OPENAI_API_KEY` blank; the
  billing and WhatsApp Premium tests alone: 78 passed. The migration also went down and up.
- Playwright against the API double at 1440, 390 and 320 px: `billing.spec.ts` (gates, PayU form,
  paid / pending / failed returns, trial and grace notices, AutoPay off, Hindi and Malayalam links,
  an expired link, Reports' statement button, legal pages) and the theme contrast and blur budgets
  for the new pages and the upgrade sheet. The whole suite: 355 passed, 119 skipped (live-API
  only), 0 failed; after the last change, the billing, reports, statement and theme suites again:
  191 passed, 1 skipped.

**Not verified yet:**
- AutoPay end to end (mandate registration, pre-debit, `si_transaction`, revocation): needs PayU to
  enable Subscriptions; covered by unit and database tests against a mocked PayU.
- PayU's webhooks and mandate notices reaching the API (PayU can't reach loopback): covered by
  tests; confirm in PayU's webhook log after deploy.
- Live keys, a real payment, PayU's website verification, and PayU's own receipt email or SMS.
- WhatsApp Premium replies and nudges on Meta: covered by database tests only; no message was sent.
