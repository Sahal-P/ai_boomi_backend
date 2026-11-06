# FinBoy engineering guide

## Scope and architecture

- Phase 1 includes the authorized completion round in
  `docs/phase1/parallel-completion.md`, which supersedes conflicting scope,
  ownership, language, provider, and runtime sections of the original contract.
  All other boundaries in `docs/phase1/contract.md` remain binding.
- Keep one FastAPI application in `apps/api` and one Next.js App Router application
  in `apps/web`. PostgreSQL is the only persistent service.
- API routes own HTTP contracts, `services` own business logic, `db` owns SQLAlchemy
  sessions and metadata, and `core` owns settings, errors, and logging.
- Keep UI components presentational. Put backend communication and runtime response
  validation in `apps/web/src/lib/api/` (one module per domain, shared helper in
  `http.ts`) and connection state in a small hook.
- Prefer simple functions and explicit types. Avoid generic repositories, service
  containers, microservices, or shared packages until there is a real need.
- Use Alembic for schema changes; never call `metadata.create_all()` at startup.
  Import future model modules into Alembic's environment before autogeneration.

## Coding standards

- Use uv for Python and pnpm for JavaScript. Commit both lockfiles. Use stable
  releases and official documentation when changing dependencies.
- Python uses type annotations, Pydantic v2, Ruff, and SQLAlchemy 2-style APIs.
  Blocking database work belongs in synchronous routes/services, not async routes.
- TypeScript is strict. Avoid `any`, unchecked response casts, and disabling lint
  rules to hide problems. Use accessible HTML, Tailwind, shadcn/ui, and Lucide.
- Keep modules small, names descriptive, and comments focused on non-obvious intent.
  Add dependencies only when they solve a concrete problem.
- Do not delegate to subagents unless the user explicitly asks for delegation.

## Security and privacy

- Never commit `.env` files, real credentials, tokens, bank identifiers, or financial
  records. Examples must contain only clearly local development values.
- Every future OpenAI call runs on the backend. Never place an API key in a
  `NEXT_PUBLIC_*` variable, client component, browser bundle, or frontend request.
- Never log request/response bodies, query strings, authorization/cookie headers,
  database URLs, raw SQL parameters, exception messages, or financial information.
  Use structured, allowlisted operational fields and generated request IDs.
- Keep CORS origins explicit. Local services bind to loopback. Health responses and
  error envelopes must not reveal internal exception details or credentials.
- Parameterize database queries and validate external input. Future write services
  own their transaction boundaries; session dependencies do not auto-commit.

## Testing and delivery

- Run `pnpm check` and `pnpm build` before completing a code change.
- Add focused pytest/HTTPX coverage for behavior, failure modes, error redaction,
  and CORS when changing backend contracts. Unit tests must not require PostgreSQL.
- For database changes, run `pnpm db:migrate`, `pnpm db:check`, and
  `pnpm test:integration` against a local disposable database. Never use a production
  database for tests or run destructive migrations without explicit authorization.
- Verify frontend changes in a browser at desktop and mobile widths, including
  loading, connected, degraded, and offline behavior when relevant.
- Update setup/architecture documentation when commands, settings, or boundaries
  change. Report commands, actual outcomes, and any remaining verification limits.

## Parallel work

- Follow the ownership table, ports, and per-agent databases in
  `docs/phase1/parallel-completion.md` for this completion round.
- Never stop the shared PostgreSQL container (`db:down` or Compose down).
- Secrets live only in `~/.config/finboy/secrets.env` and gitignored env files.

## Completion-round handoff clarification

- Agent 5 owns final integration after each owner handoff. The human explicitly
  reassigned the absent Agent 2 frontend work to Agent 5; the original uncommitted
  design worktree must remain untouched, with only reviewed snapshot copies used.
- The human's final TTS choice is Resemble Ultra for English/Hindi, Gemini for
  Malayalam. This supersedes the initial Chatterbox requirement; no Replicate setup.
- Do not equate configured providers or Graph acceptance with completed live flows.
  Record actual browser playback, human-confirmed receipt, and unresolved criteria.

## Authorized production round

- On 24 October 2026 the human authorized pushing every branch to the two named
  GitHub repositories, merging main, Vercel frontend deployment and voxpay backend
  deployment, then selected private single-household access and antlegs.in DNS.
- Follow docs/production.md. Keep production access fail-closed; do not introduce
  public multi-user signup, expose unauthenticated finance routes, or copy credentials
  into Vercel/browser configuration. Preserve all other running host applications.

