# FinBoy design system — Liquid Glass, sunflower moments, line art

Daily screens follow a glass reference: a soft field with a cool and a warm glow, glass cards,
near-black type and ink actions. Since the Liquid Glass round
([contract](liquid-glass-round/contract.md)) the navigation layer floating above them — bars,
the sidebar, the desktop toolbar, menus, sheets, dialogs, the Ask composer — is Apple's **Liquid
Glass**: glass that bends what is behind it at its rim, lights up and flexes when pressed, and
springs from the control that opened it. Its second pass gave the app what makes Apple's glass
read as glass: a **wallpaper** with colour and shape behind it (the field's glows grown into sky
and apricot bands and a sunflower sun), cards as clear **widget glass** over it, controls that
content scrolls beneath, and light that follows the mouse. The one money number per screen sits on solid **sunflower** yellow, and
the screens people pass through — sign-in, empty and all-done states, the landing hero — are
flat yellow **moments** with drawn line-art illustrations. When FinBoy's AI is working, a dotted
**thinking orb** shows it. Everything is light theme, and violet is retired everywhere, the
logo included. Real-time WebGL remains only in the landing page's lower sections, on the same
field as the app (see *3D on the landing page*); the hero is a yellow moment.

The values below were measured from the reference images, not eyeballed; the measurements,
contrast findings and verification are recorded in
[`docs/handoffs/glass-theme.md`](handoffs/glass-theme.md). Product states and patterns are
specified in [`docs/ux-round/ui-spec.md`](ux-round/ui-spec.md).

## Principles

1. **Calm glass for the work, sunflower for the moments.** Glass and ink carry the money
   screens; yellow appears only as the hero number's card and as moments. Never put *frosted*
   glass over yellow: blurred yellow over the blue field turns muddy. Clear glass without blur
   (`lg-on-color`) may sit on a moment.
2. **Liquid Glass is the navigation layer.** It floats above content: the tab pill, the
   account button, the sidebar, the desktop toolbar, menus, sheets, dialogs and Ask's composer.
   On the app's wallpaper, content cards are widget glass (`surface`): clear, lit at the edges,
   but with no `backdrop-filter` — the wallpaper is soft, so a blur would only cost GPU.
   Content-layer controls look like glass (`lg-static`) and become real glass only while dragged
   (the lens). At most three blurred or refracting layers in view, in every state.
3. **Measured contrast.** Every text is ≥ 4.5:1 (large ≥ 3:1) and every form-control boundary
   ≥ 3:1 against its composited background, at the field's darkest point. The reference's own
   greys (3.97–4.29:1) and placeholder (2.68:1) fail; ours are darker.
4. **Numbers are sacred.** Tabular figures, `₹` with Indian grouping, never "bank balance".
5. **The orb means FinBoy's AI is working.** Data loading keeps the plain spinner.
6. **Everything degrades gracefully.** Refraction is Chromium-only (`refract` tier); Safari and
   Firefox get the same glass frosted (`frost`); no `backdrop-filter`, Reduce Transparency,
   Increase Contrast and forced colours get near-opaque glass (`solid`); reduced motion keeps
   every effect but its flex, stretch and overshoot. Each gives a legible screen.

## Tokens (`apps/web/src/app/globals.css`)

