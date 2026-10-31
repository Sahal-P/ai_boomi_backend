# UI refresh round — contract (31 October 2026)

A calmer household web app: fewer tabs, glass fields, expense reports and a chat-style Ask. It
changes `apps/web` only; the API, its contract and the database are unchanged. It supersedes
earlier UI statements only where it says so:
- the six-destination navigation and five-tab phone bar ([product UI](../product-ui.md),
  [design system](../design-system.md));
- the Overview layout with its action tiles and "What if" simulator;
- Ask's form layout and its yellow empty-state moment.

## Human decisions (31 October 2026)

- **Fewer tabs:** Privacy and Review leave the main navigation; Review becomes a tab inside
  Transactions; anything that overwhelms people goes.
- **Reports:** conventional expense reports (a pie chart and the like) in the current theme, in
  their own **Reports** tab.
- **Add from anywhere:** a + on every screen opens quick add.
- **Fields:** premium glass "bubble" inputs with a slightly smaller radius.
- **Ask:** laid out and animated like Gemini's chat, in FinBoy's theme.
- **Where it lives:** branch `feat/finboy-ui-refresh` from main `a09d1bd`; loopback web 3061 with
  API 8061 on disposable `finboy_signup`; no migration.

## What changed

| Area | Before | Now |
| --- | --- | --- |
| Navigation | Overview, Transactions, Review, Ask, Sources, Privacy | Home, Transactions (All · To review), Reports, Ask; Sources, Privacy & data, shortcuts and sign-out in the account menu |
| Adding an entry | Overview's Add button | Sidebar **Add entry** and a round **+** beside the phone tab pill, one sheet for the whole app |
| Home | Estimate and calculation table, four action tiles, exceptions grid, categories, budgets, obligations, simulator | "Left this month" with money in, money out and bills due; the calculation on request; attention chips only when needed; bills; a budgets snapshot |
| Reports | — | Spent (against the month before), money in, daily average; a spending donut with its table; six months of money in and out; budgets and the savings goal |
| Ask | Form, reply-style select, separate recording row, newest-first cards | Greeting and suggestions, then a conversation oldest-first; a docked glass composer with the reply style, mic and Ask/Stop; answers revealed word by word |
| Fields | Mixed radii and flat white | One `field` material (12 px), the Ask composer at 16 px |
| Words | "Estimated unallocated", "Confirmed net outflows", "obligation", "your estimate", "your overview" | "Left", "Money out", "bill", "what's left", "Home" — on Home, bills, merges, import results and error pages |

- **Removed:** Overview's action tiles, the "What if" simulator (Ask answers "Can I set aside
  ₹5,000 each month?" with the same engine, and it is a suggestion), the email-scan lines on
  Home (Sources keeps coverage), the always-open filter panel (a Filters button with a count),
  and Ask's help box, footnotes and "You asked · reply style" labels. An answer's supporting
  records fold under its "Supporting records" line until opened.
- **Changed from the plan:** Reports' third figure is a daily average (the savings goal already
  shows what is kept, in the budgets card); native selects take the `field field-select` classes
  instead of a new component; and the filters fold behind a **Filters** button at every width.
- **Kept:** every route, deep link (`?selected=`), the review queue and its shortcuts, the
  household's records and decisions, Ask's localized labels, `lang` marking, voice rules (nothing
  recorded is sent until you press Ask) and the no-storage rule for questions and answers.

## Rules that still hold

Measured by `e2e/theme.spec.ts` and described in the [design system](../design-system.md): text
≥ 4.5:1, form-control boundaries ≥ 3:1, at most three blurred layers in view, no glass over
yellow, the orb only while FinBoy's AI works, and reduced motion honoured without branching what
is rendered (CSS reveals, `MotionConfig reducedMotion="user"`).

## Charts

Built to the dataviz method and validated with its palette script against glass at the field's
warmest point (#ebe6de): the donut's amber ramp passes as an ordinal ramp (light end 2.23:1),
and money in (blue #2a78d6) and money out (amber #b87800) pass the categorical checks with amber
at 2.95:1, so every chart has a legend and a table. Reports reads six monthly summaries from the
existing API; a trend endpoint can replace them later if it gets slow. It derives display-only
figures from the API's totals (shares, the "Everything else" slice, the change against the month
before and the daily average); none is saved, sent or used in a decision.

## Verification

Recorded in the round's final report: `pnpm check`, `pnpm build`, `pnpm test:e2e` (desktop,
390 px and 320 px) and a browser pass against the disposable database at desktop and 375 px.
