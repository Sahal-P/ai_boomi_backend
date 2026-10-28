# FinBoy companion logo — 28 October 2026

The human confirmed option 2: the sunflower-yellow **b / speech bubble** logo. Work is on
`feat/finboy-branding` from `574b4ca`. The original generated concepts and unrelated
untracked pitch files are preserved.

## Delivered

- Twelve standalone SVGs in `apps/web/public/brand/`: horizontal primary/dark/mono/white,
  stacked, ink/white wordmarks, primary/mono/white tiles, bare symbol and maskable icon.
- Font-independent wordmarks outlined from the existing Plus Jakarta Sans ExtraBold 800;
  font licence included. No raster embedding, scripts, external references or new packages.
- Updated shared `Brand` and `BrandMark`, including navigation, demo, 404, sign-in, public
  legal pages and footer. `FinBoy home` remains the linked logo's accessible name.
- Updated SVG/ICO browser icons, Apple touch icon and a typed manifest with standard and
  maskable app icons. No service worker or financial-data caching was added.
- README branding, design-system/product documentation and `docs/branding.md` usage guide.
- PNG exports, visual brand sheet and verified 33-file ZIP in
  `output/branding/finboy-approved/`.

## Verification

All checks ran locally. Browser data came exclusively from the existing test contract double;
no database, production test suite, external provider or production configuration was changed.

| Command / check | Actual outcome |
| --- | --- |
| `pnpm check` | Passed: Ruff, ESLint, 908 API unit tests, 48 web tests and strict TypeScript; 74 integration tests deselected |
| `NEXT_PUBLIC_API_URL=/ pnpm build` | Passed: optimized production build, including `/icon.svg`, `/apple-icon.png` and `/manifest.webmanifest` |
| Playwright capture subset (command below) | 21 passed on Chrome at 1440×1000, 390×844 and 320×740 |
| Browser states captured | Landing, signed-in overview, loading, degraded, offline, empty overview, sign-in and wrong password |
| Additional browser inspection | Legal and 404 logos loaded without horizontal overflow at 1440/390/320 px; favicon, Apple and manifest links present |
| Served asset check | All twelve SVGs and manifest icons returned HTTP 200 with appropriate SVG MIME types |
| Vector/raster inspection | Twelve parseable path-only SVGs; `app/icon.svg` matches the primary mark; PNG dimensions, ICO 16/32/48 entries and fully opaque maskable safe area verified |
| Archive check | ZIP integrity passed; 33 files |

```sh
E2E_PORT=3062 E2E_REUSE_SERVER=1 \
E2E_CAPTURE_DIR=/Users/sahal/Dev/FourNotFour/ai_boom/output/branding/finboy-approved/browser \
pnpm --filter @finboy/web exec playwright test e2e/capture.spec.ts --grep '(landing|login|overview)'
```

The capture command reused the local server started with
`pnpm --filter @finboy/web exec next start --hostname 127.0.0.1 --port 3062` after the build.
That preview server was stopped after verification.

Screenshots are under `output/branding/finboy-approved/browser/`. Visually inspected the
brand sheet, desktop landing hero, desktop overview, 390 px overview, 320 px sign-in,
390 px landing hero and the 320 px degraded/offline header states. The yellow tile naturally
blends into the existing yellow landing/sign-in backgrounds, leaving the ink symbol visible.

One ad-hoc browser inspection initially used a non-unique `FinBoy home` selector on the 404
page, which also has a separate recovery link. Selecting the logo by its existing aria-label
resolved the inspection ambiguity; no application change was needed.

## Limits and release state

No live backend or human phone-install acceptance is claimed. Desktop/mobile checks used
Chrome emulation rather than physical iOS/Android devices. The existing local servers on
3061/8061 were left running. No commit, push, merge or deployment was performed.
