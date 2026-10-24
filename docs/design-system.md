# FinBoy design system — light, 3D, premium

The marketing page follows three reference shots: an airy 3D hero (lavender slabs,
neon-violet underglow, a frosted glass track with a gold coin), iridescent coin and
chrome-check product renders, and a mosaic of light landing sections with glass AI orbs.
Everything is **light theme** and motion feels weighted, never bouncy. Real-time **WebGL**
belongs to the marketing page; daily app screens are static and state-led (see *App screens*).

There is no `/styleguide` route in the shipped app; it exists only on the unmerged design
branch `phase1/d-design-3d`. The product's states and patterns are specified in
[`docs/ux-round/ui-spec.md`](ux-round/ui-spec.md); `pnpm test:e2e` exercises them in a browser.

## Principles

1. **Calm surface, rich depth.** Off-white lavender canvas, white cards, one accent family
   (violet → magenta), gold only for money objects.
2. **3D carries meaning.** Coins are money, glass is privacy/transparency, the orb is the
   assistant, the check is verification. No decorative 3D without a story.
3. **Numbers are sacred.** Tabular figures, `₹` with Indian grouping, never "bank balance".
4. **Everything degrades gracefully.** No WebGL → CSS poster; reduced motion → still frames.

## Tokens (`apps/web/src/app/globals.css`)

