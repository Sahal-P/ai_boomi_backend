# FinBoy web

## Live site and demo

- [Open FinBoy](https://finboy.antlegs.in)
- [Watch the product demo (MP4, 68 seconds)](https://github.com/Sahal-P/ai_boomi_frontend/releases/download/demo-2026-10-24/finboy-demo.mp4)

[![Watch the FinBoy product demo](../../docs/media/finboy-demo-preview.jpg)](https://github.com/Sahal-P/ai_boomi_frontend/releases/download/demo-2026-10-24/finboy-demo.mp4)

Next.js App Router, strict TypeScript, Tailwind CSS 4, shadcn/ui, and Lucide.

Use the root [README](../../README.md) for complete workspace setup, environment,
development, and verification commands. Run all commands from the repository root.

```sh
pnpm dev:web
pnpm lint:web
pnpm test:web      # node --test over src/lib/**/*.test.ts (contract fixtures, outcomes, auth)
pnpm typecheck
pnpm build
pnpm test:e2e      # Playwright journeys at 1440×1000, 390×844, 320×740 (see e2e/README.md)
```

- `src/lib/api/` owns backend communication and zod runtime validation, one module per
  domain (`money`, `transactions`, `imports`, `mail`, `privacy`, `demo`, `assistant`, `auth`,
  `health`) with the shared `http.ts` helper that classifies failures and keeps only fixed
  error codes and request IDs.
- `src/hooks/` owns request lifetimes and state (`use-resource` for independent panels,
  `use-import-run` polling with backoff, `use-voice-recorder`, `use-speech`, …).
- `src/components/` is presentational; screens live under `records/`, `money/`,
  `sources/`, `assistant/`, `privacy/`, `demo/`, with shell pieces in `app-shell/`.
- The UI follows API contract v1.1.2 in `docs/ux-round/api-contract.md`; the product
  behaviour and state matrix are in `docs/ux-round/ui-spec.md`.

Production builds use `NEXT_PUBLIC_API_URL=/` and `FINBOY_API_ORIGIN=https://…` so the
browser talks to the same origin and Next rewrites `/api/v1` to the API. `FINBOY_API_ORIGIN`
must be an HTTPS origin. To exercise that shape locally, serve the API over HTTPS on loopback
with a temporary private certificate and trust it only in Next's Node process with
`NODE_EXTRA_CA_CERTS` (commands in `e2e/README.md`); never add it to a system trust store.
