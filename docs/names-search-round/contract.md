# Names and search round — contract (21 November 2026)

This round makes Ask look up public prices and loan rates on the web, shows admins who each
household is, and asks every self-serve household for its name. It supersedes earlier statements
only where it says so:
- "A household has no personal name" and "we don't keep your name"
  ([sign-up round](../signup-round/contract.md)): a self-serve household now gives its name on the
  web.
- "Admins see activity, never … phone numbers, names … or contact details"
  ([admin round](../admin-round/contract.md)): admins now see each household's name, phone number
  and email, and the contact it typed for PayU receipts.
- "Interest rate: one the person gave" and "never estimate or invent prices, interest rates or
  returns" ([advisor round](../advisor-round/contract.md)): the advisor may quote public prices and
  typical rates from a web search, and work out an EMI with a rate the search found.

Everything else in earlier contracts still binds. Admins still never see a household's records,
amounts, payees, categories, messages, chats, memories, hashes or keys.

## Human decisions (21 November 2026)

- **Ask:** answer the way ChatGPT does, with web search for public prices and rates, instead of
  asking the person for them.
- **Admin:** show "who they are": name, full phone number, full Google email, payment contact,
  plan, sign-in, language, WhatsApp settings and activity. No money records, chats or memories.
- **Name:** required, and nothing else, asked on the web only: after the first sign-in, and once
  for existing households without one. WhatsApp-only households are asked when they first open
  the web app.
- **Where:** branch `feat/finboy-names-web-search` from release `f7f422f`; loopback API 8111 and
  web 3111 (Playwright 3112); disposable database `finboy_signup`; migration `0019_names`.

## Web search (`ADVISOR_WEB_SEARCH_ENABLED`, off by default)

- **One more read-only tool.** `search_web` joins the advisor's tool loop. It is offered only when
  `ADVISOR_ENABLED` and the flag are on and an OpenAI key and advisor model are set (the admin
  System page shows "Web search").
- **Only the question leaves FinBoy.** The backend asks OpenAI's Responses API web search one
  question: country India, low search context, at most two searches, no retries, `store=false`,
  the advisor's timeout. A question with an amount (₹, rupees, lakh, %) is refused, so the
  household's own figures never go into a search. The search always runs on OpenAI, whichever
  provider writes the answer.
- **Grounded like every other tool.** The tool returns a short summary, with links removed, and up
  to four cited https pages as `web-1`, `web-2` and so on. The summary's numbers join the figures a
  reply may quote, so the figure check still applies. `plan_numbers` accepts a rate the search
  found and a down payment, which code subtracts.
- **Replies** say web figures are approximate and vary by city, lender and date; never name or
  rank a lender or loan product; and cite page ids. The web shows "From the web" with the links;
  WhatsApp adds "🔎 From the web: …". FinBoy asks only for a detail that changes the answer, such
  as a down payment.
- **Nothing new is stored or logged.** The question, summary and pages live only for the answer;
  the chat keeps the answer text as before. When the search fails, the advisor answers without it.

## Names

- `users.display_name` is nullable (`0019_names`), and the self-serve placeholder "Household" is
  now NULL. The owner keeps their first name and pilots their "Pilot household N" label.
- `POST /api/v1/account/name {name}` saves 1–60 printable characters with at least one letter,
  spaces tidied; anything else is `invalid_name`. The name is never logged.
- The session's household carries `name`. The web shows a one-field step, "What should we call
  you?", before the app while a self-serve household's name is null, and the account menu shows
  the name. An older API that leaves `name` out asks nothing.
- Erasing a household clears its name.

## Admin

- **Households list:** name, phone number, kind, plan and dates. Search takes part of a name, a
  complete phone number (matched by its keyed hash, as before) or the start of an ID.
- **Household detail:** name, phone number (a `tel:` link), email, payment email and phone, and
  the ID; everything else as before. Confirmations name the household; erasing still means typing
  the short ID.
- **Phone numbers** are decrypted only for the households on the page shown: the encrypted copy a
  self-serve household keeps, or the private allowlist for the owner and pilots.
- **Google email:** a Fernet copy (`user_identities.encrypted_email`) is written at each Google
  sign-in or link. Households that joined earlier show the masked email until they next sign in
  with Google.
- **Payments and the audit log** name the household, falling back to the short ID.

## Privacy notice

The privacy policy says FinBoy keeps the name you give and an encrypted copy of your Google email,
that the team can see your name, phone number and email, and that OpenAI's web search looks up
public prices and loan rates with a question that never includes your records. It goes live with
the web release, before the flag is turned on.

## Release

Backend first (`0019_names` is additive and reversible), then the web. Web search waits for a live
capability check with the production advisor model, a live `pnpm eval:advisor` (two web cases
included) and the human's approval; then `ADVISOR_WEB_SEARCH_ENABLED=true` and a restart. Rollback
is the flag set to false. [docs/production.md](../production.md#names-and-web-search-release) has
the steps.

## Verification (21 November 2026)

- **Checks:**
  - `pnpm check` passes: 1,666 API unit tests, 136 web unit tests, 20 SEO tests, lint, format and
    types. `pnpm build` passes.
  - On `finboy_signup`, `0019_names` upgrades with no drift and downgrades and upgrades again.
  - `pnpm test:integration` passes: 123 tests, with the OpenAI key blanked.
- **Playwright** at desktop, 390 px and 320 px: 540 passed and 129 skipped. The only failures are
  `landing.spec.ts:83`, the stale "Typing is free" test that also fails on the live code. After
  the audit test was updated for names, the changed specs passed again (101).
- **Live web search with `gpt-6-luna`:**
  - "GT 650 on-road price in Kochi" returned ₹4,56,000 to ₹4,93,000 (autocarindia.com) in 4.9 s.
  - A price and loan rates asked together took 8.2 s.
  - A shared unit ("₹4.56–4.93 lakh") failed the figure check, so the search now writes every
    amount in full.
- **End to end on the local API:** "can i afford gt 650 bike ?", then "i am considering emi it
  for 3 years". In 3 runs of 3, both were answered with searched prices and rates, EMIs from
  `plan_numbers` and cited pages, in 10–17 s each. Before two prompt fixes, a run sometimes asked
  for the city or down payment instead:
  - search India-wide and answer first;
  - a zero down payment means none.
- **Live eval:** `pnpm eval:advisor` with web search on (`gpt-6-luna`, 44 cases × 3 runs) passed.
  - Figures, policy, refusals, memory and sources were all 100%; script was 97.7% (gate 95%).
  - There were 0 fallbacks; latency was p50 2.9 s and p95 6.9 s.
  - The two web cases passed every run. The two misses were Manglish script slips in non-web cases.
  - Coach nudges passed at 100%.
- **Browser** at desktop and 375 px:
  - the admin list, detail, Payments and Audit log show names, phone numbers and emails;
  - search works by name, exact number and ID;
  - the name step blocks the app until a valid name is saved, then the menu shows it;
  - Ask shows "Sources" with web links.
- **Not verified here:**
  - a real Google sign-in storing the email (the integration test uses a fake verifier);
  - the WhatsApp "From the web" line on a phone;
  - the production release.
