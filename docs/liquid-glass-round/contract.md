# Liquid Glass round — contract (6 November 2026)

FinBoy's web app, landing page, public pages and sign-in take on Apple's Liquid Glass (iOS 26, with
the iOS 27 refinements): glass that bends what is behind it, lights up and flexes when pressed,
and springs from the control that opened it. It changes `apps/web` only — no API, contract,
database or dependency change. It supersedes earlier UI statements only where it says so:

- the phone header's frosted capsule and the black active capsule in the tab bar, the sidebar
  and Transactions' segmented control ([design system](../design-system.md), *Navigation*);
- the floating-glass recipe (`.glass`, `.float-panel`, blurred dialog scrims) for the app's
  chrome and overlays;
- "never put glass over yellow" — now "never put *frosted* glass over yellow": clear glass
  without blur may sit on a yellow moment.

## Human decisions (6 November 2026)

- **Look:** Apple's Liquid Glass "as exactly as possible", researched from Apple's HIG
  (*Materials*), *Adopting Liquid Glass*, WWDC25 *Meet Liquid Glass* and *Get to know the new
  design system*, the iOS 27 coverage, William Candillon's *Liquid Glass with React Native Skia*
  and kube.io's refraction write-up.
- **Scope:** the signed-in app, the landing page and public pages, and sign-in. The admin panel
  inherits the shared primitives only.
- **Selection:** Apple's — an ink icon and label on a light glass platter (tab bar, sidebar) or a
  raised glass knob (segmented controls), which turns into a magnifying lens while dragged.
- **Tab bar:** stays fixed; it does not shrink on scroll.
- **Glass look:** a **Clear · Tinted** choice in the account menu, like iOS 26.1's setting.
- **Where it lives:** branch `feat/finboy-liquid-glass` from main `47f37fc`; loopback web 3091
  with the contract double on 8091 (Playwright 3092); no migration.

## Rendering tiers (`lib/liquid-glass/tier.ts`)

| Tier | Who | What it draws |
| --- | --- | --- |
| `refract` | Chromium (Chrome, Edge, Samsung Internet — most of FinBoy's Android users) | An SVG displacement filter inside `backdrop-filter`, from a map computed per element (rounded-box SDF, convex-squircle bezel, Snell's law at n = 1.5), then a light frost, saturation and brightness |
| `frost` | Safari, Firefox, `deviceMemory` < 4, scrolling that stays janky (p90 > 22 ms), `?glass=frost` | Blur, saturation and brightness with the same rims, highlights, shadows and motion |
| `solid` | Reduce Transparency, Increase Contrast, forced colours, no `backdrop-filter`, `?glass=solid` | Near-opaque glass, no blur |

- Safari and Firefox drop the *whole* `backdrop-filter` declaration when it contains `url()`,
  so the filter is attached only after Chromium is confirmed (`navigator.userAgentData`).
- The server always renders `frost`; GlassProvider picks the tier after hydration and the
  refraction *materializes* (the lensing ramps in over 420 ms) instead of fading in.
- Chromium measures the filter in CSS pixels at every device pixel ratio (checked at DPR 1, 2
  and 3), so maps are not scaled per device.
- The saved Clear · Tinted choice is applied before first paint by an inline `<head>` script
  (Next.js's *Preventing flash before hydration* pattern).

## What changed

| Area | Before | Now |
| --- | --- | --- |
| Phone top | Frosted capsule with the wordmark and a white account button | The wordmark on the top scroll edge (iOS 27's uniform bar, shown once scrolled) and a 44 px glass account circle |
| Phone tab bar | Near-opaque frosted pill, black active capsule, ink + | Clear refracting pill, light platter under the active tab, a drag lens that magnifies the tabs, a tinted-glass + |
| Desktop sidebar | In-flow `surface` panel, black active capsule | Inset thick glass that bends the field's glows, light platter, tinted-glass Add entry |
| Buttons | Ink pill, `surface` and white outline | Tinted glass (`lg-prominent`), clear glass (`lg-static`); all flex and light up from the press point |
| Menus | `.glass` with a 90% fill | `.lg-menu`: refracting glass that pops open from its control on a gel spring |
| Dialogs and sheets | `float-panel` over a blurred ink scrim | `.lg-thick` refracting glass over a plain dimming layer; sheets float inset from the screen edge with 28–32 px corners |
| Ask composer | Frosted bubble | Refracting glass bubble; the ink boundary and sunflower focus halo stay |
| Segmented controls | Black active capsule | Clear track, raised glass knob, drag lens |
| Landing nav | Transparent over the hero, then frosted | Clear glass over the hero (sunflower-filled on phones), then refracting glass that materializes as the hero leaves |
| Sign-in | White tints on yellow | The same tints as clear glass on colour (`lg-on-color`), never blurred |
| Under floating bars | Content showed through near-opaque glass | Apple's scroll edge effect: content dissolves into the field beneath the bars (`ScrollEdge`) |

## Rules that still hold

Measured by `e2e/theme.spec.ts` and `e2e/layout.spec.ts` and described in the
[design system](../design-system.md): text ≥ 4.5:1 (now also against the darkest ink scrolled under
a floating bar, dissolved by the scroll edge), form-control boundaries ≥ 3:1, at most three
blurred or refracting layers in view in every state (an open menu, dialog or sheet makes the
floating chrome solid so it never becomes a fourth), legible Reduce Transparency, Increase
Contrast and forced-colours fallbacks, reduced motion without flex, stretch or overshoot, and
no frosted glass over yellow. Content cards keep the standard `surface` material: Apple keeps
Liquid Glass out of the content layer.

## Not in this round

- Liquid merging between separate glass shapes (the video's smooth-minimum bridges); the SDF
  engine makes it a later addition.
- Light/dark flipping of small glass and a dark mode: FinBoy stays light-only.
- Highlights that follow device motion: no motion sensors in a money app.
- The unused `Switch`, the unused toast component, and sliders (none exist).

## Verification

Recorded in [the handoff](../handoffs/liquid-glass.md): `pnpm check`, `pnpm build`,
`pnpm test:e2e` (desktop, 390 px, 320 px), scroll performance against the 47f37fc baseline,
before/after captures, and a browser pass at desktop and phone widths.
