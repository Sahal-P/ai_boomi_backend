"""Dates people write or say, read by rules (docs/whatsapp.md, "Dates and card replies").

English, Hindi and Malayalam, in their own scripts or romanised: "january 1", "1st of Jan",
"01/01/27", "1 जनवरी", "ജനുവരി ഒന്നിന്", "पहली तारीख", "tomorrow", "next friday", "month end".
A due looks forward and a payment looks back, so the same words resolve by direction: Hindi कल
is tomorrow for a due and yesterday for a payment. The reader returns the date, or why there is
none, and where the text said it, so an amount is never read from a date ("january 1" is not ₹1).
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from finboy.services.ingestion.hindi_numbers import only_amount
from finboy.services.ingestion.months import (
    AMBIGUOUS,
    ENGLISH,
    NATIVE_NORMALIZED,
    ROMANISED,
    normalized,
)

Direction = Literal["past", "future"]
Problem = Literal["month_only", "invalid", "ambiguous", "out_of_range"]
Span = tuple[int, int]

OVERDUE_DAYS = 31  # a named date this recent that has passed is overdue, not next year
FUTURE_DAYS = 400
PAST_DAYS = 366

_DIGITS = str.maketrans("०१२३४५६७८९൦൧൨൩൪൫൬൭൮൯", "01234567890123456789")
_TOKEN = re.compile(r"[^\s,;:!?()\[\]\"“”।|]+")
# A day of the month with what marks it as one: 1st, 5ാം, 10-ാം; a Malayalam dative ("20ന്")
# is also a price, so it counts only next to a month.
_DAY_DIGITS = re.compile(r"(\d{1,2})(st|nd|rd|th|-?ാം|-?ാമത്തെ|-?ന്|-?നു|nu|ne|ko|को|tak|तक)?")
_ISO = re.compile(r"(?<![\d.,])(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})(?![\d,]|\.\d)")
_NUMERIC = re.compile(r"(?<![\d.,])(\d{1,2})([/.-])(\d{1,2})(?:\2(\d{4}|\d{2}))?(?![\d,]|\.\d)")
_YEAR = re.compile(r"['’](\d{2})|((?:19|20)\d{2})")
# Words that make the number before them a date: "10 तारीख", "5 को", "1-ാം തീയതി", "by 5 tak".
DATE_WORDS = frozenset(
    {"तारीख", "तारीक", "tarikh", "tareekh", "tarik", "tareek", "date", "dated", "को", "ko"}
    | {"तक", "tak", "തീയതി", "തിയതി", "തീയ്യതി", "തിയ്യതി"}
)
_LEADS = frozenset({"on", "by", "before", "till", "until", "dated"})
_UNITS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth"]
_ENGLISH_ORDINALS = {name: number for number, name in enumerate(_UNITS, start=1)}
_ENGLISH_ORDINALS |= {
    name: number
    for number, name in enumerate(
        [
            "tenth",
            "eleventh",
            "twelfth",
            "thirteenth",
            "fourteenth",
            "fifteenth",
            "sixteenth",
            "seventeenth",
            "eighteenth",
            "nineteenth",
            "twentieth",
        ],
        start=10,
    )
}
_ENGLISH_ORDINALS |= {f"twenty-{unit}": 20 + n for n, unit in enumerate(_UNITS, start=1)}
_ENGLISH_ORDINALS |= {"thirtieth": 30, "thirty-first": 31}
_HINDI_ORDINALS = {
    "पहली": 1, "पहला": 1, "पहले": 1, "pehli": 1, "pahli": 1, "pehla": 1, "pahla": 1,
    "दूसरी": 2, "दूसरा": 2, "दूसरे": 2, "doosri": 2, "dusri": 2, "doosra": 2, "dusra": 2,
    "तीसरी": 3, "तीसरा": 3, "तीसरे": 3, "teesri": 3, "tisri": 3, "teesra": 3, "tisra": 3,
    "चौथी": 4, "चौथा": 4, "चौथे": 4, "chauthi": 4, "chautha": 4,
    "छठी": 6, "छठा": 6, "छठे": 6, "chhathi": 6, "chhati": 6, "chhatha": 6,
}  # fmt: skip
_HINDI_ORDINAL_ENDINGS = ("वीं", "वां", "वें", "वी", "वा", "वे")
_MALAYALAM_DAY_ENDINGS = ("ാമത്തെ", "ാം", "ിന്", "ിനു", "ന്")
_DEVANAGARI = "ऀ-ॿ"
_SCRIPTS = "ऀ-ॿഀ-ൿ"


def _hindi(word: str) -> str:
    """A Devanagari word on its own, so कल is not found in कलम or आजकल."""
    return rf"(?<![{_SCRIPTS}]){word}(?![{_DEVANAGARI}])"


def _malayalam(word: str) -> str:
    """A Malayalam word at a word start; its endings may follow (നാളെയും)."""
    return rf"(?<![{_SCRIPTS}]){word}"


_TODAY = rf"\btoday\b|\baaj\b|{_hindi('आज')}|{_malayalam('ഇന്ന്')}|\binnu\b"
_RELATIVE: dict[str, list[tuple[re.Pattern[str], int]]] = {
    "future": [
        (
            re.compile(
                rf"day after tomorrow|{_hindi('परसों')}|{_hindi('परसो')}|\bparso[n]?\b"
                rf"|{_malayalam('മറ്റന്നാൾ')}|\bmattannaa?l\b"
            ),
            2,
        ),
        (
            re.compile(
                rf"\btomorrow\b|\btmrw?\b|{_hindi('कल')}|\bkal\b|{_malayalam('നാളെ')}|\bnaa?ley?\b"
            ),
            1,
        ),
        (re.compile(_TODAY), 0),
    ],
    "past": [
        (
            re.compile(
                rf"day before yesterday|{_hindi('परसों')}|{_hindi('परसो')}|\bparso[n]?\b"
                rf"|{_malayalam('മിനിഞ്ഞാന്ന്')}|{_malayalam('മിനിയാന്ന്')}"
            ),
            -2,
        ),
        (
            re.compile(rf"\byesterday\b|{_hindi('कल')}|\bkal\b|{_malayalam('ഇന്നലെ')}|\binnale\b"),
            -1,
        ),
        (re.compile(_TODAY), 0),
    ],
}
_IN_DAYS = {
    "future": re.compile(
        r"\b(?:in|after)\s+(\d{1,3})\s+days?\b|\b(\d{1,3})\s+days?\s+(?:later|from now)\b"
        r"|(\d{1,3})\s*(?:din|दिन)\s*(?:me|mein|में|baad|bad|बाद)|(\d{1,3})\s*ദിവസം\s*കഴിഞ്ഞ്"
    ),
    "past": re.compile(
        r"\b(\d{1,3})\s+days?\s+ago\b|(\d{1,3})\s*(?:din|दिन)\s*(?:pehle|pahle|पहले)"
        r"|(\d{1,3})\s*ദിവസം\s*(?:മുമ്പ്|മുൻപ്)"
    ),
}
_NEXT_MONTH = re.compile(r"next month|अगले महीने|agle mahine|അടുത്ത മാസം")
_THIS_MONTH = re.compile(r"this month|इस महीने|is mahine|ഈ മാസം")
_VAGUE = re.compile(r"next week|अगले हफ़?्ते|agle hafte|അടുത്ത ആഴ്ച|last week|पिछले हफ़?्ते")
_MONTH_END = re.compile(
    r"month[- ]end|end of (?:the |this )?month|महीने के (?:अंत|आखिर|आख़िर)"
    r"|mahine ke (?:ant|aakhir|akhir)|മാസാവസാനം|മാസം അവസാനം"
)
_WEEKDAYS = {
    **dict.fromkeys(("monday", "सोमवार", "somvar", "somwar", "തിങ്കളാഴ്ച"), 0),
    **dict.fromkeys(("tuesday", "मंगलवार", "mangalvar", "mangalwar", "ചൊവ്വാഴ്ച"), 1),
    **dict.fromkeys(("wednesday", "बुधवार", "budhvar", "budhwar", "ബുധനാഴ്ച"), 2),
    **dict.fromkeys(("thursday", "गुरुवार", "बृहस्पतिवार", "guruvar", "guruwar", "വ്യാഴാഴ്ച"), 3),
    **dict.fromkeys(("friday", "शुक्रवार", "shukravar", "shukrawar", "വെള്ളിയാഴ്ച"), 4),
    **dict.fromkeys(("saturday", "शनिवार", "shanivar", "shaniwar", "ശനിയാഴ്ച"), 5),
    **dict.fromkeys(("sunday", "रविवार", "ravivar", "raviwar", "ഞായറാഴ്ച"), 6),
}
_SHORT_WEEKDAYS = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3}
_SHORT_WEEKDAYS |= {"fri": 4, "sat": 5, "sun": 6}
_WEEKDAY_LEADS = frozenset({"on", "next", "last", "this", "coming"})
_FULL_NAMES = {name: month for name, month in (ENGLISH | ROMANISED).items() if len(name) >= 5}


@dataclass(frozen=True)
class DateRead:
    """A date the text said, or why it can't be used; `spans` are where it was said."""

    day: date | None = None
    problem: Problem | None = None
    month: int | None = None  # a month named without its day (month_only)
    year: int | None = None
    spans: tuple[Span, ...] = ()

    @property
    def said(self) -> bool:
        return bool(self.spans)


