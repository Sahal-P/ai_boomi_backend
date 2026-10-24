# Capture and real-AI assistant handoff — 24 October 2026

Branch `feat/finboy-voice-capture`, baseline `5d85595`. This handoff includes the
existing Groq/WhatsApp screenshot round and the human's subsequent request to use
real AI after a GT 650 purchase question returned a canned period menu.

## Assistant behavior and privacy

With backend `OPENAI_API_KEY` and `OPENAI_ASSISTANT_MODEL` configured, every question
uses OpenAI Structured Outputs with `store=false`. The verified model is `gpt-6-luna`.
The old rules-first short circuit no longer bypasses AI for recognized questions.
Generated context and native-language speech cannot contain digits, currency symbols
or percentages. Model prompts also prohibit numeric claims written as words, invented
prices/rates, unsupported affordability claims, tools, SQL and record writes.

Financial responses append complete code-rendered engine figures, dates, coverage
warnings and disclaimers verbatim. Ledger rows/engine amounts are never sent for model
wording. Closed slots, literal amounts/merchants, deterministic record periods and
the explicit security-pick decline remain enforced. Configured provider errors,
refusals and malformed/missing output return redacted `assistant_unavailable`, not
an apparently successful canned answer. Missing production configuration returns
`configuration_missing`. Unconfigured development/test runs retain offline rules.

Consumer purchases use `purchase_planning`/`clarify`, asking for the actual quote,
savings/down payment and cash/financing plan. A future purchase horizon does not
select a ledger period, and a product model number never becomes a commitment.
There is no engine call for purchase planning, no live product-price lookup, no
one-off/future purchase calculation and no persistent conversation memory. Requests
are independent; the current question needs the context required to answer it.

The supplied key was saved only in `~/.config/finboy/secrets.env` and ignored
`apps/api/.env`, with mode 600. No key is in source, documentation, frontend settings
or browser requests. The release owner must transfer the new key privately to the
backend production environment without printing it or changing other credentials.

## Actual verification

- `pnpm check`: passed 732 backend unit tests, 39 web tests, Ruff, ESLint and strict
  TypeScript. Tests use fake providers, without external provider calls.
- `NEXT_PUBLIC_API_URL=/ pnpm build`: passed the production-shaped build.
- `pnpm db:migrate` and `pnpm db:check`: passed against loopback 5433, disposable
  `finboy_capture`, at `0007_whatsapp_capture`; no schema drift.
- `pnpm test:integration`: all 55 passed on that disposable database with provider
  credentials explicitly disabled. No production tests or destructive migration.
  The privacy test now scopes its source assertion to its household and checks that
  other synthetic households' source counts stay unchanged.
- Targeted Playwright assistant/offline journeys: 15 passed at desktop, 390px and
  320px widths, using the test-only API double. They cover answer retention after
  failure, cancellation, audio failure, denied microphone and offline recovery.
- Additional browser checks simulated degraded health, assistant 503 and device
  offline states and found no horizontal overflow at those three widths.
- Actual new-key OpenAI Structured Outputs request succeeded. Actual local HTTP
  purchase-planning requests returned 200 for en/hi/ml/hinglish/manglish, with no
  proposed amount or financial facts. This is provider inference, not a mocked reply.
- Actual Chrome page submission of the reported GT 650/next-month question reached
  the local API and OpenAI, showed a contextual purchase clarification, preserved the
  loading state and rendered without overflow at 1440/390/320px. Screenshots are in
  the current chat's local `ai-assistant` visualization folder, outside Git.
- `git diff --check` and a tracked/unignored-file scan for the supplied key and
  project-key patterns passed. This targeted scan is not a full-history secret audit.

## Capture acceptance and release boundaries

The capture contract is in `contract.md`. Synthetic provider/media tests cover bounded
images, grounding, review-only ingestion, duplicate webhook admission, reconciliation
and deletion. Capture replies use neutral counterparty wording for sent or received
payments. Mixed email/screenshot evidence says source notifications.

No Groq key is configured, so no live Groq request or benchmark was run. Keep
`SPEECH_TRANSCRIBE_PROVIDER=openai` in production. `OPENAI_VISION_MODEL` still needs a
live synthetic image-input capability check before screenshot capture is enabled.
No real WhatsApp screenshot delivery, review or human receipt was established here.
WhatsApp stays disabled in production.

The human explicitly authorized coordination with “Fix deployed connect page”, which
owns final integration, main publication, migrations and deployment. That chat will
combine this commit with its separately reviewed keyboard-shortcut fix. This chat
does not merge main or deploy. Preserve household access, existing applications and
provider/session/Gmail configuration. A private backup precedes production's additive
0007 migration. Deployment and live production acceptance must be recorded separately.
