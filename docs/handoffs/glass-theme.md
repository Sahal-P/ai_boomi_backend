# Glass theme round — handoff (27 Oct 2026)

Branch `feat/finboy-glass-theme` from `main` at `ec4ed7b`, in the worktree
`.claude/worktrees/glass-theme` (inside the repository folder, git-excluded, so its files open
in the desktop app; the plan named `../ai_boom-glass-theme`). Loopback ports: web 3061, the
test-only contract double 8061 (HTTPS with a temporary private certificate), Playwright 3062.
No database, no API change, nothing pushed or deployed.

## What changed

The whole web app moved from "light, 3D, premium" (lavender canvas, white cards, violet
accent, dark estimate card) to the glass reference, with the human's choices:

- **Direction B:** glass and black pills everywhere; the one money number per screen on solid
  sunflower; violet only as the wordmark.
- **Yellow moments** with drawn line art: sign-in, every empty and all-done state, Ask's empty
  state, and the landing hero (which replaces the WebGL hero).
- **Illustrations** drawn in SVG (no mascot), swap-ready for commissioned art.
- **Tab bar** in the reference's shape with every label kept.
- **Thinking orbs** where FinBoy's AI is working.

Details live in `docs/design-system.md`; behaviour, copy and API use are unchanged apart from
layout. Removed: the WebGL hero (`marketing/hero-stage.tsx`, `three/hero/*`), its two orphaned
helpers (`lib/soft-shadows.ts`, `lib/textures.ts`), `HeroSkyEnvironment`, and the hero-only
packages `postprocessing`, `@react-three/postprocessing` and `maath` (all in git history).
Added: `thinking-orbs@0.3.1`.

## Measured against the reference (1.24 px per pt)

| Element | Reference | FinBoy at 393 pt |
| --- | --- | --- |
| Page margin | 24 | 24 (16 below 390 px) |
| Gap between rows | ~9 | 8 |
| Row radius | ~10 | 12 |
| Avatar / glyph | 42 | 40 |
| Search height / radius | 47 / ~10 | 48 / 12 |
| Month heading | ~21 regular | 20 / 500 |
| Name / amount | 14 / 15 | 14 / 15 |
| Floating nav height | 60 | 62 |
| Row height | 66 | 112–146 — intentional: FinBoy rows carry kind, category, date, review reason, status, sources and how the record counts |
| Nav active item | 60 pt black circle + label, icon-only others | 48 px black capsule, every tab labelled (fits 320 px; text-plus-icons rule) |

Contrast found in the reference and fixed here: its secondary greys measure 3.97–4.29:1 and its
search placeholder 2.68:1 (WCAG minimum 4.5:1); FinBoy's own green fell to 4.48:1 on that glass
(now `#065f46`, 6.27:1) and yellow is 1.18:1 as a line, so it is used only as a fill under ink.

## Verification (commands and outcomes)

- `env -u WEB_APP_URL DATABASE_URL=postgresql+psycopg://…@127.0.0.1:5433/finboy_glass_unit_none pnpm check`
  → exit 0: Ruff clean, 869 API unit tests passed (59 integration deselected), 41 web unit
  tests passed, typecheck clean. The worktree has no `.env` (gitignored), so the API unit tests
  need a `DATABASE_URL` string; they never connect, and the name points at no database.
- `pnpm build` → exit 0.
- `E2E_PORT=3062 pnpm test:e2e` → 202 passed, 0 failed, 116 skipped (the opt-in capture and
  live-API specs, and checks that run at one width only). Behaviour assertions are unchanged;
  two styling assumptions were updated: the tab-bar contrast check measures the active label on
  its ink capsule, and the no-WebGL check ignores the 2D orb canvases.
- `theme.spec.ts` (new, part of the suite) found three real problems, all fixed:
  1. **Glass never blurred outside Safari, already in production.** With literal values the
     CSS minifier merged `backdrop-filter` and `-webkit-backdrop-filter` into the prefixed form
     only, which Chrome 152 and Firefox ignore. The blur now goes through `--glass-blur`, and a
     check asserts real blur in Chromium.
  2. Ask's textarea used the browser's default placeholder grey (< 4.5:1).
  3. Record rows rendered the "how it counts" line twice (one per breakpoint); it is now one
     element placed by the grid.
- Performance (`E2E_PERF=1`, 230-record list, CPU 4×, scripted scroll, three runs per width),
  `main` vs this branch: desktop and phone-390 both p95 16.7–16.8 ms, max 16.8 ms — no change.
- Visual review: `capture.spec.ts` before/after sets (75 screenshots each) and a
  reference-versus-FinBoy sheet at 390 pt (Transactions, Card details ↔ Overview, Welcome ↔
  Sign in); browser checks of the overview, transactions, Ask, sign-in and landing pages at
  1440 and 375/393 in the dev preview.

## Not verified — do not claim

- **iOS Safari (WebKit).** The iOS Simulator panel was refused: device access was not granted
  in the app. Safari's `-webkit-backdrop-filter`, the canvas orbs and the fixed field are
  unchecked on WebKit.
- **A real budget Android phone.** CPU throttling doesn't model a phone GPU, where blur costs
  most; blur is capped at three layers and kept off in-flow cards for that reason.
- **Reference source values.** No Figma/Dribbble source was available; all values come from
  measuring the two images.
- **Comprehension with real people.** Run the script below when you can.
- **Brand assets.** None arrived; illustrations use the repo's ₹ mark and the measured palette.
  Swap points: `components/illustrations/scenes.tsx` (scenes), `kit.tsx` (coin, palette),
  `components/brand.tsx` (mark).
- `live.spec.ts` (real API on a disposable database) was not run: no API or contract change.

## 5-second test script (3–5 people, about 10 minutes each)

Show each person a phone with one screen for five seconds, hide it, then ask. Alternate old
(`main`) and new (this branch) between people; never explain the screen first.

1. Overview: "How much money is left this month?" and "Is anything waiting for you?"
2. Transactions: "Which record wasn't counted, and why?"
3. Review (empty ledger): "What should you do here?"
4. Sign-in: "What is this app for?"

Record each answer verbatim, whether it is right, and the time to answer. Watch for misreading
the estimate as a bank balance, missing the review count, and anyone who can't read the
secondary text in daylight.

## Follow-ups (not in this round)

- Re-tone the landing page's remaining 3D scenes to the glass field (their backdrops are
  tone-matched to the lavender `--canvas`, so it stays for now).
- A Devanagari web font (Hindi uses the system font).
- Yellow treatment for `/demo` and the 404 page; dark mode.
