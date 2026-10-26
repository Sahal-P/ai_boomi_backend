# FinBoy design system — glass, sunflower moments, line art

Daily screens follow a glass reference: a soft neutral field with a cool and a warm glow,
frosted cards, near-black type and black pill actions. The one money number per screen sits on
solid **sunflower** yellow, and the screens people pass through — sign-in, empty and all-done
states, the landing hero — are flat yellow **moments** with drawn line-art illustrations. When
FinBoy's AI is working, a dotted **thinking orb** shows it. Everything is light theme.
Real-time WebGL remains only in the landing page's lower sections (see *3D on the landing
page*); the hero is a yellow moment.

The values below were measured from the reference images, not eyeballed; the measurements,
contrast findings and verification are recorded in
[`docs/handoffs/glass-theme.md`](handoffs/glass-theme.md). Product states and patterns are
specified in [`docs/ux-round/ui-spec.md`](ux-round/ui-spec.md).

## Principles

1. **Calm glass for the work, sunflower for the moments.** Glass and ink carry the money
   screens; yellow appears only as the hero number's card and as moments. Never put glass over
   yellow: blurred yellow over the blue field turns muddy.
2. **Blur only where content moves underneath.** In-flow cards are frosted tint without
   `backdrop-filter` (the field behind them is already soft); real blur is for the phone header
   and tab bar, menus and dialog scrims — at most three blurred layers in view.
3. **Measured contrast.** Every text is ≥ 4.5:1 (large ≥ 3:1) and every form-control boundary
   ≥ 3:1 against its composited background, at the field's darkest point. The reference's own
   greys (3.97–4.29:1) and placeholder (2.68:1) fail; ours are darker.
4. **Numbers are sacred.** Tabular figures, `₹` with Indian grouping, never "bank balance".
5. **The orb means FinBoy's AI is working.** Data loading keeps the plain spinner.
6. **Everything degrades gracefully.** No `backdrop-filter`, Reduce Transparency, Increase
   Contrast, forced colours and reduced motion each give a legible screen.

## Tokens (`apps/web/src/app/globals.css`)

| Token | Value | Use |
| --- | --- | --- |
| `ink` / `ink-soft` / `ink-subtle` | `#0e1013` / `#474b52` / `#575b63` | Neutral text hierarchy; every step ≥ 4.5:1 on the field's darkest point and on glass over it |
| `field` · `field-cool` · `field-warm` | `#e1e3e6` · `#b9deeb` · `#e8d3b0` | The app background and its two glows (measured from the reference) |
| `glass-fill` · `glass-rim` · `glass-edge` | `rgb(236 236 238 / .74)` · white 85% · white 55% | In-flow frosted glass, its lit top-left rim and edge |
| `well` | white 50% | A lighter well inside glass |
| `float-fill` · `glass-blur` | `rgb(250 250 251 / .74)` · `blur(24px) saturate(140%)` | Floating glass; the blur goes through the variable (see below) |
| `sunflower` / `sunflower-ink` | `#fed234` / `#3a2c00` | Hero and moment fill / secondary text on it (9.4:1). A fill under ink only: 1.18:1 as a line or text on glass |
| `positive` · `negative` · `warning` | `#065f46` · `#a8201a` · `#d97706` | Verified/income, destructive, attention (`warning` for icons/dots; attention text uses `amber-800/900`) |
| `canvas` | `#f5f4fb` | The landing page and every 3D scene's clear colour (scenes are tone-matched to it) |
| `violet-deep` | `#4b2fd1` | The wordmark on yellow (5.51:1). Violet is otherwise retired from app screens |
| `gold` · `lilac` · `violet` · … | — | Landing page and 3D scenes only |

Shadcn variables map onto these: `--primary` is ink (black pills), `--card` is glass,
`--popover` is 90% white, `--secondary`/`--muted`/`--accent` are faint ink tints, `--input`
(form-control boundaries) is ink at 50% (≥ 3:1), `--ring` is ink. Radii follow the reference:
`lg` 12 px (rows, fields), `2xl` 20 px, `3xl` 24 px (panels), pills for actions.

**Keep `-webkit-backdrop-filter` and `backdrop-filter` behind a variable.** With literal values
the CSS minifier merges the pair into the `-webkit-` form only, which Chrome and Firefox ignore
— the previous `.glass` never blurred outside Safari. `theme.spec.ts` asserts the header blurs.

## Materials