| Token | Value | Use |
| --- | --- | --- |
| `ink` / `ink-soft` / `ink-subtle` | `#0e1013` / `#474b52` / `#575b63` | Neutral text hierarchy; every step ≥ 4.5:1 on the field's darkest point and on glass over it |
| `field` · `field-cool` · `field-warm` | `#e1e3e6` · `#b9deeb` · `#e8d3b0` | The landing's and legal pages' ground and its two glows (measured from the reference); the landing's 3D recomputes it behind its glass |
| `wallpaper` · `wallpaper-sky` · `wallpaper-apricot` · `wallpaper-sun` | `#eef0f4` · `#b6ddf8` · `#f9d2b6` · `#ffdc70` | The app's wallpaper (`bg-wallpaper`): the glows grown into sky and apricot bands and a sun (`wallpaper-sun-at`, further out on phones). Its darkest point (luminance 0.676, where the bands meet) is lighter than the field's warm glow, so every ink token keeps ≥ 4.5:1 |
| `surface-tint` | .5 (Tinted .72; Increase Contrast .9; Reduce Transparency opaque `#ececee`) | White fill of the widget-glass cards on the wallpaper |
| `glass-fill` · `glass-rim` · `glass-edge` | `rgb(236 236 238 / .74)` · white 85% · white 55% | In-flow frosted glass, its lit top-left rim and edge |
| `well` | white 50% | A lighter well inside glass |
| `float-fill` · `glass-blur` | `rgb(250 250 251 / .74)` · `blur(24px) saturate(140%)` | Floating glass; the blur goes through the variable (see below) |
| `sunflower` / `sunflower-ink` | `#fed234` / `#3a2c00` | Hero and moment fill / secondary text on it (9.4:1). A fill under ink only: 1.18:1 as a line or text on glass |
| `positive` · `negative` · `warning` | `#065f46` · `#a8201a` · `#d97706` | Verified/income, destructive, attention (`warning` for icons/dots; attention text uses `amber-800/900`) |
| `wa-wallpaper` · `wa-bar` · `wa-out` · `wa-in` · `wa-text` · `wa-meta` · `wa-icon` · `wa-avatar` · `wa-accent` · `wa-button`; `font-wa` | `#efeae2` · white · `#d9fdd3` · white · `#111b21` · `#666666` · `#54656f` · `#dfe5e7` · `#1daa61` · `#1a8456`; Roboto, then the system UI font | WhatsApp's own light theme (Android), only where a WhatsApp chat is drawn (see *WhatsApp chats*). Sampled from Meta's Cloud API documentation screenshots. The greys pass AA as WhatsApp draws them (5.7:1 on white, 5.2:1 on the green bubble, 4.8:1 on the wallpaper); reply-button labels use WhatsApp's text green (4.7:1); the icon green `wa-accent` (3:1) only fills shapes |
| `wa-quote` · `wa-quote-name` · `wa-played` · `wa-field-edge`; `.wa-wallpaper` | `#d5f3cf` · `#876331` · `#53bdeb` · `#767676`; the beige under `chat-wallpaper.svg` at 280 px | A reply's quote of FinBoy's message (the name 4.55:1 on it), the played voice note's blue mic, and the amount field's outline (3.8:1 on the wallpaper, as any enabled field needs) |
| `lg-tint` · `lg-menu-tint` · `lg-thick-tint` · `lg-sidebar-tint` · `lg-static-tint` · `lg-composer-tint` | Clear .38 · .78 · .84 · .26 · .55 · .62; Tinted .70 · .92 · .95 · .64 · .72 · .86 | White fill of each Liquid Glass material (`app/liquid-glass.css`); Reduce Transparency .96–.99, Increase Contrast .9–.98 |
| `lg-sidebar-frost` | 8 px (`frost` tier 18 px; Tinted 16 · 24) | The sidebar's lighter frost: nothing scrolls under it, so it shows the wallpaper's colour like a macOS 26 sidebar |
| `lg-lit` (registered, not inherited) | 0–1 | How lit a card or the sidebar is by the mouse over it (GlassProvider) |
| `lg-prominent` | ink .86 (Tinted .94) | Tinted glass for primary actions |
| `lg-frost` · `lg-frost-fallback` | 2 px · 10 px (Tinted 10 · 18) | Frost after refraction, and the stronger frost that stands in for it in the `frost` tier (menus 12 · 20, thick 16 · 26) |
| `lg-edge` · `lg-rim` · `lg-spec` | ink 16% · white 60% · white 96% | iOS 27's darker outer edge, the inner bright ring and the specular arcs |
| `edge-cover-top` · `edge-cover-bottom` | .94 · .70 (Tinted bottom .86) | How much of the field covers content under the floating bars (scroll edge); the contrast checks read them |
| `ease-spring` | `linear(…)` spring, ≈ 4.6% overshoot over 0.5 s | Liquid Glass's gel: press flex, menus and sheets opening |

Shadcn variables map onto these: `--primary` is ink (black pills), `--card` is glass,
`--popover` is 90% white, `--secondary`/`--muted`/`--accent` are faint ink tints, `--input`
(form-control boundaries) is ink at 50% (≥ 3:1), `--ring` is ink. Radii follow the reference:
`lg` 12 px (rows, fields), `2xl` 20 px, `3xl` 24 px (panels), pills for actions.

