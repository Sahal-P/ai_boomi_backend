"""Deterministic rupee amounts from digits and Hindi/Hinglish number words. Never guesses.

Spoken Hindi amounts mix forms: "500", "पाँच सौ", "बारह सौ" (1,200), "डेढ़ सौ" (150), "ढाई हज़ार"
(2,500), "सवा लाख" (1,25,000), "साढ़े तीन सौ" (350), "पौने दो सौ" (175), "paanch sau". Anything
ambiguous (two amounts, a bare fraction, an unknown word inside a number) yields None so the
caller asks "कितने रुपये?" instead of recording a guess.
"""

import re
import unicodedata
from fractions import Fraction

MAX_RUPEES = 10**7  # one crore; larger spoken amounts are treated as misheard

_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUMBER = re.compile(r"\d+(?:\.\d{1,2})?")
_SEPARATORS = re.compile(r"[\s,;:!?।|/()\[\]\"'“”‘’\-–—]+")


def _norm(word: str) -> str:
    """Spelling-tolerant key: no nukta, chandrabindu as anusvara, Latin lowercased."""
    word = unicodedata.normalize("NFC", word).lower().strip(".")
    return word.replace("़", "").replace("ँ", "ं")


_HINDI = """
शून्य 0|एक 1|दो 2|तीन 3|चार 4|पांच पाँच 5|छह छः छै छे 6|सात 7|आठ 8|नौ 9|दस 10|ग्यारह 11|बारह 12
तेरह 13|चौदह 14|पंद्रह पन्द्रह 15|सोलह 16|सत्रह 17|अठारह 18|उन्नीस 19|बीस 20|इक्कीस 21|बाईस 22
तेईस 23|चौबीस 24|पच्चीस 25|छब्बीस 26|सत्ताईस 27|अट्ठाईस अठ्ठाईस अठाईस 28|उनतीस 29|तीस 30
इकतीस 31|बत्तीस 32|तैंतीस तैतीस 33|चौंतीस चौतीस 34|पैंतीस पैतीस 35|छत्तीस 36|सैंतीस 37|अड़तीस 38
उनतालीस 39|चालीस 40|इकतालीस 41|बयालीस 42|तैंतालीस 43|चवालीस चौवालीस 44|पैंतालीस 45|छियालीस 46
सैंतालीस 47|अड़तालीस 48|उनचास 49|पचास 50|इक्यावन 51|बावन 52|तिरपन 53|चौवन 54|पचपन 55|छप्पन 56
सत्तावन 57|अट्ठावन अठ्ठावन 58|उनसठ 59|साठ 60|इकसठ 61|बासठ 62|तिरसठ 63|चौंसठ चौसठ 64|पैंसठ 65
छियासठ 66|सड़सठ सरसठ 67|अड़सठ 68|उनहत्तर 69|सत्तर 70|इकहत्तर 71|बहत्तर 72|तिहत्तर 73|चौहत्तर 74
पचहत्तर 75|छिहत्तर 76|सतहत्तर 77|अठहत्तर 78|उनासी उन्यासी 79|अस्सी 80|इक्यासी 81|बयासी 82|तिरासी 83
चौरासी 84|पचासी 85|छियासी 86|सत्तासी 87|अट्ठासी अठ्ठासी 88|नवासी नब्बासी 89|नब्बे 90|इक्यानवे 91
बानवे 92|तिरानवे 93|चौरानवे 94|पंचानवे पचानवे 95|छियानवे 96|सत्तानवे 97|अट्ठानवे 98|निन्यानवे निन्यानबे 99
ek 1|do 2|teen tin 3|char chaar 4|panch paanch paach 5|chhe chhah che 6|saat 7|aath 8|nau 9|das 10
gyarah gyaarah 11|barah baarah 12|terah 13|chaudah 14|pandrah 15|solah 16|satrah 17|atharah 18
unnis 19|bees 20|pachchees pachis 25|tees 30|chalis chaalis 40|pachas pachaas 50|saath 60
sattar 70|assi 80|nabbe 90
"""
WORDS: dict[str, Fraction] = {}
for _entry in re.split(r"[|\n]", _HINDI):
    *_names, _value = _entry.split() or [""]
    for _name in _names:
        WORDS[_norm(_name)] = Fraction(int(_value))