| Class | What it is | Where |
| --- | --- | --- |
| `bg-field` | Fixed pseudo-element field + grain (never repaints on scroll; iOS ignores `background-attachment: fixed`) | App shell, session check, demo, 404 |
| `surface` | In-flow frosted glass: tint, 1 px white edge, inset top-left rim, soft shadow; **no blur** | Cards, panels, rows, the desktop sidebar (nothing scrolls under it) |
| `glass` | Floating glass: `float-fill` + `--glass-blur` | Phone header and tab bar (near-opaque), menus, selects, landing nav after the hero |
| `float-panel` | Crisp near-opaque panel; its frosted scrim (`bg-ink/20 backdrop-blur-sm`) is the blurred layer | Dialogs, sheets, alert dialogs |
| `solid-hero` | Sunflower with ink and a soft warm shadow | The one money number per screen (Overview, demo) |
| `moment` | Flat sunflower with ink | Sign-in, empty and all-done states, Ask's empty state, landing hero |

Inside yellow, use white tints (`bg-white/55`), never glass. Fallbacks (unlayered, so they win
over utilities): no `backdrop-filter` → near-opaque `.glass`; **Reduce Transparency** →
`--glass-blur: none` (also on `backdrop-blur-*` scrims), opaque surfaces, flat field;
**Increase Contrast** → darker secondary ink, 45% ink edges, 75% ink control boundaries;
**forced colours** → `CanvasText` borders on every material.

## Type