@dataclass(frozen=True)
class _Found:
    span: Span
    day: date | None = None
    problem: Problem | None = None
    month: int | None = None
    year: int | None = None
    alone: int | None = None  # a day of the month said without its month


def fold(text: str) -> str:
    """Lowercase Latin and ASCII digits, one character for one, so spans fit the original."""
    return "".join(c.lower() if c.isascii() else c for c in text.translate(_DIGITS))


def strip(text: str, spans: tuple[Span, ...]) -> str:
    """The text with the date's words blanked out, for reading an amount."""
    chars = list(text)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def _one_edit(word: str, name: str) -> bool:
    """A typo of one letter: "janurary", "febuary", "agust"."""
    if abs(len(word) - len(name)) > 1:
        return False
    short, long = sorted((word, name), key=len)
    for index, (a, b) in enumerate(zip(short, long, strict=False)):
        if a != b:
            rest = short[index + 1 :] if len(short) == len(long) else short[index:]
            return rest == long[index + 1 :]
    return True


def month_of(token: str) -> tuple[int, bool] | None:
    """The month a word names, and whether it is also an everyday word (may, march, jan…)."""
    word = token.strip(".'’-")
    if word in ENGLISH:
        return ENGLISH[word], word in AMBIGUOUS
    if word in ROMANISED:
        return ROMANISED[word], False
    native = normalized(word)
    for stem, month in NATIVE_NORMALIZED.items():
        if native == stem or (native.startswith(stem) and len(native) - len(stem) <= 6):
            return month, False
    if word.isascii() and word.isalpha() and len(word) >= 5:
        for name, month in _FULL_NAMES.items():
            if _one_edit(word, name):
                return month, False
    return None


