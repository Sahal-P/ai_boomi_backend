# FinBoy web

Next.js App Router, strict TypeScript, Tailwind CSS 4, shadcn/ui, and Lucide.

Use the root [README](../../README.md) for complete workspace setup, environment,
development, and verification commands. Run all commands from the repository root.

```sh
pnpm dev:web
pnpm lint:web
pnpm test:web
pnpm typecheck
pnpm build
```

`src/lib/api.ts` owns backend communication and response validation;
`src/hooks/use-health.ts` owns connection state. The landing page contains no
financial data or product features beyond a live backend connection check.