## UX remediation round — 24 October 2026

The human assigned Backend/Integration to Agent 1 and Product to Agent 2 from exact
baseline b572565aa521a753fbee1271ca0c68e470ff15c8. This round's additive contract and
scope changes supersede earlier frozen interfaces only as documented in
`docs/ux-round/api-contract.md`. Backend uses feat/finboy-ux-backend, loopback 8031/3031
and disposable finboy_ux_api. Product uses feat/finboy-ux-frontend, 8032/3032 and
finboy_ux_ui. Backend owns apps/api and backend/domain/operations docs; Product owns
apps/web, JavaScript tooling and UI/design docs until its explicit handoff. Final
assembly belongs to Agent 1 on feat/finboy-ux-integration. Do not create more agents,
edit other worktrees, invent local OAuth callbacks, or run production test suites.

## Capture round — 24 October 2026

From main 5d85595 the human chose Groq `whisper-large-v3-turbo` speech-to-text for
English/Hindi (OpenAI `gpt-transcribe` stays for Malayalam) and authorized WhatsApp UPI
screenshot capture into the review queue, read by OpenAI vision. Scope, provider and
contract changes in `docs/capture-round/contract.md` supersede earlier non-goals only as
documented there. One agent on feat/finboy-voice-capture, loopback 8041/3041, disposable
finboy_capture. WhatsApp stays disabled in production; WhatsApp never confirms, edits or
deletes records, and screenshots/transcripts are never stored.

## Authorized WhatsApp production activation — 24 October 2026

The human subsequently explicitly requested enabling WhatsApp in production. This
supersedes the earlier production-disabled statements only for the existing Meta
app and existing private sender allowlist. Preserve household access, consent/STOP
state, stable encryption/session keys and all other host applications. No public
signup, new recipient, business phone, app, billing setup or unsolicited send.
Production speech remains OpenAI; screenshot reading uses capability-verified
`gpt-6-luna` and every screenshot-only event still requires review. Record actual
Meta delivery/read status separately from human voice/screenshot acceptance.

## Village pilot round — 26 October 2026

From main b2110a9 the human approved a Hindi, WhatsApp voice-first village pilot on the
existing Meta test number: 4 village households plus the owner, at most 10 pilot households.
Pilot households may confirm, correct the amount of and reject their own records by button,
with undo; record money and dues by voice; and receive opt-in reminders. WhatsApp never
merges or deletes records, and erasure stays operator-run. `docs/pilot/contract.md`
supersedes earlier WhatsApp non-goals and the "no new recipient or unsolicited send" rule
only as documented there. One agent on feat/finboy-village-pilot, loopback 8051/3051,
disposable finboy_pilot. The owner's web app and WhatsApp question flow stay unchanged
unless the owner's pilot flag is set. Never store messages, audio, images or transcripts.

## Sign-up round — 27 October 2026

From main e06ba9b the human approved public self-serve sign-up: WhatsApp first (a login code
sent from the person's own WhatsApp and confirmed by a button tap, or sign-up inside WhatsApp
from a link or QR code), Google sign-in as the backup, at most `SIGNUP_LIMIT` (100) self-serve
households and then a WhatsApp waitlist. Each household gets its own private web app, quick
add by text or voice, and the WhatsApp voice diary in Hindi and English.
`docs/signup-round/contract.md` supersedes the "no public multi-user signup" and
single-household statements above only as documented there. Sign-up stays off
(`SIGNUP_ENABLED=false`) until the human enables it in production. One agent on
feat/finboy-signup, loopback 8061/3061, disposable finboy_signup. Pilot households stay
WhatsApp-only; WhatsApp never merges or deletes records; messages, audio, images, transcripts,
login codes and Google tokens are never stored.

## Malayalam voice round — 28 October 2026

From feat/finboy-signup 4f0a56f the human chose Sarvam AI: Saaras speech-to-text for English,
Hindi and Malayalam (`SPEECH_TRANSCRIBE_PROVIDER=sarvam`, only the live-verified `saaras:v3`),
Bulbul v3 for Malayalam spoken replies (`MALAYALAM_TTS_PROVIDER=sarvam`; English and Hindi stay
on Resemble), and Malayalam in quick add and the WhatsApp money diary.
`docs/malayalam-round/contract.md` supersedes the Hindi/English-only diary and the
Malayalam-always-OpenAI statements only as documented there. One agent on
feat/finboy-malayalam-voice, loopback 8061/3061, disposable finboy_signup. Code defaults stay
openai/gemini, so production is unchanged until the human releases it. Before any real
household's audio reaches Sarvam, the human turns off training and sets "No retention" in
Sarvam's dashboard. Audio, transcripts and Sarvam request IDs are never stored.

