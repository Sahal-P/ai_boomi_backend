"""Category names as households type or say them, in English, Hindi and Malayalam.

Used when a household types a category instead of tapping one in the list, and when a budget names
what it is for ("food budget 5000"). Matching is on whole words, after case folding and with
punctuation removed; nothing is sent to a model.
"""

import unicodedata
from typing import get_args

from finboy.services.ingestion.types import Category
from finboy.services.whatsapp import english, hindi, malayalam

# Everyday words for a category besides its label. Ambiguous words (fees, diesel) are left out.
SYNONYMS: dict[Category, tuple[str, ...]] = {
    "food_dining": (
        "food",
        "eating out",
        "restaurant",
        "tea",
        "chai",
        "snacks",
        "swiggy",
        "zomato",
        "khana",
        "खाना",
        "खाने",
        "नाश्ता",
        "चाय",
        "ഭക്ഷണം",
        "ചായ",
    ),
    "groceries": (
        "grocery",
        "ration",
        "kirana",
        "vegetables",
        "sabzi",
        "milk",
        "राशन",
        "किराना",
        "सब्ज़ी",
        "सब्जी",
        "दूध",
        "പച്ചക്കറി",
        "പാൽ",
    ),
    "transport": (
        "petrol",
        "fuel",
        "auto",
        "bus",
        "taxi",
        "cab",
        "uber",
        "ola",
        "metro",
        "ऑटो",
        "बस",
        "पेट्रोल",
        "ഓട്ടോ",
        "ബസ്",
        "പെട്രോൾ",
    ),
    "shopping": ("clothes", "amazon", "flipkart", "कपड़े", "खरीदारी", "തുണി"),
    "utilities": (
        "bills",
        "electricity",
        "power",
        "water",
        "gas",
        "internet",
        "wifi",
        "बिजली",
        "पानी",
        "गैस",
        "കറന്റ്",
        "വെള്ളം",
        "ഗ്യാസ്",
    ),
    "subscriptions": ("subscription", "netflix", "ott"),
    "travel": ("trip", "train", "flight", "hotel", "ട്രെയിൻ"),
    "health": (
        "medicine",
        "medical",
        "doctor",
        "hospital",
        "दवा",
        "इलाज",
        "डॉक्टर",
        "മരുന്ന്",
        "ആശുപത്രി",
    ),
    "education": ("school", "college", "books", "tuition", "पढ़ाई", "स्कूल", "സ്കൂൾ"),
    "investments": ("savings", "investment", "sip", "mutual fund", "fd", "बचत", "निवेश"),
    "loan_emi": (
        "loan",
        "emi",
        "instalment",
        "installment",
        "कर्ज़",
        "कर्ज",
        "किस्त",
        "लोन",
        "ലോൺ",
        "തവണ",
    ),
    "rent": ("house rent", "किराया"),
    "phone_recharge": ("recharge", "mobile", "phone", "रिचार्ज", "मोबाइल", "റീചാർജ്"),
    "family_events": ("wedding", "festival", "gift", "gifts", "शादी", "त्योहार", "കല്യാണം"),
    "farming": ("farm", "seeds", "fertiliser", "fertilizer", "खेती", "बीज", "खाद", "വളം"),
    "livestock": ("cattle", "fodder", "पशु", "चारा"),
    "salary": ("तनख्वाह", "सैलरी"),
    "wages": ("मजदूरी",),
    "other": ("others", "misc", "अन्य"),
}


def _words(text: str) -> str:
    """Case-folded words joined by single spaces, padded so names match only whole words."""
    folded = unicodedata.normalize("NFC", text).casefold()
    kept = "".join(
        c if c.isalnum() or unicodedata.category(c).startswith("M") else " " for c in folded
    )
    return " " + " ".join(kept.split()) + " "


def _names() -> dict[str, Category]:
    names: dict[str, Category] = {}
    for category in get_args(Category):
        names[_words(category.replace("_", " "))] = category
        for module in (english, hindi, malayalam):
            names[_words(module.CATEGORY[category])] = category
        for word in SYNONYMS.get(category, ()):
            names[_words(word)] = category
    names.pop("  ", None)
    return names


NAMES = _names()


def exact(text: str) -> Category | None:
    """The category a whole message names, like "Groceries", "राशन" or "ഭക്ഷണം"."""
    return NAMES.get(_words(text))


def named(text: str) -> Category | None:
    """The category named anywhere in a message, preferring the longest name."""
    padded = _words(text)
    found = [(len(name), category) for name, category in NAMES.items() if name in padded]
    return max(found)[1] if found else None
