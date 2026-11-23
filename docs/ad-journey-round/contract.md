# Ad journey round — contract (23 November 2026)

**The problem.** The first Instagram ad (a Malayalam reel shown in Kerala) got:
- 363 link clicks and 283 website loads;
- 15 WhatsApp sign-ups, of which 6 made a first record.

FinBoy couldn't tell which households came from it. finboy.io also opened in English, and its
button sent "Hi FinBoy", so the welcome came in English too.

**What this round adds:**
- tracking from an ad to a household's first record;
- a Malayalam ad page;
- a first entry that's easier to make.

**What it supersedes, and nothing else:**
- **The site's only greeting.** The prefilled greeting "Hi FinBoy" was the only one. A page's greeting now ends with ` (ref XXXXXX)`, and the Malayalam page types `നമസ്കാരം FinBoy`.
- **"PostgreSQL keeps nothing about visitors."** A visit to a page with the WhatsApp button is now a small anonymous row (below).
- **The welcome.** The welcome and the language-chosen reply now lead with one task, "try *chai 20*". The month and budget hints move to a one-time line after the first saved entry.

**What still binds:**
- Logs never carry a ref, a User-Agent or a query string.
- Admins see counts and times, never money.
- Every other privacy promise holds.

## Human decisions (23 November 2026)

- **Landing:** the next ad opens a light Malayalam page, `/ml`.
- **Ref:** a short random ref goes at the end of the prefilled WhatsApp greeting, so a sign-up can be matched to its visit.
- **Nudge:** three households that agreed but never added an entry got a one-off "try *ചായ 20*" text, inside their 24-hour windows. It was sent at 10:51 IST, before this build.

## A visit

The table is `signup_visits` (migration `0023_signup_visits`).

| Field | Rule |
| --- | --- |
| `ref` | 6 characters from the login-code alphabet (no 0/O/1/I). Made by the page and unique. |
| `source`, `medium`, `campaign`, `content` | The link's `utm_*` values: lowercased, at most 64 of `a-z 0-9 . _ -`, otherwise dropped. A page that saw an `fbclid` but no `utm_source` records `meta` / `click`. The click ID itself is never sent. |
| `landing`, `language` | The page path (`/`, `/ml`) and its language (`en`, `hi`, `ml`). |
| `browser`, `platform` | Classes the server reads from the User-Agent: `instagram`, `facebook` or `other`, and `android`, `ios`, `desktop` or `other`. The User-Agent is never stored or logged. |
| `created_at`, `tapped_at`, `joined_at` | When the page opened, when the WhatsApp button was tapped (or a sign-in started), and when a new household's first message arrived with this ref. |
| `user_id` | The household the visit led to. NULL until claimed. Set back to NULL when that household is erased; `ON DELETE SET NULL` covers sign-ups that never agreed. |

**What a visit never keeps:** an IP address, a cookie, a device ID, a raw User-Agent or a click ID.

**Retention:** a visit that leads to no sign-up is deleted after 90 days, by `households.tidy`.

**The browser** keeps the ref in `sessionStorage`, for that tab only.

## The flow

1. **Recording.** A page with the button posts `POST /api/v1/visits` after hydration.
   - It never waits on the answer.
   - The route is public and needs the web Origin.
   - It is throttled to 30 a minute per address and 1,200 a minute in all.
   - It returns 204, and a seen ref does nothing.
2. **The link.** The button's `wa.me` link types the page's greeting plus ` (ref XXXXXX)`. On a computer, the chat QR carries the same link.
3. **The tap.** A tap fires `POST /api/v1/visits/tap` with `keepalive`. `/auth/whatsapp/start` and Google sign-up take the same optional `ref`. A login code's message carries it percent-encoded.
4. **Arrival.** The webhook parser (`events.py`) splits off a trailing ` (ref XXXXXX)` before anything reads the text: greetings, commands, login codes, the diary and the message log.
   - A ref inside a sentence stays text.
   - A message that is only the ref reads as "hi".
