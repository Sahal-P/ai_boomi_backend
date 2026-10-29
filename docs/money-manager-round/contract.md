# Money manager round — contract (29 October 2026)

This contract supersedes earlier statements only where it says so. For WhatsApp diary households
(village pilot and self-serve), three statements give way:
- "nothing counts until a tap" ([pilot contract](../pilot/contract.md), [sign-up
  contract](../signup-round/contract.md));
- "every screenshot-only event still requires review" (AGENTS.md, WhatsApp production activation);
- "List/flow replies are not used by FinBoy".

Everything else in those contracts still binds. The owner's web app and WhatsApp question flow are
unchanged unless the owner's pilot flag is set.

## Human decisions (29 October 2026)

- **Saving:** save at once, ask only when unsure.
- **CFO:** budgets with warnings, a monthly summary, an opt-in monthly check-in message and a
  savings goal.
- **Email:** later; Gmail stays invite-only.
- **Languages:** English, Hindi and Malayalam.
- **Design:** keep the current design and theme.
- **Where it lives:**
  - branch `feat/finboy-money-manager` from main `1c724a4`;
  - loopback API 8061 and web 3061, disposable database `finboy_signup`;
  - one additive migration, `0011_money_manager`.

## What people get on WhatsApp

**Saved at once.** Text, several items in one message ("chai 20, auto 50, lunch 120"), a voice
note, a UPI screenshot, a photo of a bill or receipt, or a pasted bank SMS each go through the
import pipeline as before, and FinBoy then confirms the record with a versioned decision, exactly
like quick add's Save:
- one entry: "✅ Saved: ₹500 paid · Groceries · milkman · Today", the budget it counts against,
  and [↩️ Undo] [✏️ Amount] [🏷️ Category];
- several: "✅ Saved 3 · ₹190", one line each, with [↩️ Undo all] [✏️ Fix one]. Fix one opens a
  WhatsApp list of the items.

**Asked first only when unsure.** The confirm card ("Is this right?") comes first, and nothing
counts until ✅ Yes, when:
- the amount is ₹50,000 or more;
- the pipeline marked it a possible duplicate;
- a typed or spoken entry matches a screenshot, bill, SMS or email record of the same amount and
  direction within two days ("This looks like one you already added");
- as before: no amount, or no direction.

In a message of several items, unsure items are left waiting for review and listed under "⚠️ Not
added yet"; Fix one opens their check card.

**Undo, Put back, Amount, Category.**
- Undo takes the entry out (a reject decision) and offers [↩️ Put it back], which reopens and
  confirms it again (a rejected record cannot be confirmed directly).
- Amount reuses the "say the right amount" step, then shows the saved card again.
- Category opens a WhatsApp list of ten likely categories: the household's own most used this
  month first, "Other" last, never the current one. Typing a category name ("Groceries", "राशन",
  "ഭക്ഷണം") while the list is open works too.
- Every button acts only on the record exactly as the card showed it (keyed fingerprint), as before.

**Merchant memory.** A category chosen for a payee (on WhatsApp or on the website, through any
category correction) is remembered in `merchant_categories` and applied when that payee's next
WhatsApp entry is saved, and suggested in quick add's preview. Unknown or masked payees are never
remembered.

**Check-ups, calculated (no model call):**
- "today" / "आज" / "ഇന്ന്";
- "this week", "summary", "हिसाब", "കണക്ക്" (the existing week view);
- "this month", "इस महीने", "ഈ മാസം", "budget", "goal": in, out, where it went, budgets, the
  savings goal, bills ahead and entries waiting for a check.

**Budgets.** "food budget 5000", "खाने का बजट 5000" or "ഭക്ഷണം ബജറ്റ് 5000" sets a monthly limit
for a spending category; without a category it is for all spending. Saved expenses show
"🟢 Food & dining: ₹4,200 of ₹5,000"; 🟡 from 80% of the limit, 🔴 once over. Income categories
have no budget.

**Savings goal.** "save 5000 a month" sets `users.monthly_savings_goal_minor`. "Kept" is income
minus spending, with money put into savings or investments counted as kept. Without income the
summary asks for it ("salary 30000").

