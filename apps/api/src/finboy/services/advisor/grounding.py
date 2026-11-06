"""Every figure in an advisor reply must come from FinBoy's own numbers (docs/advisor-round).

The model may quote rupee amounts, percentages and other numbers only when they appear in a tool
result, the snapshot, a memory, the conversation or the question. Small plain numbers (a list
item, a day, "3 payments") are fine; anything that looks like money, a percentage, or any number
of 100 or more is checked. "₹1,20,000", "120000", "1.2 lakh" and "१,२०,०००" are the same figure.
"""

import re
from collections.abc import Iterable
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation

from finboy.services.assistant.intent import SCALED, SCALES
from finboy.services.assistant.periods import normalized

NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
MONEY_NEAR = re.compile(
    r"₹|\brs\.?|\binr\b|rupee|रुपय|रुपए|रूपय|रुपया|രൂപ|%|percent|प्रतिशत|ശതമാനം", re.IGNORECASE
)
SMALL = Decimal(100)


def _value(token: str) -> Decimal | None:
    try:
        return Decimal(token.replace(",", ""))
    except InvalidOperation:
        return None


def figures(text: str) -> list[tuple[Decimal, bool]]:
    """(value, looks like money or a percentage) for each number in the text."""
    found: list[tuple[Decimal, bool]] = []
    question = normalized(text)
    for number, word in SCALED.findall(question):
        value = _value(number)
        if value is not None:
            found.append((value * SCALES[word], True))
    question = SCALED.sub(" ", question)
    for match in NUMBER.finditer(question):
        value = _value(match.group().rstrip(","))
        if value is None:
            continue
        around = question[max(0, match.start() - 12) : match.end() + 12]
        found.append((value, bool(MONEY_NEAR.search(around))))
    return found


def allowed(texts: Iterable[str]) -> set[Decimal]:
    """Every number in the sources, with its whole-rupee roundings."""
    values: set[Decimal] = set()
    for text in texts:
        for value, _ in figures(text):
            values.add(value)
            values.add(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
            values.add(value.quantize(Decimal(1), rounding=ROUND_FLOOR))
    return values


def unchecked(texts: Iterable[str], sources: set[Decimal]) -> list[str]:
    """The figures in a reply that no source contains."""
    missing: list[str] = []
    for text in texts:
        for value, money_like in figures(text):
            if value < SMALL and not money_like:
                continue
            if value not in sources:
                missing.append(format(value, "f"))
    return list(dict.fromkeys(missing))
