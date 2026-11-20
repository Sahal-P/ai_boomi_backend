"""Malayalam rupee amounts said or typed as words: അഞ്ഞൂറ് (500), ആയിരത്തഞ്ഞൂറ് (1,500).

Speech-to-text often writes a spoken Malayalam amount as words, so these are read like Hindi number
words in hindi_numbers: deterministically, or not at all. Malayalam fuses the parts of a number
("ഇരുപത്തഞ്ച്" is 20 + 5, "എഴുന്നൂറ്റമ്പത്" is 700 + 50), so each word is split back into
hindi_numbers' tokens. Numbers below 100 stay words, so a lone "അഞ്ച്" is not money unless rupees
are named. Hundreds, thousands, lakhs and crores become a count and a multiplier. A word that
does not parse completely is left alone, and the caller asks "how many rupees?" instead of guessing.
"""

import re
import unicodedata
from fractions import Fraction

VIRAMA = "്"
_LETTER = re.compile(r"[ഀ-ൿ]")
# Atomic chillus are the same letters as consonant + virama (+ ZWJ in older text).
_CHILLU = str.maketrans({"ൺ": "ണ്", "ൻ": "ന്", "ർ": "ര്", "ൽ": "ല്", "ൾ": "ള്", "ൿ": "ക്"})
# A vowel starting the second part of a fused number becomes a sign on the stem's consonant.
_SIGNS = {
    "ആ": "ാ",
    "ഇ": "ി",
    "ഈ": "ീ",
    "ഉ": "ു",
    "ഊ": "ൂ",
    "എ": "െ",
    "ഏ": "േ",
    "ഐ": "ൈ",
    "ഒ": "ൊ",
    "ഓ": "ോ",
}
_VOWELS = {sign: vowel for vowel, sign in _SIGNS.items()}
_GEMINATE = frozenset("കചതപ")  # നൂറ്റി + പത്ത് is written നൂറ്റിപ്പത്ത് (110)

ONES = {
    "ഒന്ന്": 1,
    "രണ്ട്": 2,
    "മൂന്ന്": 3,
    "നാല്": 4,
    "അഞ്ച്": 5,
    "ആറ്": 6,
    "ഏഴ്": 7,
    "എട്ട്": 8,
    "ഒമ്പത്": 9,
    "ഒന്പത്": 9,  # ഒൻപത്
}
_TEENS = {
    "പത്ത്": 10,
    "പതിനൊന്ന്": 11,
    "പന്ത്രണ്ട്": 12,
    "പതിമൂന്ന്": 13,
    "പതിനാല്": 14,
    "പതിനഞ്ച്": 15,
    "പതിനാറ്": 16,
    "പതിനേഴ്": 17,
    "പതിനെട്ട്": 18,
    "പത്തൊമ്പത്": 19,
    "പത്തൊന്പത്": 19,
}
_TENS = {
    "ഇരുപത്": 20,
    "മുപ്പത്": 30,
    "നാല്പത്": 40,
    "നാല്പ്പത്": 40,
    "അമ്പത്": 50,
    "അന്പത്": 50,
    "അറുപത്": 60,
    "എഴുപത്": 70,
    "എണ്പത്": 80,
    "എമ്പത്": 80,
    "തൊണ്ണൂറ്": 90,
}
# How many hundreds each word is; the spellings speech-to-text writes, standard or not.
_HUNDREDS = {
    "നൂറ്": 1,
    "ഇരുനൂറ്": 2,
    "ഇരുന്നൂറ്": 2,
    "മുന്നൂറ്": 3,
    "നാനൂറ്": 4,
    "നാന്നൂറ്": 4,
    "അഞ്ഞൂറ്": 5,
    "അറുനൂറ്": 6,
    "അറുന്നൂറ്": 6,
    "എഴുനൂറ്": 7,
    "എഴുന്നൂറ്": 7,
    "ഏഴുനൂറ്": 7,
    "ഏഴുന്നൂറ്": 7,
    "എണ്ണൂറ്": 8,
    "തൊള്ളായിരം": 9,
}
_MULTIPLIERS = {"ലക്ഷം": "lakh", "ലക്ഷത്ത": "lakh", "ലക്ഷത്തി": "lakh", "കോടി": "crore"}
# A number word can carry a case ending: എഴുനൂറിന് (for 700), ആയിരത്തിന്റെ, നൂറോളം, അഞ്ഞൂറും.
_ENDINGS = ("ിന്റെ", "ിന്", "ും", "ോളം", "ാണ്")
# The thousand in a fused word: ആയിരം, രണ്ട|ായിരം, ഇരുപത|ിനായിരം; count, joint and the rest.
_THOUSAND = re.compile(r"(?P<count>.*?)(?P<joint>ആ|ിനാ|ാ)യിര(?P<rest>.*)")
# A thousands count whose last part changes before ആയിരം: മൂവായിരം, അയ്യായിരം, എണ്ണായിരം.
_THOUSAND_COUNTS = (("മൂവ", "മൂന്ന്"), ("യ്യ", "ഞ്ച്"), ("ണ്ണ", "ട്ട്"))


def plain(word: str) -> str:
    """One spelling per word: chillus as consonant + virama, no joiners, a final ു as ്."""
    word = unicodedata.normalize("NFC", word).replace("‍", "").replace("‌", "")
    word = word.translate(_CHILLU)
    return word[:-1] + VIRAMA if word.endswith("ു") else word


def _link(citation: str) -> str:
    """The stem before a further part: ഇരുപത് → ഇരുപത്ത, നൂറ് → നൂറ്റ, ആയിരം → ആയിരത്ത."""
    return citation[:-1] + "ത്ത" if citation.endswith("ം") else citation + citation[-2]