Plus Jakarta Sans Variable (the closest loaded match to the reference's geometric sans) with
Anek Malayalam Variable as the Malayalam fallback; Hindi uses the system Devanagari font. Page
titles weight 500 at −0.025em (28/32 px); month headings 20 px/500; record names 14 px/600;
amounts 15 px/600 tabular. Yellow moments use weight 800 headlines at −0.045em (the
reference's welcome screen). Mark language on text: `lang="ml"`/`"hi"` for native script and
`ml-Latn`/`hi-Latn` for romanized replies.

## App screens

- **One page header** (`components/app-shell/page-header.tsx`): direct task title, one sentence
  of support, actions on the right. Screens reached from another one (Import results) pass
  `back` for the reference's glass square back button; top-level tabs never do.
- **Navigation:** desktop glass sidebar (in-flow, no blur) with a black active capsule;
  phones get a compact blurred header (wordmark, white account button) and the reference's
  floating tab bar — black active capsule with white icon and label, every other tab keeps its
  label in secondary ink. Content-sized cells keep "Transactions" readable at 320 px. Nothing
  else is fixed over content. Phone page margins are 24 px from 390 px up, 16 px below.
- **Overview:** the sunflower estimate with its calculation beside it on a white tint, then the
  reference's action tiles — Ask, Review (with the waiting count), Sources, What if — which
  all open existing destinations.
- **Records:** each record is a glass card (12 px radius, 8 px apart) with a circular glyph;
  Transactions groups them under IST month headings; the "how it counts" line sits under the
  details on phones and under the amount on wider screens (one element, placed by the grid).
  Filters: a search field and, on phones, a filter button that folds the five selects away
  and shows how many are on.
- **Feedback:** `ProblemNotice`, `LoadingPanel`, `RefreshingLabel` (spinner), amber
  attention strips. Successes are polite live regions; failures are alerts.

## Yellow moments

`EmptyState` always renders a moment with an illustration (first on phones, beside the text
on wider screens): no records yet, nothing matches, all reviewed, an empty month. Sign-in is
a full-page moment (violet-deep wordmark, 2 px ink-bordered field, black pill whose chevron
capsule is decoration — never a swipe) with a sunflower `themeColor`; the landing hero is the
same moment with the existing headline and CTAs. Ask's empty state is a moment with the
resting orb.

## Thinking orbs (`components/feedback/thinking-orb.tsx`)

[thinking-orbs](https://github.com/Jakubantalik/thinking-orbs) 0.3.1 (MIT, 2D canvas, no
dependencies, ≈ 7.4 KB gzip), pinned exactly: its tarball matches the tagged `v0.3.1` source;
npm's 0.3.2 was published from a commit absent from the public repository. The wrapper pins
the dark-ink theme (the library's `auto` would draw light dots under a dark OS setting), is
`aria-hidden` unless given a label (nearby text says what is happening), marks the canvas
`data-thinking-orb`, and with `rest` stops decorative motion after five seconds (WCAG 2.2.2).
Sizes are the library's two tuned designs: 64 and 20. Reduced motion draws one still frame;
orbs pause offscreen and in hidden tabs.

| Where | State · size |
| --- | --- |
| Ask's empty state (moment) | breathing · 64, rests after 5 s |
| Answer pending | searching · 64 |
| Transcribing a recording (never while recording: the real mic level is the honest signal) | listening · 20 |
| Preparing a spoken answer | composing · 20 |
| Import running; Sources' link to it | working · 64 / 20 |
| Sign-in and landing-hero illustration (FinBoy's reply bubble) | composing · 20, rests after 5 s |
| Landing voice demo status line | listening → searching → composing · 20 |

## Illustrations (`components/illustrations/`)

`kit.tsx` draws on 240-unit artboards: 2.5-unit strokes in `currentColor` (forced colours
adapt), round caps and joins, white fills, sunflower as the only colour fill, halftone shading
from a 4.5-unit dot grid (the orbs' dot language), four-point sparkles and "pop" lines, and
the ₹ coin built from `BrandMark`'s rupee path. Patterns and clip paths use per-instance
`useSvgId()`: a shared id breaks when a copy sits in a hidden subtree. Scenes (`scenes.tsx`,
each well under 6 KB, decorative): `MoneyScene` (sign-in, landing hero), `NoRecordsArt`,
`NoMatchArt`, `AllReviewedArt`, `EmptyMonthArt`. Brand assets supplied later replace these
defaults where they conflict.

## Primitives (`components/ui`)

- **Button** — `default` (ink pill, primary action), `glass` (in-flow glass), `outline`
  (white pill, faint ink border), `secondary` (ink tint), `ghost`, `destructive`, `link`.
  Sizes `sm` 36 px, `default` 44 px, `lg` 48 px, `icon*`. Pills everywhere.
- **Card** — `surface`, 24 px radius. **Badge** — `default` (ink tint), `solid`, `positive`,
  `warning`, `outline`, `destructive`. **Input / Textarea / Select** — white 80%, 12 px radius,
  50% ink boundary (≥ 3:1), placeholder in secondary ink.
- **Dialog / AlertDialog / Sheet** — `float-panel` over a frosted ink scrim; **DropdownMenu /
  Select content** — `glass` with the 90% popover fill. **Switch** — ink track, white thumb.

## Motion (`components/motion`)

| Primitive | Use |
| --- | --- |
| `Reveal` | Fade-up out of a blur when a block enters view (once). |
| `AnimatedAmount` / `formatRupees` | Paise in, `₹` out; counts up in view, final value server-rendered. |
| `TiltCard` | Pointer tilt + glare for feature cards (keep `max ≤ 3` if it contains a SceneSlot). |
| `SmoothScroll` | Lenis inertial scroll — marketing page only, driven by the GSAP ticker. App screens use native scrolling. |
| `gsap.ts` | The page's single animation clock: `gsap`, `ScrollTrigger`, `useGSAP`. |
| `.rise-in`, `.line-mask` + `.line-up` | CSS entrances for above-the-fold copy (no JS needed). |
| `<ViewTransition default="page">` | App route crossfade (in `(app)/layout.tsx`; disabled under reduced motion). |

Rules: durations 0.6–1.3 s for reveals, 0.2–0.35 s for UI feedback; springs
(`stiffness≈380–420, damping≈32–36`) for the nav capsule. **Never branch rendered output on
`useReducedMotion()`** (server and client differ → hydration errors); freeze motion in
effects, transitions, or CSS (`motion-reduce:`) instead. Import GSAP only from
`components/motion/gsap.ts`; each GSAP tick runs Lenis → ScrollTrigger → tweens → the WebGL
canvas (`TickerFrameloop`), so 3D never trails scrolled DOM by a frame.

## 3D on the landing page (`components/three`)

```text
SceneLayer (one fixed transparent canvas, z-10)
  └─ drei <View.Port/> renders every <SceneSlot> scissored into the slot's rectangle
SceneSlot (DOM placeholder, lazy, in-view)
The canvas uses frameloop "never" and is advanced by the GSAP ticker (TickerFrameloop).
```

- **Use 3D only through `<SceneSlot spec={...} className="h-72" />`** with `<SceneLayerMount />`
  mounted once per page that has slots (today only the landing page). Daily screens ship no
  three.js (audit F35); thinking orbs are 2D canvases, not WebGL. Add 3D to an app screen only
  when it carries task state and has a phone-tested budget.
- Slots render **above** DOM (canvas `z-10`); DOM that must overlap a scene needs `relative z-20`.
- Scenes: `coin-swirl` (`merge` 0–1 or `loop`), `check-orb`, `voice-orb` (`state`, `level`
  ref 0–1), `coin-stack` (`values` 0–1), `privacy-vault`, `inbox-slab`, `ribbon`.
- **Quality tiers** `high | medium | low` from device hints (software renderers → `low`);
  `AdaptiveQuality` (drei `PerformanceMonitor`) moves the DPR within the tier's range and steps
  down only when the range is exhausted, and only while the page is visible. QA override:
  `?quality=high|medium|low`. **Fallbacks:** `useWebGLSupport()` probes once; `WebGLBoundary`
  contains GPU/driver failures; `?graphics=off` and reduced motion keep the DOM.
- **Assets** (`public/models`, `lib/assets.ts`): the ₹ coin (`Coin`, `CoinLite`) and
  verification dome (`CheckDome`) are Blender-built GLBs (`apps/web/scripts/3d/build_assets.py`,
  `pnpm --filter @finboy/web assets:3d`, Blender 5), meshopt-compressed by gltfpack. Load them
  with `useCoinGeometry("full" | "lite")` and `useDomeGeometry()`; the geometry is shared —
  never dispose it.
- **Rendering:** linear workflow with Khronos Neutral tone mapping on the renderer;
  `preToneMapped(css)` (`lib/tone.ts`) lands a rendered colour exactly on a CSS token (the voice
  orb's backdrop is `--canvas`, so the landing keeps the lavender canvas). Light is image-based
  from `ProductStudioEnvironment tone="dark"` (metals) or `"light"` (pastels, glass). Materials:
  `lib/materials.ts`.
- **Adding a scene:** create `scenes/<name>.tsx` (GLB or parametric geometry, materials from
  `lib/materials.ts`, randomness from `lib/random.ts`; dispose what it creates), choreograph
  with `useGSAP` tweening plain objects that `useFrame` reads (hold a pose under reduced
  motion), add it to `SceneSpec`, `STAGES` and `renderScene`, and verify desktop, mobile,
  reduced motion and `?graphics=off`.
- **three.js r186 notes:** materials without their own `envMap` take
  `scene.environmentIntensity` (give glass/metal `useOwnReflections()`); with a transparent
  canvas, transmissive glass refracts a white haze — use `createSurfaceGlass` or an opaque
  backdrop; drei's bundled meshopt decoder predates gltfpack 1.x — load GLBs with three's
  `GLTFLoader` and `meshopt_decoder.module.js`; React Compiler lint forbids mutating
  hook-returned values in `useFrame` (use refs and `.copy()`/`.set()`).

## Performance budget

| Item | Budget / measurement |
| --- | --- |
| Blurred layers | ≤ 3 in view on every route and state (`theme.spec.ts`) |
| Scroll frame time | 230-record list, CPU 4×: p95 16.7–16.8 ms, max 16.8 ms on desktop and phone-390 — same as before the theme (`perf.spec.ts`, 27 Oct 2026) |
| Initial JS, gzip | ≤ 280 KB, no three.js; thinking orbs add ≈ 7.4 KB |
| Lazy 3D JS | three + R3F/drei/scenes, after first paint; the hero canvas and `postprocessing` (≈ 89 KB) are gone |
| Device pixel ratio | adapts within 1–1.75 (high), 0.9–1.5 (medium), 0.75–1.25 (low), capped by the screen |

CPU throttling doesn't model a budget phone's GPU, where blur costs most: that is why blur is
capped and kept off in-flow cards. Real-device checks are listed in the handoff.

## Verification

`pnpm check`, `pnpm build`, `pnpm test:e2e` (1440×1000, 390×844, 320×740), which includes
`theme.spec.ts`: rendered contrast for text, placeholders and form-control boundaries on every
route and moment, the blur budget, real blur in Chromium, Reduce Transparency / Increase
Contrast / forced-colours fallbacks, and the orbs' theme pin, accessibility and resting.
Opt-in: `E2E_CAPTURE_DIR=<dir>` (`capture.spec.ts`) screenshots every route and state for a
before/after review; `E2E_PERF=1` (`perf.spec.ts`) measures scroll frame times.