# Fractions said on their own before a multiplier: डेढ़ सौ = 150, ढाई हज़ार = 2,500.
for _name, _value in {
    "डेढ़": "3/2",
    "dedh": "3/2",
    "ढाई": "5/2",
    "अढ़ाई": "5/2",
    "dhai": "5/2",
}.items():
    WORDS[_norm(_name)] = Fraction(_value)

MULTIPLIERS = {
    _norm(name): value
    for names, value in (
        ("सौ sau", 100),
        ("हज़ार हजार hazar hazaar hajar", 1000),
        ("लाख lakh lac", 100_000),
        ("करोड़ करोड crore karod", 10_000_000),
    )
    for name in names.split()
}
# Modifiers adjust the number that follows: सवा = +¼, साढ़े = +½, पौने = −¼ (of the multiplier).
MODIFIERS = {
    _norm(name): Fraction(value)
    for names, value in (
        ("सवा sawa sava", "1/4"),
        ("साढ़े साढे sadhe saadhe sade", "1/2"),
        ("पौने paune pone", "-1/4"),
    )
    for name in names.split()
}
CURRENCY = {
    _norm(name)
    for name in [
        "₹",
        "रुपये",
        "रुपए",
        "रुपया",
        "रुपयों",
        "रु",
        "rs",
        "rs.",
        "inr",
        "rupees",
        "rupee",
        "rupaye",
        "rupaiye",
        "rupay",
    ]
}


def _tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).translate(_DIGITS)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)  # 1,200 and 1,25,000
    text = re.sub(r"(?<=\d)(?=[^\d\s.,])|(?<=[^\d\s.,])(?=\d)", " ", text)  # ₹500, 500रुपये
    return [token for token in (_norm(item) for item in _SEPARATORS.split(text)) if token]


def _is_amount_token(token: str) -> bool:
    return (
        bool(_NUMBER.fullmatch(token))
        or token in WORDS
        or token in MULTIPLIERS
        or (token in MODIFIERS)
    )


def _value(run: list[str]) -> Fraction | None:
    """Groups of [modifier] [number] [multiplier] with strictly falling multipliers."""
    total, last, index = Fraction(0), None, 0
    while index < len(run):
        modifier = MODIFIERS.get(run[index])
        if modifier is not None:
            index += 1
        base = None
        if index < len(run) and (_NUMBER.fullmatch(run[index]) or run[index] in WORDS):
            token = run[index]
            base = Fraction(token) if _NUMBER.fullmatch(token) else WORDS[token]
            index += 1
        multiplier = None
        if index < len(run) and run[index] in MULTIPLIERS:
            multiplier = MULTIPLIERS[run[index]]
            index += 1
        if base is None and multiplier is None:
            return None
        if modifier is not None:
            if multiplier is None:
                return None  # "साढ़े तीन" alone is not a rupee amount
            base = (base or Fraction(1)) + modifier
        group = multiplier or 1
        if last is not None and group >= last:
            return None
        total += (base if base is not None else Fraction(1)) * group
        last = group
    return total


def find_amounts(text: str) -> list[int]:
    """Every distinct amount (in paise) stated in text, in order of appearance."""
    tokens = _tokens(text)
    found: list[int] = []
    index = 0
    while index < len(tokens):
        if not _is_amount_token(tokens[index]):
            index += 1
            continue
        end = index
        while end < len(tokens) and _is_amount_token(tokens[end]):
            end += 1
        run = tokens[index:end]
        near_currency = (index > 0 and tokens[index - 1] in CURRENCY) or (
            end < len(tokens) and tokens[end] in CURRENCY
        )
        # A lone small word ("एक दुकान", "do") is usually not money unless rupees are named.
        lone_word = (
            len(run) == 1
            and run[0] in WORDS
            and not _NUMBER.fullmatch(run[0])
            and not near_currency
        )
        value = None if lone_word else _value(run)
        paise = None if value is None else value * 100
        if (
            value is not None
            and paise is not None
            and paise.denominator == 1
            and 0 < value <= MAX_RUPEES
            and int(paise) not in found
        ):
            found.append(int(paise))
        index = end
    return found


def parse_amount(text: str) -> int | None:
    """Exactly one stated amount in paise, or None when absent or ambiguous."""
    amounts = find_amounts(text)
    return amounts[0] if len(amounts) == 1 else None
