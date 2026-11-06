# Liquid Glass round — handoff (6 Nov 2026)

Branch `feat/finboy-liquid-glass` from main `47f37fc` (`frontend/main` = `backend/main`; the local
`main` was stale at `9fe4274`), in the worktree `.claude/worktrees/liquid-glass`. Loopback: web
3091, the test-only contract double 8091 (HTTPS, temporary private certificate), Playwright
3092. No database, API, migration or dependency change; nothing committed, pushed or deployed.
Decisions and scope: [contract](../liquid-glass-round/contract.md); how it is drawn:
[design system](../design-system.md), *Materials* and *How Liquid Glass is drawn*.

## What changed

- **Engine** (`lib/liquid-glass/`): `sdf.ts` (rounded-box distance and normal, convex-squircle
  bezel), `maps.ts` (Snell refraction into an inward displacement map, lens magnification),
  `tier.ts` (refract / frost / solid and the jank percentile), `look.ts` (the pre-paint
  Clear · Tinted script).
- **Components** (`components/liquid-glass/`): `useLiquidGlass` (per-element SVG filter,
  materialize), `GlassProvider` (tier, accessibility queries, jank guard, press glow),
  `glass-store` (tier and look), `useSelectionLens` (the drag lens), `ScrollEdge`,
  `mergeRefs`.
- **Materials** (`app/liquid-glass.css`, imported by `globals.css`): `lg`, `lg-menu`,
  `lg-thick` (+ `lg-sidebar`), `lg-static`, `lg-on-color`, `lg-prominent`, `lg-platter`,
  `lg-knob`, `lg-lens`, `scroll-edge`, the overlay-open recede rule and every fallback;
  `--ease-spring` in `@theme`; `.composer` and `.surface` rims.
- **Screens**: app navigation and account menu (with **Glass**: Clear · Tinted), buttons,
  menus, selects, dialogs, alert dialogs, sheets and every custom Radix dialog, Ask's composer,
  the Transactions segmented control, the back button, the landing nav, hero, final call to
  action and voice demo, and sign-in.
- **Tests**: 15 unit tests (`lib/liquid-glass/*.test.ts`); `theme.spec.ts` (scroll-edge
  backdrop model, refraction, `?glass=frost`, Tinted, stronger Reduce Transparency / Increase
  Contrast / forced-colours checks); `layout.spec.ts` (glass and platter label contrast, the
  drag lens, the remembered Glass choice); `perf.spec.ts` (`E2E_GLASS`).

## Findings while building

- **Chromium measures backdrop SVG filters in CSS pixels** at DPR 1, 2 and 3: a probe with a
  known map shifted the backdrop exactly 10 CSS px at each, and the map covered the element.
  No per-DPR scaling is needed.
- **Glass with a backdrop filter is its children's backdrop root.** The drag lens inside the
  tab pill only saw the pill's own layer and ghosted the labels; as a sibling it magnifies the
  rendered bar cleanly.
- **The old contrast model never reached its worst cases**: every walk stopped at `<body>`'s
  opaque fill, so "ink under floating chrome" and the field's darkest point were not applied.
  Text under `[data-scroll-edge]` bars is now measured honestly (ink under the edge's cover,
  then the glass); other routes keep the previous model, so nothing unrelated was re-judged.
- **React Compiler lint** treats an object whose member is passed as `ref` as a ref: destructure
  hook results (`const { attach, filter } = useLiquidGlass()`).
- `motion`'s `useSpring` follower did not move after `jump`; the lens retargets `animate()` on
  its own motion value instead.

## Verification (commands and outcomes)

- `pnpm install --frozen-lockfile` and `pnpm env:setup` in the fresh worktree, then
  `pnpm check` → exit 0: Ruff clean, 1419 API unit tests passed (110 integration deselected), 100
  web unit tests passed (15 new Liquid Glass tests), 13 more passed, typecheck clean.
- **Baseline on 47f37fc** (before any change, same machine): `E2E_CAPTURE_DIR=…/baseline-captures`
  → 69 passed, 75 screenshots; `E2E_PERF=1` (230 records, CPU 4×) → desktop p95 16.7 ms, phone-390
  p95 16.7 ms, phone-320 p95 16.8 ms; max 16.8 ms.
- **First full suite** `E2E_PORT=3092 pnpm test:e2e` → 478 passed, 2 failed, 123 skipped (the
  opt-in capture, perf and live specs and single-width checks). Both failures were the admin
  panel's erase confirmation at 390 and 320 px: four blurred layers (the admin's own frosted
  header and tab bar, the household sheet and the alert). The rule that makes floating chrome
  solid while an overlay is open now matches open dialogs, alert dialogs, menus and listboxes by
  role and includes `.glass` chrome, so custom Radix dialogs and the admin panel count too.
- **Second full suite** on a fresh build → **480 passed, 0 failed**, 123 skipped (5.6 min). This
  is also `pnpm build`'s check: the suite builds the app with `next build` first. `pnpm lint:web`,
  `pnpm typecheck` and the 15 engine tests passed again after the last edits.
- **Scroll performance** on that build (`E2E_PERF=1`, 230 records, CPU 4×, p95 / max in ms):

  | Tier | desktop | phone-390 | phone-320 |
  | --- | --- | --- | --- |
  | Baseline 47f37fc | 16.7 / 16.8 | 16.7 / 16.8 | 16.8 / 16.8 |
  | Default (refract, guard on) | 16.8 / 16.8 | 16.7 / 16.8 | 16.7 / 16.8 |
  | `E2E_GLASS=refract` (guard off) | 16.7 / 16.8 | 16.8 / 33.3 | 16.8 / 16.8 |
  | `E2E_GLASS=frost` | 16.7 / 16.8 | 16.8 / 16.8 | 16.8 / 16.8 |

  Within noise of the baseline; one dropped frame in 239 with refraction pinned at 390 px.
  CPU throttling does not model the GPU, which is where refraction costs.
- **Visual review**: `E2E_CAPTURE_DIR` after-set (69 passed, 75 screenshots) against the
  baseline set, plus a sheet with the two reference images and before/after pairs for
  Transactions, Home, Ask, the record sheet, desktop Home, the landing page and sign-in.
- **Browser pass** (dev preview against the contract double): at 375 px, the tab pill and
  account button refract (displacement scales ≈ 16 and 13 px); content bends at the pill's rim.
  The drag lens follows the finger, magnifies the tab under it and opens it on release. Quick add
  is an inset sheet, with chrome receding to one blurred layer. The account menu is glass. Ask's
  composer refracts the field's glow. At 1440 px the sidebar is inset glass, and Clear · Tinted
  applies live and persists. The landing nav is clear glass on the hero and turns into
  refracting glass after it, with the top scroll edge on. Sign-in panels are clear glass on
  yellow. At 320 px with `?glass=frost` it blurs without `url()` and nothing scrolls sideways.
  Reduce Transparency, Increase Contrast and forced colours were checked by Playwright
  emulation only (the browser pane cannot emulate them).

## Not verified — do not claim

- **Safari (WebKit) and Firefox**, which get the `frost` tier by design. The iPhone 17
  simulator (iOS 26.3) was booted, but the app has not been granted access to it (as in the
  glass-theme round), so nothing was rendered in WebKit; it was shut down again. Grant access in
  the simulator panel, or open the preview on an iPhone, to check it.
- **A real budget Android phone's GPU.** CPU throttling does not model GPU cost; the jank guard
  and the low-memory rule are the safety net. Check scrolling Transactions on a mid-range phone.
- **Comprehension with real people** (the 5-second script in the glass-theme handoff still
  applies, now with the platter instead of the black capsule).
