# Admin growth — contract (24 November 2026)

The admin panel gets a **Growth** page at `/admin/growth`, second in the navigation. It shows how
self-serve households join, stay and use FinBoy over time, built from the admin panel's existing
look. There is no migration, no flag and no new dependency.

## What counts

- **Who:** self-serve households that agreed (`joined_via` and `consented_at` set). The owner and
  the village pilot are left out.
- **Active:** on a day a household sent FinBoy a WhatsApp message (`whatsapp_receipts`) or saved a
  record (`transactions.created_at`, in any state). These are the overview's two signals.
  Activity counts from the day a household agreed. FinBoy keeps no page views, so web visits that
  save nothing are not seen.
- **Records saved:** confirmed or waiting for a check, counted, never their amounts.
- **Dates:** IST days; weeks start on Monday; months are calendar months.
- **Erased households** count as joined, then left. Their activity was erased with them, so they
  count as not active.

## Periods

- **30 days by day** is the default; **12 weeks by week** and **12 months by month** are the others.
  The choice is kept in the URL as `?period=`.
- The running day, week or month is counted so far, and says so.
- Periods before the first self-serve household agreed are left out.
- **New households** is compared with the same length of time just before.
- **The retention grid** groups households by the week they agreed, or by the month for 12 months.

## The page

- Four stat tiles: new households, households now, active in the last 7 days and made a first
  record.
- **Households:** a line chart of all households and active ones.
- **New households** and **Records saved:** column charts.
- **From page to first record:** the funnel of page visits in the period (`visits.funnel`, added
  up), with sign-ups that came with no visit kept apart.
- **Coming back:** the retention grid.

Every chart has "Show as table", and its table is always there for screen readers.

**Colours:**
- Blue `--chart-in` and amber `--chart-out` for the two lines. Amber is 2.95:1 on glass, so the
  end labels and table views carry its values.
- A new blue ramp, `--chart-seq-1` to `--chart-seq-7`:
  - The funnel uses steps 3–7, which pass as an ordinal ramp with the light end at 2.02:1.
  - The grid uses all seven, with ink text on steps 1–4 and white on 5–7.

## API

`GET /api/v1/admin/growth?period=30d|12w|12m` answers `services/admin/views.Growth`.
- It needs an admin session, is `no-store` and returns 422 for any other period.
- It reads at most 50,000 (household, day) pairs, newest first. That fits 100 households over a
  whole year.
- `services/admin/growth.py` keeps the arithmetic in a pure `assemble()`, and turns stored times
  into IST days with PostgreSQL's `timezone('Asia/Kolkata', …)`.

## Privacy

Counts and calendar days only: never an amount, payee, category, name, number or message. The
existing response-model test covers the new models.

## Release

1. The ad journey release goes first, because the funnel reads its `signup_visits`.
2. Then the advisor edits release.
3. Then this backend.
4. Then push main for the web.