5. **Claiming.** `receipts._self_serve` claims the visit only when it creates a new household. A number that is already a household claims nothing.

## The Malayalam page `/ml`

**The first screen** has:
- the reel's line "കണക്കുപുസ്തകം, ഇനി WhatsApp-ൽ.";
- "ചായ 20, ഓട്ടോ 50" and the voice-note line;
- the button "WhatsApp-ൽ തുടങ്ങാം";
- the three assurances;
- the price and terms lines with the home hero's facts. Continuing agrees to the terms, as on the home page.

**Below it** are three steps and a sample saved card, with a link to the English and Hindi home page.

**What it leaves out:** no 3D scene, Lenis, GSAP or glass script, so it opens fast in Instagram's in-app browser.

**The button:**
- It renders a `wa.me` link from the first paint with `FINBOY_WHATSAPP_NUMBER`, FinBoy's public business number. "FinBoy fast deploy" (`.github/workflows/ux-web.yml`) passes it to `pnpm build` from the frontend repository's Actions variable of the same name. It is not a secret.
- The session check then sends signed-in households to their dashboard.
- While sign-ups are closed, it sends everyone to `/login`.
- If the check can't reach FinBoy, the chat link stays.
- Without the variable, the page works as the home page does.

**SEO:** `/` and `/ml` name each other with `hreflang`, and `/ml` is in the sitemap.

## The first entry

- **The greeting.** "നമസ്കാരം FinBoy" (and "നമസ്കാരം ഫിൻബോയ്", "namaskaram finboy") is a greeting. Malayalam script reads as `ml`, so the welcome comes in Malayalam.
- **The welcome** in each language starts with one task, "👉 try *ചായ 20* / *chai 20* / *चाय 20*", then voice and photos. The language-chosen reply ends with the same example.
- **The first saved card.** A household's first saved card, with no records before it, gets one line: "🎉 Your first entry is saved!" plus the "this month" and budget hints. It shows once. A later card (an amount change, an undo and a new entry) or a household with earlier records gets none.
- **`pnpm eval:diary`** gains "ചായ 20", "ചായ ഇരുപത്" and "चाय 20". The offline reader needs a verb, so the integration test uses "ചായയ്ക്ക് 20 കൊടുത്തു".

## Admin

- **Sign-ups** gains "Where sign-ups came from" for 7, 30 or 90 days (`GET /admin/signups?days=`).
  - Each row is a source, medium and campaign, with counts for opened, tapped WhatsApp, signed up, agreed and first record.
  - Each row also has median minutes from open to tap, tap to first message, and first message to first record.
  - A "No visit" row covers sign-ups that came in directly.
  - A greeting that arrived means a tap, even if the tap's ping was lost.
- **A self-serve household's detail** shows "Came from": its tags, page, browser and phone class, and the times it opened, tapped, first wrote, agreed, linked WhatsApp and made its first record.
- **First record** is the earliest still-confirmed household record.
- **Day filters** arrive as text, so `days` and the households list's `active` are read as
  numbers. An integer `Literal` refused "30", and the "Active in" filter answered 422 before this
  round.

## Tagging links

| Where | Link |
| --- | --- |
| Our ads | `https://finboy.io/ml?utm_source=instagram&utm_medium=paid_social&utm_campaign=<yyyy-mm>-<name>&utm_content=<creative>` |
| Instagram bio | Instagram adds `utm_source=ig&utm_medium=social&utm_content=link_in_bio` by itself; these read as "ig · social". |
| An untagged Meta click | `meta · click` |

## Checks

- **API unit:** tags, classes, ref splitting, login links, funnel medians, both routes (origin, throttles, body limits, refusals, no ref or User-Agent in logs), greetings, the welcome copy and the first-record line.
- **Integration:** a Malayalam visit through to the first record; a login code carrying its ref; the 90-day tidy; erasure unlinking the visit.
- **Web:** UTM reading (Instagram's real bio-link tags), refs, greetings, the chat link, the first-paint number, the login link, admin schemas and labels.
