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
3061/8061 were left running. At the initial handoff no commit, push, merge or deployment
had been performed; the human subsequently authorized all three on 28 October.

## Authorized publication and live verification

The human requested merge, push and deployment. Branding commit `65b05b6` was fast-forwarded
into main and pushed, with `feat/finboy-branding`, to both named GitHub repositories.
Vercel production deployment `FDd7Y8VjAxvJARiUR9LhsDLQ9S4N` reached Ready in 48 seconds and
aliased `finboy.antlegs.in`. The logo, mark and 512 px icon fetched from that domain match
the committed bytes. Manifest, favicon and Apple icon return 200; proxied health returns
200 and unauthenticated money summary returns 401. Direct backend health remains 200.

The live public landing page was checked in a fresh Chrome context at 1440, 390 and 320 px:
new logo loaded, manifest linked and no horizontal overflow. Production reads were limited
to public assets, the landing page, health and an unauthenticated access check; no financial
records, login codes, production tests or record mutations were used.

The local system resolver intermittently returned ENOTFOUND for the frontend domain.
Public DNS returned the configured Vercel CNAME and addresses; verification used that
resolved address with the original HTTPS hostname and normal certificate validation
(`curl --resolve` and a per-browser host resolver rule). No DNS or host configuration changed.

The GitHub workflow exposed six pre-existing pilot unit-test failures, also present on
baseline `574b4ca`. SQLite discards timestamp zones, while the helper used the real clock
instead of the business date. The helper now creates synthetic records at noon UTC on
`today_ist()`, so UTC CI, IST development and overridden demo dates agree. This changes
tests only, with no backend runtime or schema change. The six failing cases were reproduced
with `TZ=UTC DEMO_TODAY=2026-10-24` before the fix and all six passed afterward.
`TZ=UTC pnpm check` and `NEXT_PUBLIC_API_URL=/ pnpm build` both passed after the fix.

No backend restart, migration, production settings change or unrelated service operation
was needed. Public assets and read-only health/access checks establish this frontend release;
phone installation and earlier voice acceptance gaps remain as previously documented.