**Monthly check-in (opt-in).** "This month" offers [🔔 Monthly check-in] when
`WHATSAPP_CHECKIN_TEMPLATE` is configured, and [🔕 Stop check-ins] once opted in. Opted-in
households get one approved utility template on the 1st (or the 2nd or 3rd if the server was
down), 08:00–20:00 IST, with last month's money in, money out and top category. STOP stops it with
everything else. A unique row per number and month (`whatsapp_checkins`) is written before the
send, so it is never sent twice. Pilot numbers come from the private allowlist; a self-serve
household's comes from its own encrypted copy, which must still hash to its binding.

**CFO limits.** Budgets and discipline only. The existing "can I afford it?" stays a cash-flow
model; no specific funds, stocks or securities are recommended.

**Spoken replies.** Pilot households hear every reply, as before. Self-serve households hear one
only when they sent a voice note.

## Reading

- **Several items:** the statement model returns the first payment in its main fields and up to
  nine more. With several, each amount must be said for that item: no whole-message fallback, and
  an item without its own amount is left out.
- **Bank SMS:** account, card, reference and phone numbers are masked (`[account]`, `[number]`)
  before the model sees the text. A question mark in "Not you? Call…" is not a question. Day-first
  dates (28-10-26, 28/10/2026, 28 Oct) are read, within the last year and never in the future.
  Without a model, the first rupee amount that is not a balance is used.
- **Bills and receipts:** the vision reader also returns `bill` (total, shop, date, kind of shop)
  for a purchase bill that is not a payment screen. Each field must appear verbatim in the
  transcript; an invented total is never used. A bill becomes a purchase line through the same
  pipeline as screenshots.
- **Budget and goal kinds** are grounded like any amount.

## Website (same design and theme)

- **Overview:** a Budgets card under "Where it went" (progress per budget, add, change or remove
  inline) and the savings goal in the same card.
- **Review:** shows only what FinBoy was unsure about, because diary entries are now saved at once.
- **Empty Overview:** adds "Send it on WhatsApp" with the existing chat link.
- **API:** `GET /api/v1/money/budgets`, `PATCH /api/v1/money/budgets`
  (`{category, limit_minor | null}`), `PATCH /api/v1/money/goal` (`{goal_minor | null}`). PATCH,
  not PUT, because the API's CORS policy allows no PUT.

## Self-serve replies fix

`MetaClient` refused every number outside the private allowlist, so self-serve households got no
WhatsApp reply at all, sign-in and sign-up cards included. The client now also sends to a number
the caller vouched for: `processor.send_reply` calls `allow()` only after matching the number to
its own self-serve binding, and the check-in sender only after the decrypted number hashes to the
binding. A new client is made for every message, so a vouch never carries over. The test fakes now
enforce the same rule.

## Data and privacy

- **Stored:** budgets, the savings goal, the check-in choice, payee→category pairs, and one
  check-in row per number and month. No message text, audio, image, transcript or number in clear
  is added.
- **Erasure:** household removal deletes budgets and merchant memory and clears the goal; bindings
  cascade to check-ins and prompts.
- **Prompts:** new purposes `saved`, `pick_item`, `pick_category` and `checkin_opt_in`; a
  `group_id` links one message's items for Undo all.

## Settings

| Setting | Value |
| --- | --- |
| `WHATSAPP_CHECKIN_TEMPLATE` | approved template name; unset means the check-in is neither offered nor sent |

## Human steps

1. **Meta template** `finboy_monthly_checkin` (Utility) in English (`en`), Hindi (`hi`) and
   Malayalam (`ml`), with four body parameters and no buttons. Text in
   [production](../production.md#money-manager-release-procedure).
2. **Wording:** a native read of the new Hindi and Malayalam copy (`hindi.py`, `malayalam.py`).
3. **Before a public push:** an Indian WhatsApp business number with a permanent token, and Google
   verification for Gmail.
4. **Local key:** the OpenAI key in the private secrets file still returns 401 (only the server's
   was replaced), so local checks used recorded model answers.
