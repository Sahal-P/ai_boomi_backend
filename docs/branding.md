# FinBoy companion identity

The human selected the yellow companion logo (option 2) on 28 October 2026. It replaces
the faceted rupee gem. FinBoy is a **personal finance companion**; the identity does not
restrict the product to a language, household type or input channel.

The lowercase **b** contains a speech bubble: your money is something you can ask about.
The sunflower tile keeps the mark friendly and recognisable, while the ink wordmark
provides contrast. This is a flat vector reconstruction of the approved image concept,
with deliberate curves and an outlined wordmark rather than an embedded raster image.

## Source assets

All twelve standalone SVGs live in `apps/web/public/brand/`. They contain editable paths,
no external references, no embedded images, no scripts, no gradients and no font dependency.

| File | Intended use |
| --- | --- |
| `finboy-logo.svg` | Primary horizontal lockup; transparent background, yellow tile, ink wordmark |
| `finboy-logo-dark.svg` | Horizontal lockup with yellow tile and white wordmark for dark surfaces |
| `finboy-logo-mono.svg` | One-ink horizontal lockup with a transparent knockout symbol |
| `finboy-logo-white.svg` | White horizontal lockup with a transparent knockout symbol |
| `finboy-logo-stacked.svg` | Centered mark above the wordmark for square compositions |
| `finboy-wordmark.svg` | Ink wordmark without the icon |
| `finboy-wordmark-white.svg` | White wordmark without the icon |
| `finboy-mark.svg` | Primary yellow companion tile |
| `finboy-mark-mono.svg` | One-ink tile with a transparent knockout symbol |
| `finboy-mark-white.svg` | White tile with a transparent knockout symbol |
| `finboy-symbol.svg` | Ink companion symbol without a tile |
| `finboy-mark-maskable.svg` | Full-bleed yellow square with the symbol inside the maskable safe area |

The wordmark uses outlined **Plus Jakarta Sans ExtraBold (800)**, already used by the app,
with optical tracking. Its font licence is included as `WORDMARK-LICENSE.txt`. Keep the
capitalisation **FinBoy**. Do not substitute live text in logo lockups.

## Colour and spacing

- Sunflower: `#FED234`.
- Ink: `#0E1013`.
- Reversed wordmark: `#FFFFFF`.
- Use at least one quarter of the tile height as clear space around the complete lockup.
- Use the horizontal lockup at a minimum tile height of 24 px; use the mark alone below that.
- Browser favicons are supplied at 16, 32 and 48 px. At these sizes the silhouette matters
  more than the small speech-tail detail. Use at least 24 px for interactive UI branding.
- Keep the original proportions. Avoid stretching, rotations, extra outlines, gradients,
  shadows and placing the ink wordmark on a dark surface.

## App integration

`src/components/brand.tsx` uses the primary SVGs with explicit dimensions and decorative
image alternatives. The linked lockup is labelled **FinBoy home** for assistive technology.
Navigation, sign-in and the footer share these components. The ₹ coin remains a currency
illustration and is not a logo.

Next.js file conventions supply `src/app/icon.svg`, `favicon.ico` and the 180 px
`apple-icon.png`. `src/app/manifest.ts` links the 192 px and 512 px app icons plus a separate
512 px maskable icon. The maskable image has an opaque yellow background and keeps the
symbol within its central safe circle. The manifest adds app identity only; it does not add
a service worker, cache financial records or promise offline operation.

The app remains light themed; the dark and monochrome assets are exports for other surfaces.
When changing the mark, update all variants and Next.js icons together.

## Exports and review

`output/branding/finboy-approved/` contains PNG exports, a visual brand sheet and
`finboy-brand-kit.zip`. The kit includes every SVG, the raster app icons, the favicon,
the Apple touch icon, the usage guide and the font licence. The original two generated
concepts remain in `output/branding/finboy-logo-concepts-2026-10-28/`.

Verification for this change is recorded in `docs/handoffs/finboy-branding.md`.
