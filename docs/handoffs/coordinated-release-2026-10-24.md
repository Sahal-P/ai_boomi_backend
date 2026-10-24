# Coordinated release — 24 October 2026

The human requested commit, push, merge and deployment of the current project,
and explicitly authorized coordination with the active AI-assistant chat. That
owner froze and committed the complete shared checkout at `bc9aadc`. The release
branch merges that handoff with `fd576c9`, which synchronizes review shortcuts in
a layout effect so a newly painted queue position cannot retain the previous
position's keyboard listener. The prior frontend CI failure exercised this race.

The older design branch's three refinements were already selectively integrated
in `5d85595`. Its stale product files must not replace the newer application.
Original design and earlier owner worktrees remain untouched.

## Verified combined application source

- `pnpm check`: Ruff/format, ESLint and strict TypeScript pass; 732 backend unit
  tests and 39 web client tests pass.
- `NEXT_PUBLIC_API_URL=/ pnpm build`: passes.
- `E2E_PORT=3040 pnpm test:e2e`: 131 pass, 46 intentional viewport/opt-in-live
  skips. Covers all daily screens, sessions, decisions, exact evidence, assistant
  provider failure, offline recovery, cancellation and phone layouts. The keyboard
  journey also passed five consecutive focused runs.
- Additive migration through `0007_whatsapp_capture`, `pnpm db:check` (no drift)
  and `pnpm test:integration` (55 pass) use a private temporary PostgreSQL container
  on loopback 5544, database `finboy_capture`. The original shared container stays
  running. No production tests or fixtures are used.
- The owner separately verified live OpenAI inference and actual local browser
  purchase clarification at 1440/390/320 widths, plus English, Hindi, Malayalam,
  Hinglish and Manglish. See [the owner handoff](../capture-round/handoff.md).

## Publication and production operations

Both existing GitHub repositories receive the release and capture branches and
identical main history. Hosted CI checks the reviewed pull request before release.
Production application source and domain deployment identity are checked afterward.

Before backend promotion: validate a private backup, require zero active imports,
stop only FinBoy, apply additive 0007 and check drift/record-count preservation.
Retain the scoped previous release and backup; never downgrade the schema or use
pre-scope API code. Transfer only the newly supplied OpenAI key from the private
operator secrets file. Preserve the existing assistant model, all other settings,
household session keys, Gmail grants, provider credentials, DNS and other services.

Production STT remains OpenAI. No Groq key or vision model has passed live capability
acceptance, and WhatsApp remains disabled. Deployed capability is not activation or
human acceptance. Frontend config contains only the existing API origin/proxy values.

Final production checks are read-only health/access/schema checks and the authenticated
browser's synthetic purchase-planning question. The release verification must record
the actual backend source, Vercel main SHA, preserved service/data state and live
assistant result separately from the local/hosted tests above.