def _number_word(word: str) -> int | None:
    paise = only_amount(word)
    if paise is None or paise % 100:
        return None
    value = paise // 100
    return value if 1 <= value <= 31 else None


def day_of(token: str, *, words: bool) -> tuple[int, bool] | None:
    """A day of the month in one word, and whether the word itself marks it as a date (1st, 5ാം).

    Ordinal words (first, पहली, ഒന്നാം) and plain number words count only when `words` is true:
    next to a month, a date word or "on the"."""
    word = token.strip(".'’")
    found = _DAY_DIGITS.fullmatch(word)
    if found:
        number, suffix = int(found[1]), found[2] or ""
        marked = bool(suffix) and not any(dative in suffix for dative in ("ന്", "നു", "nu", "ne"))
        return (number, marked) if 1 <= number <= 31 else None
    if not words:
        return None
    if word in _ENGLISH_ORDINALS:
        return _ENGLISH_ORDINALS[word], True
    if word in _HINDI_ORDINALS:
        return _HINDI_ORDINALS[word], True
    for ending in _HINDI_ORDINAL_ENDINGS:
        if word.endswith(ending) and (value := _number_word(word[: -len(ending)])):
            return value, True
    for ending in _MALAYALAM_DAY_ENDINGS:
        if word.endswith(ending) and (value := _number_word(word[: -len(ending)] + "്")):
            return value, True
    value = _number_word(word)
    return (value, False) if value else None


def _year_of(token: str) -> int | None:
    found = _YEAR.fullmatch(token.strip(".,"))
    if not found:
        return None
    return 2000 + int(found[1]) if found[1] else int(found[2])


