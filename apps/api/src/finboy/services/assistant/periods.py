"""The period a question names, read by rules (docs/ask-round/contract.md).

Month names in English, Hindi and Malayalam (with or without a year), weeks, years, "last 3 months",
"April to June", "since April" and single days. A bare month is its most recent past occurrence.
Future dates are not records, and a question naming two periods is left to the assistant to compare.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from finboy.services.money.engine import PeriodSpec

MAX_DAYS = 731
Problem = Literal["future", "ambiguous", "too_long"]

ENGLISH: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "sept": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
# Words that are also everyday words ("may I", "march on", "Jan Dhan") count only in date context.
AMBIGUOUS = {"may", "march", "jan", "mar", "dec"}
NATIVE: dict[str, int] = {
    "जनवरी": 1,
    "फरवरी": 2,
    "फ़रवरी": 2,
    "मार्च": 3,
    "अप्रैल": 4,
    "मई": 5,
    "जून": 6,
    "जुलाई": 7,
    "अगस्त": 8,
    "सितंबर": 9,
    "सितम्बर": 9,
    "अक्टूबर": 10,
    "अक्तूबर": 10,
    "नवंबर": 11,
    "नवम्बर": 11,
    "दिसंबर": 12,
    "दिसम्बर": 12,
    "ജനുവരി": 1,
    "ഫെബ്രുവരി": 2,
    "മാർച്ച്": 3,
    "ഏപ്രിൽ": 4,
    "മേയ്": 5,
    "മെയ്": 5,
    "ജൂൺ": 6,
    "ജൂലൈ": 7,
    "ഓഗസ്റ്റ്": 8,
    "ആഗസ്റ്റ്": 8,
    "സെപ്റ്റംബർ": 9,
    "ഒക്ടോബർ": 10,
    "നവംബർ": 11,
    "ഡിസംബർ": 12,
}
CONTEXT = (
    r"(?:in|for|during|of|since|from|to|till|until|between|and|through|thru|last|this|on|"
    r"till|upto|up to|-|–)"
)
THIS_WEEK = ("this week", "इस हफ्ते", "इस हफ़्ते", "इस सप्ताह", "ഈ ആഴ്ച", "is hafte", "ee aazhcha")
LAST_WEEK = (
    "last week",
    "previous week",
    "पिछले हफ्ते",
    "पिछले हफ़्ते",
    "पिछले सप्ताह",
    "കഴിഞ്ഞ ആഴ്ച",
    "pichle hafte",
    "kazhinja aazhcha",
)
THIS_YEAR = ("this year", "इस साल", "इस वर्ष", "ഈ വർഷം", "is saal", "ee varsham")
LAST_YEAR = (
    "last year",
    "previous year",
    "पिछले साल",
    "पिछले वर्ष",
    "കഴിഞ്ഞ വർഷം",
    "pichle saal",
    "kazhinja varsham",
)
THIS_MONTH = ("this month", "current month", "इस महीने", "इस माह", "ഈ മാസം", "ee masam", "is mahine")
LAST_MONTH = (
    "last month",
    "previous month",
    "पिछले महीने",
    "पिछले माह",
    "കഴിഞ്ഞ മാസം",
    "kazhinja masam",
    "pichle mahine",
)
TODAY = ("today", "आज", "ഇന്ന്", "aaj", "innu")
YESTERDAY = ("yesterday", "बीते कल", "ഇന്നലെ", "innale")
_MONTH_NAMES = "|".join(sorted(ENGLISH, key=len, reverse=True))
_NATIVE_MONTH_NAMES = "|".join(sorted(NATIVE, key=len, reverse=True))
FUTURE = re.compile(
    rf"\b(?:tomorrow|next (?:week|month|year)|(?:next|coming|last|previous) (?:{_MONTH_NAMES}))\b|"
    rf"अगले (?:हफ्ते|महीने|साल|{_NATIVE_MONTH_NAMES})|"
    rf"पिछले (?:{_NATIVE_MONTH_NAMES})|നാളെ|अടുത്ത (?:ആഴ്ച|മാസം|വർഷം|{_NATIVE_MONTH_NAMES})|"
    rf"കഴിഞ്ഞ (?:{_NATIVE_MONTH_NAMES})"
)


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


# Malayalam inflects a month's last letter ("ഓഗസ്റ്റിൽ", "സെപ്റ്റംബറിൽ"): match the stem too, with a
# final virama dropped or a chillu written as its consonant.
CHILLU = {"ൻ": "ന", "ർ": "റ", "ൽ": "ല", "ൾ": "ള", "ൺ": "ണ"}


def _stems(name: str) -> tuple[str, ...]:
    if name.endswith("്"):
        return (name, name[:-1])
    if name[-1:] in CHILLU:
        return (name, name[:-1] + CHILLU[name[-1]])
    return (name,)


NATIVE_NORMALIZED = {
    stem: month for name, month in NATIVE.items() for stem in _stems(normalized(name))
}


@dataclass(frozen=True)
class PeriodRead:
    """The question's period, default, or unsupported-date reason."""

    period: PeriodSpec | None = None
    problem: Problem | None = None