## Reply language and direct API round — 29 October 2026

From main 2fb2eb7 the human made two choices.
- **WhatsApp replies** start in English for everyone, village pilot households included. They then
  follow each person's own language, or the one they choose: `en`/`english`, `hindi`/`हिंदी`, or
  `ml`/`malayalam`/`മലയാളം`. A bare `hi` is a greeting.
- **The browser calls the API** at its own HTTPS origin with credentials, instead of through
  Vercel's proxy, which could not reach the server about 4 times in 10.

These supersede, only as documented in `docs/whatsapp.md` ("Reply language") and
`docs/production.md` ("Access and network"):
- the Phase 1 `credentials: "omit"` client rule;
- the same-origin proxy statements;
- the earlier first-message and Hindi-default language rules.

One agent on feat/finboy-language-and-access, loopback 8061/3061, disposable finboy_signup. CORS
stays exact-origin. Origin checks, `__Host-` host-only cookies and every no-storage rule are
unchanged.

## Money manager round — 29 October 2026

From main 1c724a4 the human chose a WhatsApp-first money manager: diary entries (text, several
items, voice, UPI screenshots, bill photos, pasted bank SMS) are saved at once with Undo, Amount
and Category, and FinBoy asks first only when unsure; categories learn per payee; budgets with
warnings, a savings goal, "today"/"this week"/"this month" replies and an opt-in monthly check-in
template. Email stays later and Gmail invite-only; languages stay English, Hindi and Malayalam;
the web keeps its design. `docs/money-manager-round/contract.md` supersedes "nothing counts until
a tap", "screenshot-only events require review" and "list replies are not used" for diary
households only as documented there. One agent on feat/finboy-money-manager, loopback 8061/3061,
disposable finboy_signup, migration `0011_money_manager`. The check-in timer is enabled only after
Meta approves its template. Messages, audio, images, transcripts and numbers in clear are never
stored; advice stays on budgeting and discipline, never specific investments.

## Fast decisions round — 30 October 2026

From main b89821d the human chose Liquid AI's d1-ultra decision model to make FinBoy answer faster.
It sorts each diary message, question and WhatsApp photo; when it is sure, FinBoy answers without
waiting for OpenAI: simple entries, check-ups in other words, greetings, common questions (engine
figures and templates, without the AI intro line) and photos that are not payments or bills.
Today's OpenAI call always starts at the same moment, so nothing waits longer.
`docs/triage-round/contract.md` supersedes "every question uses OpenAI" only as documented there.
One agent on feat/finboy-fast-decisions, loopback 8061/3061, disposable finboy_signup, no migration.
`TRIAGE_ENABLED` stays false until `pnpm eval:triage` passes for each enabled language, the human has
checked Liquid's data terms and approves the release. d1-ultra gets masked text and a small photo
preview, never ledger amounts; nothing it sees or answers is stored.

## UI refresh round — 31 October 2026

From main a09d1bd the human asked for a calmer web app: four tabs (Home, Transactions with an
All · To review tab, Reports, Ask), Sources and Privacy & data in the account menu, a + that
opens quick add from every screen, glass fields, expense reports (a spending donut, six months
of money in and out, budget meters) and a chat-style Ask like Gemini's in FinBoy's theme.
`docs/ui-refresh/contract.md` supersedes the earlier navigation, Overview and Ask layouts only as
documented there. One agent on feat/finboy-ui-refresh, loopback web 3061 with API 8061,
disposable finboy_signup; web only, no API or migration change. Charts follow the dataviz method
with validated tokens; contrast, blur and reduced-motion rules are unchanged.

## Statement round — 31 October 2026

From feat/finboy-ui-refresh 00904f2 the human asked to import transactions from a Google Pay
statement PDF, on the web and by sending it on WhatsApp, keeping every detail and losing nothing,
with four new report sections: Who you pay most, Regular payments, Money with people and Small
payments. `docs/statement-round/contract.md` supersedes "PDFs can't be read", WhatsApp ignoring
documents and single-month periods only as documented there. One agent on
feat/finboy-statement-import, loopback 8061/3061, disposable finboy_signup, migration
`0012_statement_imports`. `STATEMENT_IMPORT_ENABLED` stays false until `pnpm eval:gpay` passes and
the human approves the release. A statement saves nothing unless every row adds up to Google's own
totals; the PDF, its phone number and email are never stored or logged; WhatsApp never removes an
import or merges records. Never commit a real statement or use one as a fixture.

