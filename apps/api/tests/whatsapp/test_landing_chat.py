"""The landing's WhatsApp chat says only what FinBoy sends.

apps/web/src/lib/chat-demo/finboy-copy.json holds every text the landing's live chat shows, and
the web's script.test.ts checks the chat produces them. This rebuilds the file from english.py
and pilot.py. When FinBoy's wording changes, update the JSON and script.ts to match.
"""

import json
from datetime import date
from pathlib import Path

from finboy.services.money.budgets import BudgetStatus
from finboy.services.whatsapp import english as words
from finboy.services.whatsapp import pilot

COPY = Path(__file__).resolve().parents[3] / "web/src/lib/chat-demo/finboy-copy.json"
TODAY = date(2026, 11, 10)
TEXTS = (
    "UNDO",
    "AMOUNT",
    "CATEGORY_BUTTON",
    "PUT_BACK",
    "UNDO_ALL",
    "FIX_ONE",
    "CHANGE_ASK",
    "AMOUNT_CHANGED",
    "AMOUNT_UNCLEAR",
    "PUT_BACK_DONE",
    "FIX_ASK",
    "FIX_OPEN",
    "FIX_SECTION",
    "CATEGORY_ASK",
    "CATEGORY_OPEN",
    "CATEGORY_SECTION",
    "CHANGED",
    "UNDO_REFUSED",
    "NOTHING_TO_FIX",
)


def groceries(spent: int) -> BudgetStatus:
    """The demo household's one budget: ₹6,000 on groceries."""
    return BudgetStatus("groceries", 600_000, spent)


def saved(amount: int, category, payee: str | None = None, budget=None) -> tuple[str, str]:
    return words.saved(
        amount_minor=amount,
        out=True,
        counterparty=payee,
        day=TODAY,
        category=category,
        today=TODAY,
        budget=budget,
    )


def test_the_landing_chat_says_what_finboy_sends() -> None:
    spending = list(pilot.SPENDING_ORDER[:10])
    many = [(2_000, True, None, "food_dining"), (5_000, True, None, "transport")]
    many.append((12_000, True, None, "food_dining"))
    expected = {
        "texts": {name: getattr(words, name) for name in TEXTS},
        "categories": {name: words.CATEGORY[name] for name in (*spending, "other")},
        "spending_order": spending,
        "examples": {
            "saved_many": words.saved_many(saved=many, unsure=[], budgets=[])[0],
            "saved_milkman": saved(50_000, "groceries", "milkman", groceries(230_000))[0],
            "spoken_milkman": saved(50_000, "groceries", "milkman", groceries(230_000))[1],
            "saved_milkman_400": saved(40_000, "groceries", "milkman", groceries(220_000))[0],
            "saved_milkman_near": saved(300_000, "groceries", "milkman", groceries(480_000))[0],
            "saved_milkman_over": saved(500_000, "groceries", "milkman", groceries(680_000))[0],
            "saved_milkman_paise": saved(45_050, "groceries", "milkman", groceries(225_050))[0],
            "saved_milkman_food": saved(50_000, "food_dining", "milkman")[0],
            "saved_auto": saved(5_000, "transport")[0],
            "removed_milkman": words.removed(50_000, True, "milkman"),
            "removed_auto": words.removed(5_000, True, None),
            "removed_many_3": words.removed_many(3, 19_000),
            "removed_many_1": words.removed_many(1, 2_000),
            "category_changed_milkman": words.category_changed("food_dining", "milkman"),
            "category_changed_auto": words.category_changed("shopping", None),
            "fix_title_chai": pilot._title(2_000, words.CATEGORY["food_dining"]),
            "fix_title_auto": pilot._title(5_000, words.CATEGORY["transport"]),
            "lakh": words.removed(12_345_600, True, None),
        },
    }
    assert json.loads(COPY.read_text(encoding="utf-8")) == expected, (
        "FinBoy's WhatsApp wording changed: update finboy-copy.json and script.ts to match"
    )
