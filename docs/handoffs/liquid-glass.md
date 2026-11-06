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

## Second pass — "it doesn't feel like Liquid Glass"

The first pass was committed as `d736e60`. Shown desktop Reports, the human said it did not feel
like Liquid Glass. The diagnosis: refraction was on (Chromium tier), but nothing had colour or
shape behind any glass.

- The sidebar bent a nearly flat grey field.
- Nothing scrolled under glass on desktop.
- The cards were opaque grey.

The glass Apple shows reads as glass for two reasons: the wallpaper behind it (macOS Tahoe's
Control Center modules are almost clear over wavy colour), and controls floating over content.
Prototyped with injected CSS and full-resolution Chrome screenshots, then built:

- **Wallpaper** (`bg-wallpaper`, `--wallpaper-*` in `globals.css`): sky and apricot bands and a
  sunflower sun. The sun sits further out on phones, so the account button stays clear glass.
  - The app, the admin console and its sign-in, the session checks, the demo and the 404 use it.
  - The landing and the legal pages keep the field, whose 3D mirror (`three/lib/field.ts`) would
    otherwise drift.
  - Its darkest point measures luminance 0.676, where the bands meet at 390 px. That is lighter
    than the field's warm glow (0.669), so the existing contrast reference covers it; the colours
    were lifted once to get that margin.
- **Widget-glass cards**: `.bg-wallpaper .surface` is white .5 (Tinted .72), with a light-drawn
  edge and a deep shadow. It has no backdrop filter, so the blur budget is unchanged.
- **Desktop toolbar**: `PageActions` floats a page's actions in a refracting `lg` capsule at the
  content column's top right, and the page scrolls beneath it.
  - The title, and the offline banner that shares its row, keep clear of it through the measured
    `--page-actions-width` on `main`.
  - A desktop top scroll edge fades out under the capsule's lower half.
  - The edge keeps cover .94: at .55 the period select's boundary fell to 2.9:1 in the contrast
    model.
  - Desktop `scroll-padding-top` is 6 rem, so focus clears the toolbar.
- **Sidebar**: white .26 with an 8 px frost (18 px in the `frost` tier), saturation 1.35. A
  bright `lg-hover` pill glides under the mouse.
- **Pointer light**: under a mouse, GlassProvider lights the card or sidebar beneath the pointer
  (`--lg-x/--lg-y`, registered `--lg-lit`, once per frame). It fades on scroll and is off for
  touch and reduced motion.
- **Fixed in passing** (both from the first pass):
  - under Reduce Transparency the scroll edges painted the gradient over a flat field; they are now
    flat too;
  - with the Tinted look saved, the Reduce Transparency, Increase Contrast and no-backdrop-filter
    tokens lost to Tinted's more specific `:root[data-glass-look="tinted"]`. Increase Contrast's
    glass then kept Tinted's .70 instead of .94. The fallbacks now also match
    `:root[data-glass-look]` (new theme test).
- **Tests** (`layout.spec.ts`, desktop):
  - the toolbar is glass, refracts, stays put while the page scrolls, keeps clear of the title at
    1024 px and still works;
  - the offline banner keeps clear of the toolbar;
  - the sidebar highlight appears on the hovered item and fades when the mouse leaves;
  - a card's `--lg-lit` follows the mouse.
- **Found while checking**: after a dev-server restart, the app's browser pane failed its HMR
  socket and never hydrated, so its page stayed server-rendered (no tier, no refraction). The same
  server in Chrome hydrated and refracted, and the visual pass used Chrome screenshots.

### Second-pass verification (commands and outcomes)

- `pnpm check` → exit 0 on the final code: Ruff clean, 1419 API unit tests (110 integration
  deselected), the web unit tests, 13 more, typecheck.
- **Full suites** `E2E_PORT=3092 pnpm test:e2e`, each on a fresh build:
  - before the Tinted-fallback fix: 483 passed, 0 failed, 129 skipped (the 3 new desktop tests
    included);
  - after it: 483 passed and 3 failed, all the new fallback test. It compared `"0.94"` with the
    minified `.94`; it now compares numbers.
- **On the final build** (`next build` + `next start`, then `E2E_EXTERNAL_SERVER=1`):
  `theme.spec.ts` and `layout.spec.ts` at all three widths → 175 passed, 0 failed, 11 skipped.
  This covers the fixed test, the offline banner beside the toolbar, and contrast and the blur
  budget on every route.
- **Scroll performance** on that build (230 records, CPU 4×, p95 / max in ms): default glass
  16.7 / 16.8 at desktop, 16.8 / 16.8 at phone-390 and 16.7 / 16.8 at phone-320.
  `E2E_GLASS=refract` 16.8 / 16.8, 16.7 / 16.8 and 16.7 / 16.8. That is unchanged from the
  47f37fc baseline, and the first pass's single 33 ms frame did not recur.
- **Visual pass** in Chrome against the dev server:
  - Reports, Home, Transactions (also at 1024 px), Ask, the account menu, quick add, a record,
    the demo, offline Home, the Tinted look, and `?glass=frost` and `?glass=solid`, at
    1440 / 1280 / 1024 / 390 px;
  - a 13 s screencast of the sidebar highlight, the pointer light and scrolling under the toolbar;
  - the wallpaper's darkest point, measured at seven viewport sizes.

## Not verified — do not claim

- **Safari (WebKit) and Firefox**, which get the `frost` tier by design. The iPhone 17
  simulator (iOS 26.3) was booted, but the app has not been granted access to it (as in the
  glass-theme round), so nothing was rendered in WebKit; it was shut down again. Grant access in
  the simulator panel, or open the preview on an iPhone, to check it.
- **A real budget Android phone's GPU.** CPU throttling does not model GPU cost; the jank guard
  and the low-memory rule are the safety net. Check scrolling Transactions on a mid-range phone.
- **Comprehension with real people** (the 5-second script in the glass-theme handoff still
  applies, now with the platter instead of the black capsule).