| Token | Value | Use |
| --- | --- | --- |
| `ink` / `ink-soft` / `ink-subtle` | `#14122b` / `#57546e` / `#68657f` | Text hierarchy; every step ≥ 4.5:1 on white, canvas and glass |
| `canvas` | `#f5f4fb` | Page background (also every 3D scene's clear colour) |
| `lilac` · `periwinkle` · `blush` · `sun` | soft washes | Gradients, tints |
| `violet` · `violet-deep` · `orchid` · `magenta` · `neon` | `#6d4aff` … `#d63af9` | Accent, focus, highlights |
| `gold` / `gold-soft` | `#f2b544` / `#ffd27a` | Money objects only |
| `sky` | `#3e7bfa` | Assistant / AI |
| `positive` · `negative` · `warning` | `#047857` · `#c4262e` · `#d97706` | Verified/income, destructive, attention. `warning` is for icons/dots only; attention text uses `amber-800/900` |

Shadcn variables (`--primary`, `--card`, `--border`, …) map onto these, so primitives
inherit the system. Utilities: `glass`, `surface`, `eyebrow`, `text-gradient`, `tabular`,
`bg-aurora`, `grain`, `mask-fade-edges`, shadows `shadow-soft|lift|glow|hairline`, easing
`ease-out-expo` / `ease-in-out-quint`.

**Type:** Plus Jakarta Sans Variable (display + UI) with Anek Malayalam Variable as the
Malayalam fallback. Mark language on text: `lang="ml"`/`"hi"` for native script and
`ml-Latn`/`hi-Latn` for romanized replies. Marketing headlines: weight 600, tracking −0.04em,
`leading-[1.02–1.05]`. Eyebrows: `.eyebrow` (11 px, 0.16em caps) — marketing only.

**Contrast (measured, WCAG 2.2 AA):** functional text ≥ 4.5:1 on its rendered surface. Phone
header and tab bar are 94 % white glass so labels keep contrast over the dark estimate card;
tab labels are 11 px `ink-soft` (≈ 6.4:1 worst case). Destructive buttons use `#c4262e` on a
10 % tint (≈ 5:1). Focus ring `#8b6bff` ≥ 3:1. `layout.spec.ts` asserts the navigation case.

## App screens

- **One page header** (`components/app-shell/page-header.tsx`): direct task title
  (Overview, Transactions, Review, Ask FinBoy, Sources, Import results, Privacy & data) at
  28–32 px semibold, one supporting sentence, actions on the right. No eyebrows or poetic
  titles on daily screens; brand voice lives in the supporting text.
- **Surfaces:** `surface` cards with 28 px radius for panels; amber tint for attention;
  the dark `bg-ink` estimate card is the one hero per screen. Avoid nesting cards in cards.
- **Feedback:** `ProblemNotice` (what didn't happen, whether anything changed, next action,
  request reference), `LoadingPanel`, `EmptyState`, `RefreshingLabel` — see the state matrix
  in `ui-spec.md`. Successes are polite live regions; failures are alerts.
- **Records:** `RecordGlyph` distinguishes spending, income, refunds (undo arrow), transfers and
  failed attempts (ban, struck-through amount); rows show kind, provenance tags and the record's
  effect on totals.
- **Navigation chrome:** desktop glass sidebar with account footer; phones get a compact header
  with an account menu and a content-sized five-tab bar that hides while typing. Nothing else
  is fixed over content.

## Primitives (`components/ui`)

- **Button** — `default` (ink pill, primary action), `brand` (violet→magenta gradient,
  AI actions), `glass`, `outline`, `secondary` (lilac), `ghost`, `destructive`, `link`.
  Sizes `sm` 36 px, `default` 44 px, `lg` 48 px, `icon*`. Pills everywhere.
- **Card** — 28 px radius, white, `shadow-soft`, hairline ring. Prefer `surface` for
  custom blocks.
- **Badge** — `default` (lilac), `solid`, `positive`, `warning`, `outline`, `destructive`.
- **Input** — 44 px, 12 px radius, white with inset hairline.

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
(`stiffness≈380, damping≈32`) for selection pills. **Never branch rendered output on
`useReducedMotion()`** (server and client differ → hydration errors); freeze motion in
effects, transitions, or CSS (`motion-reduce:`) instead.

**One clock.** Import GSAP only from `components/motion/gsap.ts`. Each GSAP tick runs, in
order: Lenis (scroll) → ScrollTrigger → tweens → both WebGL canvases (`TickerFrameloop`),
so 3D never trails scrolled DOM by a frame. 3D choreography (intros, loops, scroll scrubs)
tweens plain objects in refs that `useFrame` reads — never React state. Loops use sine
yoyos with unrelated durations or tweens that return to their start, so nothing visibly
repeats or jumps.

## 3D architecture (`components/three`)

```text
HeroCanvas (marketing hero only)          SceneLayer (one fixed transparent canvas, z-10)
  own WebGL context, sun shadow map,        └─ drei <View.Port/> renders every <SceneSlot>
  bloom → Neutral tone map → SMAA              scissored into the slot's rectangle
  mounted on idle after first paint        SceneSlot (DOM placeholder, lazy, in-view)

Both canvases use frameloop "never" and are advanced by the GSAP ticker (TickerFrameloop).
```

- **Use 3D only through `<SceneSlot spec={...} className="h-72" />`.** Mount
  `<SceneLayerMount />` once per layout/page that has slots (today only the marketing page).
  The app layout deliberately mounts none: daily screens ship no three.js (audit F35). Add 3D
  to an app screen only when it carries task state and has a phone-tested budget.
- Slots render **above** DOM (canvas `z-10`). DOM that must overlap a scene (buttons on a
  scene background) needs `relative z-20`.
- Scenes: `coin-swirl` (`merge` 0–1 or `loop`), `check-orb`, `voice-orb` (`state`,
  `level` ref 0–1), `coin-stack` (`values` 0–1), `privacy-vault`, `inbox-slab`, `ribbon`.
- **Quality tiers** `high | medium | low` from device hints (software renderers → `low`).
  `AdaptiveQuality` (drei `PerformanceMonitor`) moves the DPR within the tier's range and
  steps a tier down only when the range is exhausted, and only while the page is visible.
  QA override: append `?quality=high|medium|low` (pins the tier).
- **Fallbacks:** `useWebGLSupport()` probes once; `WebGLBoundary` contains any GPU/driver
  failure; the hero keeps its CSS poster. Reduced motion renders still frames on demand.

### Assets (`public/models`, `lib/assets.ts`)

Sculpted forms are real GLBs, not primitives. `apps/web/scripts/3d/build_assets.py` builds
them in Blender: the ₹ coin (`Coin`, 84-ridge reeded edge for close-ups; `CoinLite`, 48
broad ridges for small or many coins; brand stroke in bevelled relief) and the
verification dome (`CheckDome`). gltfpack then meshopt-compresses them (float positions,
12-bit normals so chrome stays band-free). Rebuild with
`pnpm --filter @finboy/web assets:3d` (Blender 5; set `BLENDER=/path/to/Blender` if it is
not in `/Applications`). Load them with `useCoinGeometry("full" | "lite")` and
`useDomeGeometry()`; the geometry is cached and shared — never dispose it. Parametric
shapes (the hero track sweep, the ribbon, rounded slabs) stay procedural.

### Rendering

- **Colour.** Linear workflow with Khronos **Neutral** tone mapping: the hero applies it
  as a postprocessing effect (renderer `NoToneMapping`), the SceneLayer on the renderer.
  `preToneMapped(css)` (`lib/tone.ts`) inverts Neutral so a rendered colour lands exactly
  on a CSS token (hero background and fog, the voice orb's backdrop).
- **Light.** Image-based, from `studio-environment.tsx`. The hero uses
  `HeroSkyEnvironment` (gradient dome, window, top, fill and magenta bounce
  Lightformers at `environmentIntensity` 0.5) plus a spot-light "sun" projecting a
  window gobo — the only shadow-casting light. Product scenes use
  `ProductStudioEnvironment tone="dark"` (metals keep contrast) or `"light"` (pastels,
  glass) with one warm key light.
- **Materials** (`lib/materials.ts`): `createGold`, `createAnodised` (interference-film
  metal), `createIridescentChrome`, `createSatinAcrylic`, `createFrostedAcrylic`,
  `createSurfaceGlass` (alpha-blended), `createGlass` (transmission + dispersion),
  `createNeon` (HDR emissive).
- **Shadows** (`lib/soft-shadows.ts`). `patchStableSoftShadows()` replaces three's PCF
  filter (5 taps rotated by screen-space noise, which crawls under camera motion) with a
  separable texel-space tent: `shadow.radius` is the tent's half-width R in texels, R×R
  hardware-filtered taps, no stair-steps. Sun: 2048 px / R 4 on `high`, 1024 px / R 3
  otherwise. Translucent casters use `createTranslucentShadowMaterial()` (half the caster
  dropped on a texel checkerboard → a uniform half-strength shadow).
- **Underglow** (`hero/floor-spill.ts`). The slabs' LED spill is the exact diffuse
  irradiance of each rectangular emitter (Lambert's polygon form factor), evaluated only in
  the floor shader — the same light a `RectAreaLight` gives a matte floor, on every tier.
- **Post** (hero only): mipmap bloom with `luminanceThreshold` 5, so only HDR LEDs and
  specular glints bloom (sunlit white stays ≈ 1–3), then Neutral and SMAA. Screen-space AO
  was measured and dropped: ≈ 15 fps even at half resolution, for barely visible contact
  shading under floating slabs.
- **Motion.** The hero camera is a layered rig — rest frame per aspect, GSAP intro (3.6 s),
  scroll push-in, slow idle drift on incommensurate periods, damped pointer parallax —
  with lens shift (`setViewOffset`) for composition. Coins ride an energy-based track
  model (speed from drop and drag, lean into curves, rolling angle from arc length), so
  their motion is continuous and frame-rate independent.

### Adding a scene

1. Create `scenes/<name>.tsx`: geometry from GLBs (`lib/assets.ts`) or parametric code,
   materials from `lib/materials.ts`, deterministic randomness from `lib/random.ts`.
   Dispose what the scene creates (never shared GLB geometry).
2. Choreograph with `useGSAP` from `components/motion/gsap.ts`, tweening plain objects in
   refs that `useFrame` reads. Under reduced motion, skip the tweens and hold a pose.
3. Add it to `SceneSpec` (`scene-spec.ts`), `STAGES` and `renderScene` (`scene-view.tsx`):
   the `dark` studio for metals, `light` for pastels and glass.
4. Verify desktop + mobile + reduced motion + `?graphics=off` on the page that uses it.

### three.js r186 notes (learned the hard way)

- Materials without their own `envMap` take **`scene.environmentIntensity`** and ignore
  `envMapIntensity`. Keep scene environment low for matte surfaces and give glass/metal
  their own reflections with `useOwnReflections()`.
- `PCFSoftShadowMap` is gone — use `shadows="percentage"`. three's published build strips
  GLSL comments, so anchor `ShaderChunk` patches on code (`soft-shadows.ts` warns in
  development if its anchor disappears).
- A light allocates its shadow map once: a new `shadow.mapSize` needs a new light (the
  hero sun is keyed by tier).
- With a transparent canvas, three clears the transmission buffer to white at half alpha,
  so transmissive glass in the SceneLayer refracts a white haze. Use `createSurfaceGlass`
  there, or put an opaque backdrop behind the glass (voice orb).
- `RectAreaLight` needs `RectAreaLightUniformsLib` (~110 KB gzip of LTC tables) and is
  evaluated in every lit material; light one receiver analytically instead (`floor-spill`).
- drei's bundled meshopt decoder predates gltfpack 1.x: load GLBs with three's
  `GLTFLoader` and `meshopt_decoder.module.js`.
- Don't add the `Noise` effect before tone mapping (speckles).
- React Compiler lint forbids mutating hook-returned values in `useFrame`; reach materials
  through object refs, use method calls (`.copy()`, `.set()`), and keep animated scalars
  in `useRef`.

## Performance budget

| Item | Budget (measured 2026-10-24, production build) |
| --- | --- |
| Initial JS, gzip | ≤ 280 KB (landing 266 KB) — no three.js |
| Lazy 3D JS, gzip | ≈ 420 KB (three 254, postprocessing 89, R3F/drei/scenes 77), after first paint |
| Models | 370 KB (coin 243, dome 127), fetched with the 3D bundle |
| Device pixel ratio | adapts within 1–1.75 (high), 0.9–1.5 (medium), 0.75–1.25 (low), capped by the screen |
| Frame rate | hero 58–60 fps at 1440×900 on an Apple M4 (headless Chrome, Metal), DPR settling at 1.55–1.75 on `high`; `medium` holds 60 |
| Frame loop | hero pauses off-screen and in hidden tabs; Views skip off-screen slots |

## Verification

`pnpm check`, `pnpm build`, then browser checks at 1440×900, 390×844 and 320×740 with
`?quality=high|low` and default tiers, reduced motion emulation, and WebGL disabled
(`--disable-webgl`). The hero exposes `data-hero-canvas="ready"` for automated captures;
let the 3.6 s intro settle before judging composition. Measure frame rate in headless
Chrome with the GPU enabled (`--use-angle=metal` on macOS) and nothing else rendering
WebGL; never with `--disable-frame-rate-limit`, which makes rAF timings meaningless.