**Brand:** the approved 28 October 2026 identity is the sunflower companion tile: an ink
lowercase **b** with a speech-bubble counter, paired with the outlined **FinBoy** wordmark.
`components/brand.tsx` uses the standalone SVGs in `public/brand/`; the same tile appears in
`app/icon.svg`, the ICO favicon, Apple touch icon and manifest icons. Use the ink wordmark on
glass, white and yellow; use the white wordmark on dark backgrounds. Flat fills only, with no
gradients or shadows in the logo. See [brand assets and usage](branding.md) for variants,
clear space and exports. The lavender `canvas`, the violet family (`violet`, `lilac`,
`magenta`, …) and the old landing palette are gone; `field` is deliberately not a Tailwind
colour, so the `bg-field` material never also paints a flat background.

**Keep `-webkit-backdrop-filter` and `backdrop-filter` behind a variable.** With literal values
the CSS minifier merges the pair into the `-webkit-` form only, which Chrome and Firefox ignore
— the previous `.glass` never blurred outside Safari. `theme.spec.ts` asserts the tab pill and
sidebar refract in Chromium and still blur with `?glass=frost`.

## Materials

| Class | What it is | Where |
| --- | --- | --- |
| `bg-field` | Fixed pseudo-element field + grain (never repaints on scroll; iOS ignores `background-attachment: fixed`) | App shell, session check, demo, 404, admin, legal pages, landing below the hero (with `isolation-auto`, so DOM marked `z-20` stays above the 3D layer) |
| `bg-wallpaper` (with `bg-field`) | Paints the wallpaper instead of the field (`--field-paint: var(--wallpaper-paint)`), so scroll edges and Ask's fade follow | App shell, the admin console and its sign-in, session checks, demo, 404 |
| `surface` | The content layer's standard material: in-flow frosted tint, 1 px white edge, inset top-left rim, Liquid Glass's faint dark edge, soft shadow; **no blur**. On the wallpaper it is **widget glass**: a clear white fill (`surface-tint`) the wallpaper shows through, a bright top-left catch and a softer bottom-right one, a glow inside the rim, a deep soft shadow, and the mouse's light | Cards, panels, rows |
| `glass` | Frosted floating glass: `float-fill` + `--glass-blur` (pre–Liquid Glass) | The admin panel's header and tab bar, chart tooltips |
| `float-panel` | Retired: dialogs and sheets are `lg-thick` over an unblurred dimming layer | — |
| `solid-hero` | Sunflower with ink and a soft warm shadow | The one money number per screen (Home's "Left this month", the demo, the landing simulator's estimate and the mosaic's overview tile) |
| `moment` | Flat sunflower with ink | Sign-in, empty and all-done states, landing hero |
| `field` | Glass field: 74% white with a soft top sheen, white inner rim, soft drop, 1 px `--input` edge (≥ 3:1); focus turns the edge ink with a soft ink halo | Every input, textarea and select |
| `composer` | `lg` refracting bubble with `field`'s 1 px ink edge, a deeper shadow and, on focus, an ink edge with a sunflower halo; 20 px radius | Ask's composer (the textarea carries the edge, so the boundary check still measures it) |
| `lg` | Liquid Glass (regular): clear white fill, specular rim, darker edge, lift shadow; refracts (Chromium) or frosts | Phone tab pill and account button, landing nav after the hero, Ask's composer, the drag lens |
| `lg-menu` | Thicker glass for dense text | Dropdown and Select menus |
| `lg-thick` (+ `lg-sidebar`) | Large glass: deeper shadow, softer scattering, no light/dark flip | Dialogs, alert dialogs, sheets (inset 8 px, 32 px corners on phones), the desktop sidebar |
| `lg-prominent` | Ink-tinted glass, lit from within | Primary buttons, the phone +, Add entry, the landing's Start links |
| `lg-static` | The glass look without a backdrop filter | Content-layer glass: `glass`/`outline` buttons, segmented tracks, the back button, landing chips |
| `lg-on-color` | Clear glass on yellow (never blurred), warm shadow | Sign-in panels, the hero's secondary action, the landing nav over the hero |
| `lg-platter` · `lg-knob` | The selected item's inset well · a raised glass knob | Tab bar and sidebar selection · segmented controls and the hero's chevron capsule |
| `lg-hover` | A bright glass pill under the mouse that glides from item to item | The desktop sidebar |
| `page-actions` (with `lg` on desktop) | A page's actions; on desktop a floating, refracting toolbar capsule at the content column's top right that the page scrolls beneath (`PageActions` measures it, and the title and offline banner keep clear) | Every `PageHeader` with actions |
| `scroll-edge` | Fixed, unblurred copy of the field masked to the screen's edges | Under the phone bars, desktop's toolbar row and the landing nav (Apple's scroll edge effect) |

Inside yellow, use white tints (`bg-white/55`) or `lg-on-color`, never frosted glass. Fallbacks
(unlayered, so they win over utilities): no `backdrop-filter` → near-opaque glass; **Reduce
Transparency** → `--glass-blur: none` (also on `backdrop-blur-*`), no Liquid Glass backdrop,
opaque surfaces, flat field and edges; **Increase Contrast** → darker secondary ink, 45% ink
edges, 75% ink control boundaries, solid Liquid Glass with a 60% ink edge; **forced colours** →
`CanvasText` borders on every material and `Highlight` on the selection.

### How Liquid Glass is drawn (`components/liquid-glass`, `lib/liquid-glass`)

- `useLiquidGlass()` measures its element, builds a displacement map for its size and corner
  radius (`maps.ts`: a rounded-box SDF, a convex-squircle bezel and Snell's law at n = 1.5;
  offsets always point inward, so the filter never samples outside the element), caches it as a
  PNG data URL and sets `--lg-refract: url(#…)` and `data-lg-refract`. The material puts the
  filter ahead of its frost, saturation and brightness. Lenses add magnification and a
  three-pass colour split. Chromium measures filters in CSS pixels at every DPR.
- `GlassProvider` (root layout) picks the tier after hydration (`tier.ts`), follows the
  accessibility media queries, drops to `frost` for the session if scrolling stays janky, and
  writes `--lg-x/--lg-y` and `data-pressed` for the press glow. Under a mouse (fine pointer, no
  reduced motion) it also lights the card or sidebar beneath the pointer: `--lg-x/--lg-y` and
  `--lg-lit` (registered and not inherited, so nested glass stays unlit) drive a soft light in
  the material's background, once per frame; scrolling lets it fade. The saved Clear · Tinted look is
  applied before first paint by an inline `<head>` script.
- Glass with a backdrop filter is its children's *backdrop root*: render a lens or any other
  glass **beside** it, never inside, or it will only see its parent's own layer.
- Pass the hook's `attach` as the element's ref and render its `filter` anywhere; destructure
  the result (the React Compiler treats an object whose member is a ref as a ref).

## Type

Plus Jakarta Sans Variable (the closest loaded match to the reference's geometric sans) with
Anek Malayalam Variable as the Malayalam fallback; Hindi uses the system Devanagari font. Page
titles weight 500 at −0.025em (28/32 px); month headings 20 px/500; record names 14 px/600;
amounts 15 px/600 tabular. Yellow moments use weight 800 headlines at −0.045em (the
reference's welcome screen). Mark language on text: `lang="ml"`/`"hi"` for native script and
`ml-Latn`/`hi-Latn` for romanized replies.

## App screens

- **One page header** (`components/app-shell/page-header.tsx`): direct task title, one sentence
  of support, actions on the right — on desktop in a floating Liquid Glass toolbar capsule
  (`PageActions`) that the page scrolls beneath, as toolbar items float in iPadOS and macOS 26.
  Screens reached from another one (Import results) pass `back` for the reference's glass
  square back button; top-level tabs never do.
- **Navigation:** four tabs — Home, Transactions, Reports, Ask. Desktop: an inset Liquid Glass
  sidebar (`lg-thick lg-sidebar`, clearer than other thick glass, so it carries the wallpaper's
  colour) with the tinted-glass **Add entry** pill, the tabs (the selected one in ink on a light
  platter, and a bright highlight gliding under the mouse) and an account button at its foot. Phones: no bar behind the
  wordmark — content dissolves under the top scroll edge once scrolled — and a 44 px glass
  account circle; at the bottom a floating clear-glass tab pill (ink icon and label on the
  platter for the selected tab, every other tab labelled in secondary ink) with a round
  tinted-glass **+** beside it. Press and slide across the pill and a magnifying lens follows
  the finger; releasing on a tab opens it (through its link, so unsaved-work guards still ask).
  Content-sized cells keep "Transactions" readable at 320 px. Sources, Privacy & data,
  shortcuts, the **Glass** look (Clear · Tinted) and sign-out are in the account menu. Phone page
  margins are 24 px from 390 px up, 16 px below.
- **Home:** the sunflower hero — "Left this month", then Money in, Money out and Bills due on
  white tints, and "How is this worked out?" folding the calculation away — then one row of
  amber attention chips (only when something needs a look), Bills due and a budgets snapshot.
- **Reports:** three stat tiles (spent against the month before, money in, daily average), the
  spending donut with its legend table, six months of money in and out as columns, and the
  budget meters with the savings goal. See **Charts**. For a range of months (statement round)
  the first tile reads "Confirmed spending over 6 months" and the columns show the range's own
  months; below them come Who you pay most, then Regular payments, Money with people and Small
  payments stacked beside it on wide screens, each a `surface` card that appears only with data.
  A glass callout with **Sort payees** appears when more than 20% of spending is "Other".
- **Ask:** a chat in one centred column (≤ 768 px): a greeting under the resting orb and
  suggestion chips; then questions as right-aligned glass bubbles and answers beside FinBoy's
  mark, without a box. The **composer** docks at the bottom (above the phone tab pill); a new
  question or a followed answer scrolls to the page's end, which always clears the dock, and the
  conversation fades into the field beneath it (`.ask-fade`: a fixed, unblurred copy of the
  field's paint masked to the bottom band, so it adds no blurred layer).
- **Records:** each record is a glass card (12 px radius, 8 px apart) with a circular glyph;
  Transactions groups them under IST month headings; the "how it counts" line sits under the
  details on phones and under the amount on wider screens (one element, placed by the grid).
  Transactions and Review are two tabs of one place (**All** · **To review** with its count, a
  glass segmented control). Filters: a search field and a filter button that folds the five
  selects away and shows how many are on.
- **Feedback:** `ProblemNotice`, `LoadingPanel`, `RefreshingLabel` (spinner), amber
  attention strips. Successes are polite live regions; failures are alerts.

## Yellow moments

`EmptyState` always renders a moment with an illustration (first on phones, beside the text
on wider screens): no records yet, nothing matches, all reviewed, an empty month. Sign-in is
a full-page moment (logo and ink wordmark, 2 px ink-bordered field, black pill whose chevron
capsule is decoration — never a swipe) with a sunflower `themeColor`; the landing hero is the
same moment with the existing headline and CTAs. Ask's greeting is not a moment: it sits on the
field like the rest of the chat, under the resting orb.

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
| Ask's greeting | breathing · 64, rests after 5 s |
| Answer pending (in FinBoy's avatar, beside the shimmering "Thinking…") | searching · 20 |
| Transcribing a recording (never while recording: the real mic level is the honest signal) | listening · 20 |
| Preparing a spoken answer | composing · 20 |
| Import running; Sources' link to it | working · 64 / 20 |
| Sign-in and landing-hero illustration (FinBoy's reply bubble) | composing · 20, rests after 5 s |

## Illustrations (`components/illustrations/`)

`kit.tsx` draws on 240-unit artboards: 2.5-unit strokes in `currentColor` (forced colours
adapt), round caps and joins, white fills, sunflower as the only colour fill (except inside a
drawn WhatsApp chat, below), halftone shading
from a 4.5-unit dot grid (the orbs' dot language), four-point sparkles and "pop" lines, and
the ₹ coin as a currency illustration (separate from the companion logo). Patterns and clip
paths use per-instance
`useSvgId()`: a shared id breaks when a copy sits in a hidden subtree. Scenes (`scenes.tsx`,
each well under 6 KB, decorative): `MoneyScene` (sign-in, landing hero), `NoRecordsArt`,
`NoMatchArt`, `AllReviewedArt`, `EmptyMonthArt`. Brand assets supplied later replace these
defaults where they conflict.

### WhatsApp chats

Where FinBoy shows its WhatsApp chat, it looks like WhatsApp for Android in light mode, in the
`wa-*` tokens (human's choice, 10 November 2026):
- **The landing's How it works chat** (`marketing/chat-preview.tsx`, with its parts in
  `marketing/chat/`) is a live demo. It plays FinBoy's real replies from `english.py`, in the
  flows of `pilot.py`, as plain lines with no bold. It has:
  - a rounded screen with a soft shadow (no bezel);
  - WhatsApp's top bar, with FinBoy's photo cropped round and "typing…" before each reply;
  - FinBoy's own doodle wallpaper (`public/brand/chat-wallpaper.svg`, Lucide shapes laid out by
    `scripts/chat-wallpaper.mjs`; WhatsApp's doodle art and tail assets are not copied);
  - bubbles with tails on the first of each run, and grey "delivered" ticks (FinBoy sends no read
    receipts);
  - reply buttons inside the bubble under a hairline, each with the reply arrow (a tapped one greys
    out), and list buttons that open WhatsApp's bottom sheet;
  - two playable voice notes, each with its knob, played bars and time. Yours ("Paid the milkman
    500", Sarvam Bulbul v3) shows its transcript; FinBoy's spoken reply ("Saved, 500 rupees paid,
    milkman.") is in its production voice. Both are AI-made.
  - the message bar, with the green mic, which becomes a real field after ✏️ Amount.

  Visitors can tap Undo all, Fix one, Undo, Put it back, Amount (typing the new amount) and
  Category (the list). Each tap gets FinBoy's own reply, including "This record has already
  changed" for a stale card. The script is pure (`lib/chat-demo/script.ts`). It runs only in the
  browser and sends nothing.

  The opening chat renders on the server. From the first tap the phone keeps its height and
  scrolls inside, with no smooth scroll under reduced motion. "Start again" in FinBoy's caption
  restores it.

  For accessibility:
  - controls are real buttons;
  - the list sheet is a modal dialog that keeps focus and hands it back;
  - new messages are announced;
  - the amount field has a ≥3:1 outline.

  `lib/chat-demo/finboy-copy.json` pins every text: `script.test.ts` checks the ports against it,
  and the API's `tests/whatsapp/test_landing_chat.py` rebuilds it from `english.py`.
- **`MoneyScene`'s phone** keeps the line art, but its chat is WhatsApp's: a white top bar,
  the wallpaper, your voice note in the green bubble with the green knob, white replies with
  tails, a reply-button row and the green mic. The receipt, envelope and coin keep sunflower.
- The "…on WhatsApp" buttons and links stay FinBoy's ink.

## Primitives (`components/ui`)

- **Button** — `default` (tinted ink glass, `lg-prominent`, primary action), `glass` and
  `outline` (clear glass in the content layer, `lg-static`), `secondary` (ink tint), `ghost`,
  `destructive`, `link`. The three glass variants carry `data-glass-press`: they flex (scale
  1.06 on a spring) and light up from the press point. Sizes `sm` 36 px, `default` 44 px, `lg`
  48 px, `icon*`. Pills everywhere.
- **Card** — `surface`, 24 px radius. **Badge** — `default` (ink tint), `solid`, `positive`,
  `warning`, `outline`, `destructive`. **Input / Textarea / Select** — the `field` material
  (below), 12 px radius; native selects add `field-select` (a drawn chevron; forced colours get
  the platform arrow back).
- **Dialog / AlertDialog / Sheet** — refracting `lg-thick` glass (28 px corners; sheets inset
  8 px with 32 px corners on phones) over an unblurred ink 25% dimming layer, springing in;
  custom Radix dialogs use the same classes. **DropdownMenu / Select content** — refracting
  `lg-menu` glass that pops open from its control. While any of them is open, floating chrome
  turns solid. **Switch** (unused) — ink track, white thumb.

## Charts (`components/charts`, `lib/charts.ts`)

Plain SVG and HTML, no chart library, built to the dataviz method: the form first, then colour,
validated with its `validate_palette.js` against glass at the field's warmest point (#ebe6de).

- **Donut** (part-to-whole): the five largest spending categories plus "Everything else" in grey
  (≤ 6 slices, 2 px apart), on one amber ramp `--chart-1` … `--chart-5` (#2e2200 → #c49400,
  darkest for the largest; few slices spread across the ramp). It sweeps in clockwise; hovering
  or tapping a slice (or focusing its row) puts it in the centre readout. The legend is a real
  table — every category with amount and share, each a link to its records — so the drawing is
  hidden from screen readers. Net refunds are listed, never drawn.
- **Columns** (money in and out by month): `--chart-in` blue #2a78d6 and `--chart-out` amber
  #b87800 on one ₹ axis with Indian compact ticks (₹10K, ₹1.2L), thin bars with 4 px rounded
  tops growing from the baseline, the chosen month full strength and the rest receding, a glass
  tooltip per month, and **Show as table** (the table is always there for screen readers).
  Amber is 2.95:1 on glass, so the legend and table are required, not optional.
- **Meters** (budgets): the same-ramp track with a status fill (green under 80%, amber from 80%,
  red over), always with "₹X left" or "₹X over" in words.
- **Payee bars** (who you pay, who pays you): a table of names with a thin 6 px bar under each,
  scaled to the largest, in `--chart-out` for payments and `--chart-in` for money received (one
  series per table, so the heading names it and no legend is needed); amount, share and count
  are text in ink. Regular payments, money with people and small payments are lists with figures
  in words, not charts. Sort payees uses the existing progress meter for "how much is sorted".
- Chart text stays in ink tokens, never series colours; reveals are CSS (`animate-sweep`,
  `animate-grow-y`, `animate-grow-x`), so reduced motion shows the finished chart.

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
| `AppMotion` | `MotionConfig reducedMotion="user"` around the app shell, so springs and layout moves (the nav capsule, the Transactions tabs, Ask's composer gliding to its dock) honour reduced motion. |
| `.word-in`, `.shimmer-text` | An answer arriving word by word (≤ about 0.9 s), and the light sweeping through "Thinking…" (its colour stays ink-soft for contrast). |
| Liquid Glass materialize | Refraction ramps in (displacement scale 0 → full over 420 ms) when glass appears or the landing nav leaves the hero; reduced motion sets it at once. |
| Press (`data-glass-press`, glass links and buttons) | Scale 1.06 on `--ease-spring` and a glow from the press point; reduced motion keeps the glow only. |
| Selection platter, segmented knob | `layoutId` spring (stiffness 420, damping 30) between items. |
| Sidebar highlight (`lg-hover`) | Glides under the mouse on a spring (520/38), appearing in place on the first item it reaches and fading out when the mouse leaves; reduced motion moves it without the glide. |
| Pointer light | Cards and the sidebar brighten where the mouse is and fade in 0.5 s (`--lg-lit`); off for touch and reduced motion. |
| Drag lens (`selection-lens.tsx`) | Follows the finger on a spring (650/40), stretches with its speed (scaleX ≤ 1.22), magnifies 1.28×; under reduced motion it moves straight and never stretches. |
| Menus, dialogs, sheets | Open on `--ease-spring` (300 ms menus and dialogs, 500 ms sheets) from their source; close in 150–200 ms. |

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

Below the yellow hero the landing sits on the app's field (`main.bg-field.isolation-auto`) with
the app's materials: glass cards, ink-soft eyebrows, ink icons and chips, the simulator's
estimate on `solid-hero`, and no violet. Its scenes are re-toned to the same world.

- **Use 3D only through `<SceneSlot spec={...} className="h-72" />`** with `<SceneLayerMount />`
  mounted once per page that has slots (today only the landing page). Daily screens ship no
  three.js (audit F35); thinking orbs are 2D canvases, not WebGL. Add 3D to an app screen only
  when it carries task state and has a phone-tested budget.
- Slots render **above** DOM (canvas `z-10`); DOM that must overlap a scene needs `relative z-20`
  (the final call to action's text does). That is why the landing's `main` is not isolated: an
  isolated `bg-field` would trap `z-20` DOM below the canvas.
- Scenes: `ribbon`, the final call to action's only one. The voice demo's glass orb was removed
  on 11 November 2026, with the field shader, tone mapping and glass material only it used.
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
- **Palette:** the glass world in 3D. Money objects are sunflower (`createSunflower`: half metal
  under a clear lacquer — a full metal mirrors the dark cove and reads as brass); decisions and
  committed money are lacquered ink (`createInk`: the verification dome, the simulator's
  committed columns — the black pills in 3D); slabs are pearl (`createSatinAcrylic`, the inbox
  tray); glass is neutral-cool; contact shadows and drawn rings are ink. No violet or magenta.
  The voice orb's four states stay distinct in value and hue: idle pale cool (the field's cool
  glow), listening vivid cool, thinking ink (as the app's thinking orbs), speaking sunflower.
- **Rendering:** linear workflow with Khronos Neutral tone mapping on the renderer; the GLSL
  `preToneMapped()` (`lib/tone.ts`) lands a rendered colour exactly on a CSS colour. Light is image-based from `ProductStudioEnvironment`: `tone="dark"` (an ink cove for
  coins and the ink dome) or `"light"` (a field-grey cove for glass and pearl), with the field's
  glows as gels — cool from the left and below, warm from the right. Materials:
  `lib/materials.ts`.
- **Glass over the field:** the field is fixed to the viewport, so what sits behind a scene
  changes as the page scrolls, and a flat backdrop colour would show as a disc. The voice orb's
  refraction backdrop and its core's feathered edge paint `fieldBehind()` (`lib/field.ts`): the
  `.bg-field` gradient and the grain's average recomputed per fragment from the slot's rectangle
  (`useFieldUniforms(track)`; `SceneView` passes the slot element), with colours read from the
  CSS tokens and the glows dropped under Reduce Transparency, as the CSS does. Inside and just
  outside the sphere now agree within a few levels (before: a disc 15 levels darker). Keep the
  shader in step with `.bg-field` (positions, radii, stops, grain). Other scenes are transparent
  and composite over the DOM, so they need no matching.
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
| Blurred layers | ≤ 3 blurred or refracting layers in view on every route and state (`theme.spec.ts`); an open overlay makes floating chrome solid |
| Refraction | Chromium only; maps cached per size (≤ 40), half resolution above 120 000 px²; the jank guard drops to `frost` when p90 frame time stays above 22 ms while scrolling |
| Scroll frame time | 230-record list, CPU 4×: p95 16.7–16.8 ms, max 16.8 ms on desktop and phones — unchanged by Liquid Glass in every tier (one 33 ms frame with refraction pinned at 390 px) (`perf.spec.ts`, 6 Nov 2026) |
| Initial JS, gzip | ≤ 280 KB, no three.js; thinking orbs add ≈ 7.4 KB |
| Lazy 3D JS | three + R3F/drei/scenes, after first paint; the hero canvas and `postprocessing` (≈ 89 KB) are gone |
| Device pixel ratio | adapts within 1–1.75 (high), 0.9–1.5 (medium), 0.75–1.25 (low), capped by the screen |

CPU throttling doesn't model a budget phone's GPU, where blur costs most: that is why blur is
capped and kept off in-flow cards. Real-device checks are listed in the handoff.

## Verification

`pnpm check` (including the Liquid Glass unit tests in `lib/liquid-glass/*.test.ts`),
`pnpm build`, `pnpm test:e2e` (1440×1000, 390×844, 320×740), which includes `theme.spec.ts`:
rendered contrast for text, placeholders and form-control boundaries on every route and moment
(under floating bars, against ink dissolved by the scroll edge), the blur budget, real
refraction in Chromium (materialized), `?glass=frost` without `url()`, the Tinted look,
Reduce Transparency / Increase Contrast / forced-colours fallbacks, and the orbs' theme pin,
accessibility and resting; and `layout.spec.ts`: navigation-label contrast on the glass and
platter, the drag lens and the remembered Glass choice. Opt-in: `E2E_CAPTURE_DIR=<dir>`
(`capture.spec.ts`) screenshots every route and state for a before/after review; `E2E_PERF=1`
(`perf.spec.ts`, `E2E_GLASS=refract|frost|solid` to pin a tier) measures scroll frame times.
QA in a browser: `?glass=refract|frost|solid` holds a tier for the tab's session, `?glass=auto`
clears it.
