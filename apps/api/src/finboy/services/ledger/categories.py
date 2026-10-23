import re

from finboy.services.ingestion.types import Category, Event

ALIASES = {
    "amazon seller services private limited": "Amazon",
    "bundl technologies pvt ltd": "Swiggy",
}
CATEGORY_RULES: tuple[tuple[str, Category], ...] = (
    (r"hotel arya", "travel"),
    (r"swiggy|zomato|cafe|restaurant|canteen", "food_dining"),
    (r"freshmart|grocer", "groceries"),
    (r"metro|uber|fuel", "transport"),
    (r"amazon|bookshop|myntra", "shopping"),
    (r"rent|landlord", "rent"),
    (r"netflix|music|subscription", "subscriptions"),
    (r"electricity|internet", "utilities"),
)


def normalize_merchant(merchant: str | None) -> str | None:
    if not merchant:
        return None
    clean = re.sub(r"\s+", " ", merchant).strip()
    return ALIASES.get(clean.lower(), clean)


def category_for(event: Event) -> Category:
    special: dict[str, Category] = {
        "salary": "salary",
        "credit": "other_income",
        "investment": "investments",
        "transfer": "transfer",
        "emi_due": "loan_emi",
        "fee": "fees",
    }
    if event.event_type in special:
        return special[event.event_type]
    merchant = normalize_merchant(event.merchant) or ""
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, merchant, re.I):
            return category
    return event.category or "other"