## Subscription round — 2 November 2026

From main 9fe4274 the human chose FinBoy Premium at ₹299 a month through PayU India: 30 days of
Premium from sign-up (households that signed up earlier get 30 days from launch), then a Free plan
that keeps typed entries, Home, Transactions, Reports, budgets and check-ups, while voice, Ask
FinBoy, photo and screenshot reading and statement import need Premium. The owner and the village
pilot households are always included. Each ₹299 PayU Hosted Checkout payment adds a month; UPI
AutoPay and card auto-renew turn on with `PAYU_AUTOPAY_ENABLED` once PayU enables Subscriptions.
`docs/subscription-round/contract.md` supersedes earlier statements only as documented there. One
agent on feat/finboy-subscriptions, loopback 8071/3071, disposable finboy_billing, migration
`0013_billing`. `BILLING_ENABLED` stays false until the human releases it with live keys. The PayU
salt stays on the backend; card numbers, UPI IDs and bank references are never stored or logged;
the payer's email and phone are kept only encrypted and erased with the account.

## Admin round — 5 November 2026

From main 1eadf04 the human asked for an admin panel at `/admin`, signed in with an admin email and
password and built from FinBoy's existing design, with full operator control: overview counts,
households (search by ID or exact phone number), Premium grants, AutoPay cancel, pay links,
sign-out, suspend and restore, erase, payments and PayU re-checks, sign-up tidying, system status,
admin accounts and an audit log. `docs/admin-round/contract.md` records it. Admins see activity,
never a household's money: no record amounts, payees, categories, messages, phone numbers, names,
hashes or keys; FinBoy's own ₹299 payments are the only money shown. Flags stay in
`/etc/finboy/production.env`; the panel only shows them. Admin accounts live in the
database and are created on the server with `python -m finboy.services.admin.cli`; no admin
password goes into an env file, Git or the browser. Admin sessions are server-side and never
reuse `WEB_SESSION_KEY`. One agent on feat/finboy-admin, loopback 8081/3081, disposable
finboy_admin, migration `0014_admin`.

## Liquid Glass round — 6 November 2026

From main 47f37fc the human asked for Apple's latest Liquid Glass "as exactly as possible" across
the signed-in app, the landing and public pages and sign-in: refracting glass for the navigation
layer (bars, the sidebar, menus, sheets, dialogs, Ask's composer), Apple's selection platter and
drag lens, a fixed tab bar, and a Clear · Tinted choice in the account menu.
`docs/liquid-glass-round/contract.md` supersedes the header capsule, black active capsule,
floating-glass and "never glass over yellow" statements only as documented there. One agent on
feat/finboy-liquid-glass, loopback web 3091 with the contract double on 8091 (Playwright 3092);
web only, no API, migration or dependency change. Refraction is a Chromium enhancement over a
frosted fallback (never send `url()` to other engines' backdrop filters); text ≥ 4.5:1, control
boundaries ≥ 3:1, ≤ 3 blurred layers in view, no frosted glass over yellow and every
accessibility fallback still hold. After "it doesn't feel like Liquid Glass", a second pass gave
the app a wallpaper with colour and shape (`bg-wallpaper`; the landing keeps its field), widget-glass
cards without backdrop filters, a floating desktop toolbar for page actions, a gliding sidebar
highlight and pointer light, as the contract's *Second pass* records.

## Advisor round — 7 November 2026

From main 42b1a53 the human asked for the best AI advisor with a personalised experience and
long-term memory like ChatGPT's, said privacy is not a blocker, chose a money coach (never a fund,
stock or other product pick) and made the advisor and memory free for every household. Ask reads
the household's records through read-only money-engine tools, every figure it writes is checked
against FinBoy's own numbers, and the keyword rules answer when the model fails. Chats with FinBoy
and saved memories are kept until the household deletes them (Memory page, WhatsApp commands,
erasure); the privacy policy says so. `docs/advisor-round/contract.md` supersedes "Ask stores
nothing", "never store messages/transcripts" (for advisor questions and answers only), "model
output never selects tools", "no generated figures", the Premium gate on Ask and the template
fast path for questions, only as documented there. One agent on feat/finboy-advisor, loopback
8101/3101, disposable finboy_advisor, migration `0015_advisor`. `ADVISOR_ENABLED` stays false
until `pnpm eval:advisor` passes live and the human approves the release. Audio, photos,
screenshots and diary messages are still never stored; admins never see chats or memories.
