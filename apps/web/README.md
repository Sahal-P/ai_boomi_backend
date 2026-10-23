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

`src/lib/api/` owns backend communication and zod response validation
(one module per domain, shared `http.ts` helper);
`src/hooks/use-health.ts` owns connection state (shown in the app sidebar).

The 3D marketing site (`/`), the glass app shell (`src/app/(app)/layout.tsx`) and the
design system — tokens, primitives, motion and the WebGL scene kit — are described in
[docs/design-system.md](../../docs/design-system.md) and browsable at `/styleguide` in
dev. Append `?quality=high|medium|low` to pin the 3D quality tier while testing.
The sculpted models in `public/models/` are generated and committed; rebuild them with
`pnpm --filter @finboy/web assets:3d` (needs Blender 5, see `scripts/3d/`).

Phase 1 app routes are placeholders under `src/app/(app)/`. Domain owners implement
their features against [the shared contract](../../docs/phase1/contract.md), using the
design system for every screen.
