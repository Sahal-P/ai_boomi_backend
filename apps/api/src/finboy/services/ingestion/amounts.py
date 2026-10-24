import re
from decimal import Decimal

_NUMBER = r"(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d{1,2})?"
_AMOUNT = re.compile(rf"(?:₹|Rs\.?|INR)?\s*(?P<number>{_NUMBER})", re.IGNORECASE)


def parse_amount(value: str) -> int:
    """Parse positive INR without floats; reject malformed grouping and fractions of paise."""
    match = _AMOUNT.fullmatch(value.strip())
    if not match:
        raise ValueError("invalid_amount")
    result = int(Decimal(match["number"].replace(",", "")) * 100)
    if not 0 < result <= 10**14:
        raise ValueError("invalid_amount")
    return result


AMOUNT_PATTERN = rf"(?:₹|Rs\.?|INR)\s*(?P<amount>{_NUMBER})(?![\d,]|\.\d)"
