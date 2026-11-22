"""Typed answers to FinBoy's cards (docs/whatsapp.md, "Dates and card replies").

People type "yes", "galat" or just "5 january" instead of tapping a button. These are rules only,
with no model: a reply counts as an answer only when it says nothing else, so a new entry
("lunch 150") or a question ("any payment for jan") is never taken for one.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from finboy.services.ingestion import dates
from finboy.services.ingestion.hindi_numbers import only_amount

Kind = Literal["yes", "no", "cancel", "undo", "fix", "other"]

YES = frozenset(
    {"yes", "y", "yeah", "yea", "yep", "yup", "ya", "ok", "okay", "okk", "k", "kk", "correct"}
    | {"right", "sure", "done", "confirm", "confirmed", "fine", "perfect", "👍", "✅", "👌", "✔️"}
    | {"haan", "haa", "han", "ha", "hanji", "haanji", "theek", "thik", "sahi", "bilkul"}
    | {"हाँ", "हां", "हा", "जी", "सही", "ठीक", "बिल्कुल"}
    | {"ശരി", "അതെ", "ഉവ്വ്", "ഓക്കെ", "seri", "shari", "sheri", "athe", "uvvu"}
)
# Words that may sit around an answer without changing it ("haan sahi hai", "yes it is").
SOFT = frozenset(
    {"hai", "है", "ji", "जी", "bhai", "ആണ്", "aanu", "it", "is", "its", "it's", "that's", "thats"}
    | {
        "all",
        "good",
        "please",
        "pls",
        "plz",
        "thanks",
        "thank",
        "you",
        "👍🏻",
        "🙏",
        "save",
        "this",
    }
    | {"kar", "karo", "do", "kijiye", "कर", "करो", "दो", "कीजिए"}
)
NO = frozenset(
    {"no", "n", "nope", "nah", "wrong", "incorrect", "not", "galat", "ghalat", "nahi", "nahin"}
    | {"nai", "na", "गलत", "ग़लत", "नहीं", "नही", "ना", "തെറ്റ്", "അല്ല", "alla", "thettu", "👎", "❌"}
)
CANCEL = frozenset(
    {"cancel", "leave", "never", "mind", "skip", "drop", "dont", "don't", "forget"}
    | {"rehne", "rahne", "chhodo", "chodo", "रहने", "छोड़ो", "छोडो", "mat", "मत"}
    | {"വേണ്ട", "വേണ്ടാ", "venda", "മതി", "mathi"}
)
UNDO = frozenset(
    {"undo", "delete", "remove", "hatao", "hata", "हटाओ", "हटा", "मिटाओ"}
    | {"ഒഴിവാക്കൂ", "ഒഴിവാക്കുക", "നീക്കൂ"}
)
# Words that may come with a corrected amount or date: "no it's jan 1", "date is 5 jan",
# "galat hai, 1 jan", "300 rupees only".
FILLER = (
    frozenset(
        {"it", "it's", "its", "is", "was", "the", "date", "day", "on", "to", "change", "changed"}
        | {"make", "set", "should", "be", "actually", "sorry", "amount", "rs", "rupees", "rupee"}
        | {
            "inr",
            "for",
            "of",
            "in",
            "a",
            "an",
            "just",
            "only",
            "wait",
            "oh",
            "oops",
            "save",
            "this",
        }
        | {"that", "and", "but", "please", "pls", "plz", "hai", "tha", "thi", "ko", "kar", "karo"}
        | {"do", "de", "dijiye", "bhai", "ji", "wala", "wali", "rakam", "tarikh", "tareekh", "se"}
        | {"रकम", "है", "था", "थी", "को", "कर", "करो", "दो", "दीजिए", "वाला", "वाली", "तारीख", "से"}
        | {"ആണ്", "ആക്കൂ", "മാറ്റൂ", "തീയതി", "തുക", "രൂപ", "aanu", "akku", "mattu"}
    )
    | SOFT
    | NO
    | YES
)
_WORD = re.compile(r"[^\s,.!?;:()\"“”‘’।|]+")


@dataclass(frozen=True)
class Reply:
    """What a typed reply to a card means: an answer, a correction or something else."""

    kind: Kind
    amount_minor: int | None = None
    day: date | None = None
    month: int | None = None  # "january" alone: the card's day in that month


def words(text: str) -> list[str]:
    return [word.casefold() for word in _WORD.findall(dates.fold(text))]


def _only(found: list[str], kinds: frozenset[str]) -> bool:
    return (
        bool(found)
        and all(word in kinds | SOFT for word in found)
        and any(word in kinds for word in found)
    )


def read_reply(text: str, today: date, direction: dates.Direction) -> Reply:
    """A reply that is only yes, no, cancel, undo, or only a corrected amount and/or date."""
    found = words(text)
    if not found:
        return Reply("other")
    if _only(found, YES):
        return Reply("yes")
    if _only(found, UNDO):
        return Reply("undo")
    if _only(found, CANCEL | NO) and any(word in CANCEL for word in found):
        return Reply("cancel")
    if _only(found, NO):
        return Reply("no")
    if len(found) == 1 and (named := dates.month_of(found[0])) is not None:
        return Reply("fix", month=named[0])
    said = dates.read_date(text, today, direction)
    rest = [word for word in words(dates.strip(text, said.spans)) if word not in FILLER]
    amount = only_amount(" ".join(rest)) if rest else None
    if rest and amount is None:
        return Reply("other")
    month = said.month if said.problem == "month_only" else None
    if said.day is None and month is None and amount is None:
        return Reply("other")
    if said.said and said.day is None and month is None:
        return Reply("other")  # an impossible or unclear date: let the diary say so
    return Reply("fix", amount, said.day, month)