@dataclass(frozen=True)
class _Month:
    start: int
    end: int
    month: int
    year: int | None
    day: int | None


def _shift(year: int, month: int, by: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + by
    return index // 12, index % 12 + 1


def _month_end(year: int, month: int) -> date:
    following = date(year + month // 12, month % 12 + 1, 1)
    return following - timedelta(days=1)


def _months(q: str) -> list[_Month]:
    found: list[_Month] = []
    names = "|".join(sorted(ENGLISH, key=len, reverse=True))
    for match in re.finditer(rf"\b({names})\b\.?", q):
        word = match.group(1)
        after = q[match.end() : match.end() + 12]
        before = q[max(0, match.start() - 12) : match.start()]
        year = re.match(r"\s*,?\s*'?(20\d{2})\b", after) or re.match(r"\s*'(\d{2})\b", after)
        day_after = re.match(r"\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!\s*(?:\d|,\s*\d{3}))", after)
        day_before = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?$", before)
        if word in AMBIGUOUS and not (
            year
            or day_before
            or re.search(rf"(?:^|\s){CONTEXT}\s+$", before)
            or re.match(r"\s+(?:month|mahine|masam)\b", after)
            or re.match(rf"\s*(?:to|till|until|through|-|–)\s*(?:{names})\b", q[match.end() :])
        ):
            continue
        found.append(
            _Month(
                match.start(), match.end(), ENGLISH[word], *_year_day(year, day_after, day_before)
            )
        )
    taken: set[int] = set()
    for name, month in sorted(NATIVE_NORMALIZED.items(), key=lambda item: -len(item[0])):
        for match in re.finditer(re.escape(name), q):
            if match.start() in taken:
                continue
            taken.add(match.start())
            after = q[match.end() : match.end() + 12]
            year = re.search(r"^\S*\s*,?\s*(20\d{2})\b", after)
            found.append(_Month(match.start(), match.end(), month, *_year_day(year, None, None)))
    return sorted(found, key=lambda item: item.start)


def _year_day(year, day_after, day_before) -> tuple[int | None, int | None]:
    value = None
    if year:
        value = int(year.group(1))
        value = value if value > 99 else 2000 + value
    day = day_before or (None if year and day_after is None else day_after)
    return value, int(day.group(1)) if day else None


def _resolved(item: _Month, today: date) -> tuple[int, int]:
    """The month's year: as written, else its most recent past occurrence."""
    if item.year is not None:
        return item.year, item.month
    return (today.year, item.month) if item.month <= today.month else (today.year - 1, item.month)


def _range(start: date, end: date, today: date) -> PeriodRead:
    if start > today:
        return PeriodRead(problem="future")
    end = min(end, today)
    if (end - start).days + 1 > MAX_DAYS:
        return PeriodRead(problem="too_long")
    if start.day == 1 and end == _month_end(start.year, start.month) and start.month == end.month:
        return PeriodRead(PeriodSpec(kind="month", year=start.year, month=start.month))
    return PeriodRead(PeriodSpec(kind="range", start_date=start, end_date=end))


def read_period(text: str, today: date) -> PeriodRead:
    """One period, or none (this month), or the reason the question's dates can't be used."""
    q = normalized(text)
    choices: list[PeriodRead] = []
    if FUTURE.search(q):
        return PeriodRead(problem="future")
    if re.search(r"(?<!\d)20\d{2}-(?:0?0|1[3-9]|[2-9]\d)(?![-\d])", q):
        return PeriodRead(problem="ambiguous")
    explicit = re.findall(r"(?<!\d)(20\d{2})-(0[1-9]|1[0-2])(?![-\d])", q)
    for year, month in explicit:
        first = date(int(year), int(month), 1)
        choices.append(
            PeriodRead(PeriodSpec())
            if (first.year, first.month) == (today.year, today.month)
            else _range(first, _month_end(first.year, first.month), today)
        )
    months = _months(q)
    if len(months) >= 2 and re.search(
        r"\b(?:to|till|until|upto|through|thru|and)\b|[-–]|से|तक|മുതൽ|വരെ",
        q[months[0].end : months[1].start],
    ):
        compare = re.search(r"\b(?:compare|vs|versus|against)\b|तुलना|താരതമ്യ", q)
        between = re.search(r"\bbetween\b", q[: months[0].start])
        joined = q[months[0].end : months[1].start].strip()
        if not compare and (joined not in {"and", "&"} or between):
            first, last = months[0], months[1]
            start_year, start_month = _resolved(first, today)
            end_year, end_month = _resolved(last, today)
            if last.year is None and first.year is not None:
                end_year = first.year if end_month >= start_month else first.year + 1
            elif first.year is None and (end_year, end_month) < (start_year, start_month):
                start_year -= 1
            choices.append(
                _range(date(start_year, start_month, 1), _month_end(end_year, end_month), today)
            )
            months = months[2:]
    for item in months:
        year, month = _resolved(item, today)
        if item.day is not None:
            return PeriodRead(problem="ambiguous")
        elif re.search(r"\b(?:since|from)\s+$|से\s*$", q[max(0, item.start - 8) : item.start]):
            choices.append(_range(date(year, month, 1), today, today))
        elif (year, month) == (today.year, today.month):
            choices.append(PeriodRead(PeriodSpec()))
        else:
            choices.append(_range(date(year, month, 1), _month_end(year, month), today))
    if spans := re.search(
        r"\b(?:last|past|previous)\s+(\d{1,3})\s+(months?|days?)\b|"
        r"(?:पिछले|बीते)\s+(\d{1,3})\s+(महीने|महीनों|दिन|दिनों)|"
        r"കഴിഞ്ഞ\s+(\d{1,3})\s+(മാസം|മാസങ്ങൾ|മാസത്തെ|ദിവസം|ദിവസങ്ങൾ)|"
        r"\b(?:pichle|kazhinja)\s+(\d{1,3})\s+(mahine|masam|din|divasam)\b",
        q,
    ):
        count = int(next(group for group in spans.groups()[0::2] if group))
        unit = next(group for group in spans.groups()[1::2] if group)
        if unit.startswith(("month", "महीन", "മാസ", "mahine", "masam")):
            year, month = _shift(today.year, today.month, -(count - 1))
            choices.append(_range(date(year, month, 1), today, today))
        else:
            choices.append(_range(today - timedelta(days=count - 1), today, today))
    contains = lambda terms: any(term in q for term in terms)  # noqa: E731
    if contains(YESTERDAY):
        day = today - timedelta(days=1)
        choices.append(_range(day, day, today))
    elif contains(TODAY):
        choices.append(_range(today, today, today))
    if contains(LAST_WEEK):
        monday = today - timedelta(days=today.weekday() + 7)
        choices.append(_range(monday, monday + timedelta(days=6), today))
    elif contains(THIS_WEEK):
        choices.append(_range(today - timedelta(days=today.weekday()), today, today))
    if contains(LAST_MONTH):
        year, month = _shift(today.year, today.month, -1)
        choices.append(_range(date(year, month, 1), _month_end(year, month), today))
    elif contains(THIS_MONTH):
        choices.append(PeriodRead(PeriodSpec()))
    if contains(LAST_YEAR):
        choices.append(_range(date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), today))
    elif contains(THIS_YEAR):
        choices.append(_range(date(today.year, 1, 1), today, today))
    elif (
        not explicit
        and not months
        and (
            year := re.search(
                r"\b(?:in|for|during|of|year)\s+(20\d{2})\b|\b(20\d{2})\s+(?:mein|il)\b", q
            )
        )
    ):
        value = int(year.group(1) or year.group(2))
        choices.append(_range(date(value, 1, 1), date(value, 12, 31), today))
    if not choices:
        return PeriodRead()
    problems = [choice for choice in choices if choice.problem]
    if problems:
        return problems[0]
    distinct = {choice.period.model_dump_json() for choice in choices if choice.period is not None}
    return PeriodRead(problem="ambiguous") if len(distinct) > 1 else choices[0]


def strip_dates(q: str) -> str:
    """The question without its dates, so "september 2026" or "last 3 months" is not an amount."""
    names = "|".join(sorted(ENGLISH, key=len, reverse=True))
    q = re.sub(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{names})\b", " ", q)
    q = re.sub(rf"\b(?:{names})\b\.?\s*,?\s*(?:'?\d{{2,4}}|\d{{1,2}}(?:st|nd|rd|th)?)?\b", " ", q)
    for name in NATIVE_NORMALIZED:
        q = re.sub(re.escape(name) + r"\s*,?\s*(?:20\d{2})?", " ", q)
    q = re.sub(r"\b(?:last|past|previous|pichle|kazhinja)\s+\d{1,3}\s+\w+", " ", q)
    q = re.sub(r"(?:पिछले|बीते|കഴിഞ്ഞ)\s+\d{1,3}\s+\S+", " ", q)
    q = re.sub(r"\b(?:in|for|during|of|year|since)\s+20\d{2}\b", " ", q)
    return re.sub(r"(?<!\d)20\d{2}-(?:0[1-9]|1[0-2])(?![-\d])", " ", q)


_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_LONG = (
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
)


def period_label(start: date, end: date) -> str:
    """ "September 2026", "1–14 Nov 2026", "1 Apr – 30 Sep 2026": dates as people say them."""
    if start == end:
        return f"{start.day} {_SHORT[start.month - 1]} {start.year}"
    whole = start.day == 1 and end == _month_end(end.year, end.month)
    if whole and (start.year, start.month) == (end.year, end.month):
        return f"{_LONG[start.month - 1]} {start.year}"
    if whole:
        if start.year == end.year:
            return f"{_SHORT[start.month - 1]} – {_SHORT[end.month - 1]} {end.year}"
        return f"{_SHORT[start.month - 1]} {start.year} – {_SHORT[end.month - 1]} {end.year}"
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{end.day} {_SHORT[end.month - 1]} {end.year}"
    if start.year == end.year:
        return (
            f"{start.day} {_SHORT[start.month - 1]} – {end.day} {_SHORT[end.month - 1]} {end.year}"
        )
    return (
        f"{start.day} {_SHORT[start.month - 1]} {start.year} – "
        f"{end.day} {_SHORT[end.month - 1]} {end.year}"
    )
