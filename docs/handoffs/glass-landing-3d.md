# Glass landing 3D round — handoff (27 Oct 2026)

Branch `feat/finboy-glass-landing-3d` from `feat/finboy-glass-theme` at `9737c6c` (not yet merged
to `main`), in the worktree `.claude/worktrees/laughing-newton-59938b`. Loopback ports: web
3063, the test-only contract double 8063 (HTTPS with a temporary private certificate),
Playwright 3063. No database, no API change, nothing pushed or deployed.

## What changed

The follow-up left by the glass round (`docs/handoffs/glass-theme.md`): the landing below the
yellow hero now sits on the app's field, and its WebGL scenes are re-toned to the same world.
Mid-round the human also asked to recolour the logo and remove violet everywhere it showed.

- **Landing on the field.** `main.bg-field.isolation-auto` (not isolated, so DOM marked `z-20`
  stays above the shared 3D layer); the app's materials throughout — ink-soft eyebrows, ink
  icons and chips, glass panels, the simulator's estimate and the mosaic's overview tile on
  `solid-hero`. `--canvas`, `.bg-aurora`, `.text-gradient`, `.grain`, `--shadow-glow` and the
  violet/old landing palette are removed; the body's ground is `--field`. Theme colour: field by
  default, sunflower on the landing (it opens on the yellow hero), as on sign-in.
- **Scenes** (`components/three`): studio gels are the field's glows (cool left and below, warm
  right) on an ink or field-grey cove; coins are sunflower (half metal under a clear lacquer —
  full metal read as brass); the verification dome and the simulator's committed columns are
  lacquered ink; tray and plate pearl; glass neutral-cool; contact shadows and the vault's ring
  ink; the CTA ribbon runs cool → pearl → warm. Voice orb states: idle pale cool, listening
  vivid cool, thinking ink, speaking sunflower — distinct in value and hue.
- **No disc behind the voice orb.** The field is fixed to the viewport, so a flat backdrop could
  never match it while scrolling. The orb's refraction backdrop and its core's feathered edge
  now paint the `.bg-field` gradient recomputed per fragment (`lib/field.ts`, colours read from
  the CSS tokens, glows dropped under Reduce Transparency). Measured at 1440: inside the sphere
  versus just outside now differs by 2–9 levels (the glass's own inversion of the warm glow);
  before, the sphere was a disc 15 levels darker than the page.
- **Violet retired.** The logo is an ink gem with a sunflower ₹ (`components/brand.tsx`,
  `app/icon.svg` with a faint white rim for dark tab strips); the sign-in wordmark is ink;
  radios use the ink accent; the Sources sample card is glass.
- **Found and fixed:**
  1. `bg-field` was also a Tailwind colour utility (`--color-field` was registered), painting a
     flat field on the element. Isolated app shells hid it; on the landing it covered the glows.
     The mapping is removed (nothing used the colour utility).
  2. On phones the voice demo's status pill sat under the 3D layer, hidden by the orb, and
     wrapped onto two lines. It is now `z-20` and `whitespace-nowrap`.
- Removed as dead code: `createFrostedAcrylic` and its clearcoat fade (hero-only),
  `createAnodised`, `createIridescentChrome` and the JS `preToneMapped` (replaced).

## Verification (commands and outcomes)

- `env -u WEB_APP_URL DATABASE_URL=postgresql+psycopg://finboy@127.0.0.1:5433/finboy_glass3d_unit_none pnpm check`
  → exit 0: Ruff clean, 869 API unit tests passed (59 integration deselected), web lint clean,
  41 web unit tests passed, typecheck clean. The URL names no database; unit tests never
  connect.
- `pnpm build` → exit 0.
- `E2E_PORT=3063 pnpm test:e2e` → 202 passed, 0 failed, 119 skipped, including `theme.spec.ts`
  contrast and blur budget on `/` and the no-WebGL landing check at all three widths.
- Visual checks, headless Chrome on ANGLE Metal (scripted captures, not committed): every
  landing section at 1440, 390 and 320 with `?quality=high` and `?quality=low`, reduced motion,
  and `?graphics=off`; the voice orb in each state; the logo on the yellow hero, the scrolled
  glass nav, the app sidebar, the phone header and sign-in, and the favicon at 16–48 px on
  light and dark tab strips; before/after pixel samples across the orb's silhouette. Plus the
  desktop app's browser pane at 1440 and 375.

## Not verified — do not claim

- **iOS Safari (WebKit) and real phone GPUs**, as in the glass round. The field shader assumes
  the canvas and `.bg-field::before` share one box (both `position: fixed; inset: 0`), which
  should hold under Safari's dynamic toolbar but is unchecked.
- **Forced colours:** the orb's backdrop paints the field, not the system colour (the lavender
  canvas behaved the same way).
- **`theme.spec.ts` never measures against the field's darkest point.** Its `backdrop()` stops
  at the first opaque ancestor, and `body` is always opaque, so the `fieldDarkest` base is never
  reached: text is checked against the flat field on every route (before this round too). The
  tokens were chosen for the darkest point, but the test does not enforce it.