def _calendar(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def place(month: int, day: int, year: int | None, today: date, direction: Direction):
    """A month and day, with or without a year, by direction and the overdue allowance."""
    if year is not None:
        return _calendar(year, month, day)
    this = _calendar(today.year, month, day)
    if direction == "past":
        if this is not None and this <= today:
            return this
        return _calendar(today.year - 1, month, day)
    if this is not None and (this >= today or (today - this).days <= OVERDUE_DAYS):
        return this
    for ahead in (1, 2, 3, 4):  # 29 February waits for its year
        if following := _calendar(today.year + ahead, month, day):
            return following
    return None


def day_of_month(number: int, today: date, direction: Direction) -> date | None:
    """A day of the month alone: the next one for a due, the last one for a payment."""
    month = today.replace(day=1)
    for _ in range(3):
        candidate = _calendar(month.year, month.month, number)
        if candidate and (candidate >= today if direction == "future" else candidate <= today):
            return candidate
        if direction == "future":
            month = (month + timedelta(days=32)).replace(day=1)
        else:
            month = (month - timedelta(days=1)).replace(day=1)
    return None


def _month_end(today: date, direction: Direction) -> date:
    first = today.replace(day=1)
    if direction == "past":
        return first - timedelta(days=1)
    return (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def _weekday(index: int, lead: str | None, today: date, direction: Direction) -> date:
    if direction == "future":
        ahead = (index - today.weekday()) % 7
        return today + timedelta(days=ahead or (7 if lead == "next" else 0))
    back = (today.weekday() - index) % 7
    return today - timedelta(days=back or (7 if lead == "last" else 0))


def _overlaps(span: Span, spans: list[Span]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in spans)


def _numeric(text: str, today: date, direction: Direction) -> list[_Found]:
    found: list[_Found] = []
    for match in _ISO.finditer(text):
        year, month, day = int(match[1]), int(match[2]), int(match[3])
        when = _calendar(year, month, day)
        found.append(_Found(match.span(), when, None if when else "invalid", month, year))
    for match in _NUMERIC.finditer(text):
        if _overlaps(match.span(), [item.span for item in found]):
            continue
        day, separator, month, year_text = int(match[1]), match[2], int(match[3]), match[4]
        if separator == "." and not year_text:
            continue  # "12.10" is also an amount; a dotted date needs its year
        if not (1 <= day <= 31 and 1 <= month <= 12):
            continue
        year = None if not year_text else int(year_text) + (2000 if len(year_text) == 2 else 0)
        when = place(month, day, year, today, direction)
        found.append(_Found(match.span(), when, None if when else "invalid", month, year))
    return found


def _named(text: str, today: date, direction: Direction) -> list[_Found]:
    """Month names with their day and year, then days said alone ("on the 5th", "10 तारीख")."""
    tokens = [(match[0], match.span()) for match in _TOKEN.finditer(text)]
    words = [word for word, _ in tokens]
    found: list[_Found] = []
    used: set[int] = set()
    for index, word in enumerate(words):
        named = month_of(word)
        if named is None:
            continue
        month, ambiguous = named
        parts, day, year = [index], None, None
        before = index - 1
        if before >= 1 and words[before] in {"of", "the"}:
            before -= 1
        if before >= 0 and (read := day_of(words[before], words=True)):
            day, parts = read[0], [before, index]
        after = index + 1
        if day is None:
            if after < len(words) and words[after] == "the":
                after += 1
            if after < len(words) and (read := day_of(words[after], words=True)):
                day, parts, after = read[0], [index, after], after + 1
            else:
                after = index + 1
        if after < len(words) and (year := _year_of(words[after])) is not None:
            parts.append(after)
        lead = words[index - 1] if index else ""
        if ambiguous and day is None and year is None and lead not in {"in", "next", "this"}:
            continue  # "may I", "jan dhan", "march on" are not dates
        span = (tokens[min(parts)][1][0], tokens[max(parts)][1][1])
        used.update(range(min(parts), max(parts) + 1))
        if day is None:
            found.append(_Found(span, None, "month_only", month, year))
            continue
        when = place(month, day, year, today, direction)
        found.append(_Found(span, when, None if when else "invalid", month, year))
    for index, word in enumerate(words):
        if index in used:
            continue
        following = words[index + 1] if index + 1 < len(words) else ""
        lead = words[index - 1] if index else ""
        on_the = lead == "the" and index > 1 and words[index - 2] in _LEADS
        context = following in DATE_WORDS or on_the or lead in _LEADS
        read = day_of(word, words=following in DATE_WORDS or on_the)
        if read is None or not (read[1] or following in DATE_WORDS or (context and word.isdigit())):
            continue
        end = tokens[index + 1][1][1] if following in DATE_WORDS else tokens[index][1][1]
        when = day_of_month(read[0], today, direction)
        found.append(_Found((tokens[index][1][0], end), when, None, alone=read[0]))
    return found


def _weekday_of(word: str) -> int | None:
    if word in _WEEKDAYS:
        return _WEEKDAYS[word]
    for name, index in _WEEKDAYS.items():
        if not name.isascii() and word.startswith(name):
            return index  # Malayalam endings: വെള്ളിയാഴ്ചയ്ക്ക്
    return None


def _relative(text: str, today: date, direction: Direction) -> list[_Found]:
    found: list[_Found] = []
    for pattern, shift in _RELATIVE[direction]:
        for match in pattern.finditer(text):
            if not _overlaps(match.span(), [item.span for item in found]):
                found.append(_Found(match.span(), today + timedelta(days=shift)))
    for match in _IN_DAYS[direction].finditer(text):
        count = int(next(group for group in match.groups() if group))
        found.append(
            _Found(match.span(), today + timedelta(days=count if direction == "future" else -count))
        )
    for match in _MONTH_END.finditer(text):
        found.append(_Found(match.span(), _month_end(today, direction)))
    for match in _VAGUE.finditer(text):
        found.append(_Found(match.span(), None, "ambiguous"))
    tokens = [(match[0], match.span()) for match in _TOKEN.finditer(text)]
    for index, (word, span) in enumerate(tokens):
        lead = tokens[index - 1][0] if index else None
        weekday = _weekday_of(word)
        if weekday is None and lead in _WEEKDAY_LEADS:
            weekday = _SHORT_WEEKDAYS.get(word)
        if weekday is not None:
            start = tokens[index - 1][1][0] if lead in _WEEKDAY_LEADS else span[0]
            found.append(_Found((start, span[1]), _weekday(weekday, lead, today, direction)))
    return found


def _in_month(found: list[_Found], text: str, today: date) -> list[_Found]:
    """ "next month 5th", "अगले महीने 5 तारीख": a day said alone moves into the month named."""
    match = _NEXT_MONTH.search(text)
    first = today.replace(day=1)
    target = (first + timedelta(days=32)).replace(day=1) if match else first
    match = match or _THIS_MONTH.search(text)
    if match is None:
        return found
    alone = [item for item in found if item.alone is not None]
    if not alone:
        return [*found, _Found(match.span(), None, "month_only", target.month, target.year)]
    moved = [item for item in found if item.alone is None]
    for item in alone:
        when = _calendar(target.year, target.month, item.alone or 0)
        span = (min(item.span[0], match.start()), max(item.span[1], match.end()))
        moved.append(_Found(span, when, None if when else "invalid", target.month, target.year))
    return moved


def read_date(text: str | None, today: date, direction: Direction) -> DateRead:
    """The one date a message says, by direction, or why it can't be used."""
    if not text:
        return DateRead()
    folded = fold(text)
    found = _numeric(folded, today, direction)
    found += _named(strip(folded, tuple(item.span for item in found)), today, direction)
    found += _relative(strip(folded, tuple(item.span for item in found)), today, direction)
    found = _in_month(found, folded, today)
    if not found:
        return DateRead()
    spans = tuple(sorted(item.span for item in found))
    dated = sorted((item for item in found if item.day is not None), key=lambda item: item.span)
    days = {item.day for item in dated}
    if len(days) > 1 and direction == "future":
        return DateRead(problem="ambiguous", spans=spans)
    if dated:
        day = dated[0].day
        assert day is not None
        low, high = (
            (today - timedelta(days=OVERDUE_DAYS), today + timedelta(days=FUTURE_DAYS))
            if direction == "future"
            else (today - timedelta(days=PAST_DAYS), today)
        )
        if not low <= day <= high:
            return DateRead(problem="out_of_range", spans=spans)
        return DateRead(day=day, spans=spans)
    problem = next(item for item in found if item.problem is not None or item.day is None)
    return DateRead(problem=problem.problem, month=problem.month, year=problem.year, spans=spans)
