"""Deterministic display style and value-preserving speech normalization."""

import re
from datetime import date
from decimal import Decimal

from finboy.core.languages import DisplayStyle, Language
from finboy.services.assistant.intent import normalized

ResolvedStyle = str


def resolve_style(text: str, requested: DisplayStyle) -> tuple[str, Language]:
    if requested != "auto":
        return requested, "hi" if requested in {"hi", "hinglish"} else "ml" if requested in {
            "ml",
            "manglish",
        } else "en"
    if re.search(r"[\u0d00-\u0d7f]", text):
        return "ml", "ml"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi", "hi"
    q = normalized(text)
    # Question words, then everyday money words. Never English words or common names (no "mile",
    # no "Rupa"): "Paid Roopa 500" stays English.
    if re.search(
        r"\b(ee masam|ethra|poyi|pattumo|enthanu|varumanam|chelavu|ente|koduthu|kodutthu|kitti"
        r"|chelavayi|chilavayi|innale|vangi|vaangi|adachu|sambalam)\b",
        q,
    ):
        return "manglish", "ml"
    if re.search(
        r"\b(mahine|khane|kharch|kharcha|kitna|kya|kaunsa|mera|meri|bacha|paise|diye|diya|liye"
        r"|liya|mila|rupaye|rupay|hazaar|hazar|udhaar|udhar|kiraya|doodh|sabzi|aaj|kal|bheje"
        r"|bheja|kiya|hua|gaya|wale|wala)\b",
        q,
    ):
        return "hinglish", "hi"
    return "en", "en"


def indian_digits(value: int) -> str:
    digits = str(abs(value))
    if len(digits) > 3:
        tail, head = digits[-3:], digits[:-3]
        groups = []
        while head:
            groups.append(head[-2:])
            head = head[:-2]
        digits = ",".join([*reversed(groups), tail])
    return ("-" if value < 0 else "") + digits


def money(amount_minor: int) -> str:
    whole, paise = divmod(abs(amount_minor), 100)
    return (
        ("-" if amount_minor < 0 else "")
        + "₹"
        + indian_digits(whole)
        + (f".{paise:02}" if paise else "")
    )


def spoken_money(amount_minor: int, language: Language) -> str:
    whole, paise = divmod(abs(amount_minor), 100)
    unit, fraction, minus = {
        "en": ("rupees", "paise", "minus"),
        "hi": ("रुपये", "पैसे", "ऋण"),
        "ml": ("രൂപ", "പൈസ", "മൈനസ്"),
    }[language]
    return f"{minus + ' ' if amount_minor < 0 else ''}{indian_digits(whole)} {unit}" + (
        f" {paise} {fraction}" if paise else ""
    )


def normalize_speech(text: str, language: Language) -> str:
    def currency(match: re.Match[str]) -> str:
        value = Decimal(match[1].replace(",", "")) * 100
        return spoken_money(int(value), language)

    text = re.sub(r"₹\s*(-?\d[\d,]*(?:\.\d{1,2})?)", currency, text)
    pronunciation = {
        "en": {"SIP": "S I P", "UPI": "U P I", "EMI": "E M I"},
        "hi": {"SIP": "एस आई पी", "UPI": "यू पी आई", "EMI": "ई एम आई"},
        "ml": {"SIP": "എസ് ഐ പി", "UPI": "യു പി ഐ", "EMI": "ഇ എം ഐ"},
    }[language]
    for word, replacement in pronunciation.items():
        text = re.sub(rf"\b{word}\b", replacement, text, flags=re.I)
    # Keep ISO dates unambiguous, with localized month names instead of slash ambiguity.
    months = {
        "en": (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        "hi": (
            "जनवरी",
            "फ़रवरी",
            "मार्च",
            "अप्रैल",
            "मई",
            "जून",
            "जुलाई",
            "अगस्त",
            "सितंबर",
            "अक्टूबर",
            "नवंबर",
            "दिसंबर",
        ),
        "ml": (
            "ജനുവരി",
            "ഫെബ്രുവരി",
            "മാർച്ച്",
            "ഏപ്രിൽ",
            "മേയ്",
            "ജൂൺ",
            "ജൂലൈ",
            "ഓഗസ്റ്റ്",
            "സെപ്റ്റംബർ",
            "ഒക്ടോബർ",
            "നവംബർ",
            "ഡിസംബർ",
        ),
    }[language]

    def spoken_date(match: re.Match[str]) -> str:
        try:
            value = date.fromisoformat(match[0])
            return f"{value.day} {months[value.month - 1]} {value.year}"
        except ValueError:
            return match[0]

    return re.sub(r"\b\d{4}-\d{2}-\d{2}\b", spoken_date, text)


def numeric_guard(candidate: str, template: str) -> str:
    """Optional wording may neither add, remove, reorder, nor change numeric literals."""

    def numbers(value: str) -> list[str]:
        return [
            x.replace(",", "")
            for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", normalized(value).replace("₹", ""))
        ]

    return candidate if numbers(candidate) == numbers(template) else template