def _fused(link: str, number: str) -> list[str]:
    """How `number` is written after a linking stem: ഇരുപത്ത + അഞ്ച് → ഇരുപത്തിയഞ്ച്,
    ഇരുപത്തഞ്ച്; ഇരുപത്ത + രണ്ട് → ഇരുപത്തിരണ്ട്."""
    first, rest = number[0], number[1:]
    if first == "അ":
        return [link + "ിയ" + rest, link + rest]
    if first in _SIGNS:
        return [link + "ിയ" + _SIGNS[first] + rest, link + _SIGNS[first] + rest]
    if first in _GEMINATE:
        return [link + "ി" + number, link + "ി" + first + VIRAMA + number]
    return [link + "ി" + number]


def _unfused(tail: str) -> list[str]:
    """The numbers a fused tail can stand for (the inverse of `_fused`)."""
    found: list[str] = []
    for lead in ("ിയ", ""):
        rest = tail[len(lead) :] if tail.startswith(lead) else ""
        if rest[:1] in _VOWELS:
            found.append(_VOWELS[rest[0]] + rest[1:])
        elif rest and "ക" <= rest[0] <= "ഹ":  # a consonant carries the vowel അ
            found.append("അ" + rest)
    if tail.startswith("ി") and len(tail) > 1:
        rest = tail[1:]
        found.append(rest)
        if len(rest) > 2 and rest[1] == VIRAMA and rest[0] == rest[2]:
            found.append(rest[2:])
    return found


def _below_hundred() -> dict[str, int]:
    words = {"ഒര്": 1, **ONES, **_TEENS, **_TENS}  # ഒരു (one, "a") as plain() writes it
    for tens, tens_value in _TENS.items():
        for one, one_value in ONES.items():
            for form in _fused(_link(tens), one):
                words.setdefault(form, tens_value + one_value)
    return words


SMALL = _below_hundred()
# Halves before a multiplier: ഒന്നര ലക്ഷം (1.5 lakh), രണ്ടര ലക്ഷം; അര (half).
HALVES = {
    "അര": Fraction(1, 2),
    **{
        word[:-1] + "ര": Fraction(value) + Fraction(1, 2)
        for word, value in {**ONES, "പത്ത്": 10}.items()
    },
}
# The spelling that stands for each value below 100, for "ഇരുപത്തി അഞ്ച്" said as two words.
NAMES = {value: word for word, value in reversed(SMALL.items())}
_TENS_LINKS = {
    form: value for tens, value in _TENS.items() for form in (_link(tens), _link(tens) + "ി")
}


def _times(count: int, multiplier: str) -> list[str]:
    return [multiplier] if count == 1 else [str(count), multiplier]


def _below_thousand(word: str) -> list[str] | None:
    if word in SMALL or word in HALVES:
        return [word]
    for citation, count in _HUNDREDS.items():
        head = _times(count, "hundred")
        if word == citation:
            return head
        link = _link(citation)
        if not word.startswith(link):
            continue
        tail = word[len(link) :]
        if tail in {"", "ി"}:
            return head  # "എഴുനൂറ്റി" before a separate word: the next number adds
        for number in _unfused(tail):
            if number in SMALL:
                return [*head, str(SMALL[number])]
    return None


def _thousands_count(count: str, joint: str) -> int | None:
    if joint == "ആ":
        return 1 if not count else None
    if joint == "ിനാ" and count == "പത":
        return 10  # പതിനായിരം
    if joint == "ാ":
        for fused, citation in _THOUSAND_COUNTS:
            if count.endswith(fused):
                return SMALL.get(count[: -len(fused)] + citation)
    return SMALL.get(count + VIRAMA)


def _number(word: str) -> list[str] | None:
    """Tokens for one whole number word, or None when any part of it is not a number."""
    if word in _MULTIPLIERS:
        return [_MULTIPLIERS[word]]
    found = _below_thousand(word)
    if found is not None:
        return found
    split = _THOUSAND.fullmatch(word)
    count = _thousands_count(split["count"], split["joint"]) if split else None
    if split is None or count is None:
        return None
    head, rest = _times(count, "thousand"), split["rest"]
    if rest == "ം" or rest in {"ത്ത", "ത്തി"}:
        return head
    if not rest.startswith("ത്ത"):
        return None
    for number in _unfused(rest[3:]):
        below = _below_thousand(number)
        if below is not None:
            return head + below
    return None


def _readings(word: str) -> list[str]:
    """The word, and its stem without a case ending (എഴുനൂറിന് → എഴുനൂറ്, ആയിരമാണ് → ആയിരം)."""
    readings = [word]
    for ending in _ENDINGS:
        stem = word[: -len(ending)]
        if word.endswith(ending) and stem:
            readings += [stem + VIRAMA, stem]
            if stem.endswith("മ"):
                readings.append(stem[:-1] + "ം")
    return readings


def tokens(words: list[str]) -> list[str]:
    """hindi_numbers' tokens with each Malayalam number word replaced by its parts."""
    out: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        if not _LETTER.search(word):
            out.append(word)
            index += 1
            continue
        current = plain(word)
        following = plain(words[index + 1]) if index + 1 < len(words) else ""
        if current in _TENS_LINKS and following in ONES:
            out.append(NAMES[_TENS_LINKS[current] + ONES[following]])  # ഇരുപത്തി അഞ്ച്
            index += 2
            continue
        parts = next(
            (found for reading in _readings(current) if (found := _number(reading)) is not None),
            None,
        )
        out.extend(parts if parts is not None else [word])
        index += 1
    return out
