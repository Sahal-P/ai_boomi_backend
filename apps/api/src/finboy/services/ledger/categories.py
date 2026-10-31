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
    # UPI payee names as payment-app statements print them; whole words only, so "Smart Mobiles"
    # is not a "mart". Names that could be anything (a person, "… Stores") wait for Sort payees.
    (r"\b(airtel|jio|vodafone|vi (?:prepaid|postpaid)|bsnl|recharge)\b", "phone_recharge"),
    (
        r"\b(apple media services|google play|youtube|spotify|hotstar|jiocinema|prime video"
        r"|aws|amazon web services)\b",
        "subscriptions",
    ),
    (
        r"\b(broad ?band|fibernet|kseb|electricity board|gas agency|indane|bharat gas)\b",
        "utilities",
    ),
    (r"\b(indian railways|irctc|redbus|makemytrip|goibibo|ksrtc|airlines?)\b", "travel"),
    (r"\b(petrol|petroleum|fuels?|filling station|rapido|fastag|parking)\b", "transport"),
    (r"\b(medicals?|pharmacy|pharma|chemists?|hospital|clinic|diagnostics?|dental)\b", "health"),
    (r"\b(school|college|academy|university|tuition|coaching)\b", "education"),
    (
        r"\b(super ?market|hyper ?market|supermart|grocery|groceries|vegetables?|provisions?)\b",
        "groceries",
    ),
    (
        r"\b(hotel|restaurant|caf[eé]|bakery|bakers|juice|biriyani|biryani|tea stall|coffee)\b",
        "food_dining",
    ),
    (r"\b(flipkart|meesho|ajio|nykaa|textiles?|fashion|footwear|electronics)\b", "shopping"),
)


def normalize_merchant(merchant: str | None) -> str | None:
    if not merchant:
        return None
    clean = re.sub(r"\s+", " ", merchant).strip()
    return ALIASES.get(clean.lower(), clean)


# Village incomes a household names when money arrives; they refine the generic "credit".
INCOME_CATEGORIES: frozenset[Category] = frozenset(
    {"wages", "farm_sales", "govt_benefit", "remittance"}
)


def category_for(event: Event) -> Category:
    if event.event_type == "credit" and event.category in INCOME_CATEGORIES:
        return event.category
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
