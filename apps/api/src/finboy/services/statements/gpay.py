"""Read a Google Pay transaction statement (PDF) into exact rows.

Untrusted input, read in memory and never stored (docs/statement-round/contract.md). PDFium gives
each word with its position; rows are rebuilt from the table's three columns using the header's
x-positions, so amounts and names that wrap onto a second line join correctly and the page footer
is never read as a row. The caller checks the rows against the statement's own Sent and Received
totals before anything is saved. The phone number printed on the statement is returned only so
the caller can compare a keyed digest; it is never stored or logged.
"""

import json
import re
import subprocess
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, get_args
from zoneinfo import ZoneInfo

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

# Statements print Indian time. Kept local so the parsing process imports nothing else of FinBoy.
IST = ZoneInfo("Asia/Kolkata")

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 600
MAX_ROWS = 5000
PARSE_SECONDS = 30

Problem = Literal["not_gpay_statement", "statement_locked", "statement_unreadable", "upload_limit"]
Direction = Literal["out", "in", "other"]

AMOUNT = re.compile(r"^₹(\d[\d,]*(?:\.\d{1,2})?)$")
DATE_START = re.compile(r"^\d{1,2}\s*[A-Z][a-z]{2},?$")
WHEN = re.compile(r"^(\d{1,2})\s*([A-Z][a-z]{2}),?\s*(\d{4})\s*(\d{1,2}):(\d{2})\s*([AP]M)$")
PERIOD = re.compile(r"(\d{1,2} [A-Z][a-z]+ \d{4})\s*-\s*(\d{1,2} [A-Z][a-z]+ \d{4})")
REFERENCE = re.compile(r"^UPI Transaction ID:?\s*([A-Za-z0-9]{6,35})$")
ACCOUNT = re.compile(r"^Paid (?:by|to)\s+(.+?)(?:\s+(\d{4}))?$")
PAGE = re.compile(r"\bPage\s+(\d+)\s+of\s+(\d+)\b")
PHONE = re.compile(r"^(\d{10}),?$")
# Same visual line: words on one line differ by about a point; lines are 11 points or more apart.
LINE = 4.0


class StatementError(Exception):
    """A fixed code; PDF and library details never cross this boundary."""

    def __init__(self, code: Problem) -> None:
        self.code: Problem = code
        super().__init__(code)


@dataclass(frozen=True)
class Row:
    page: int
    position: int
    occurred_at: datetime
    direction: Direction
    name: str
    detail: str
    upi_id: str
    bank: str
    last4: str | None
    amount_minor: int


@dataclass(frozen=True)
class Statement:
    period_start: date
    period_end: date
    sent_minor: int
    received_minor: int
    pages: int
    rows: tuple[Row, ...]
    # In memory only: compared as a keyed digest with the household's WhatsApp number.
    phone: str | None

    @property
    def paid_minor(self) -> int:
        return sum(row.amount_minor for row in self.rows if row.direction == "out")

    @property
    def got_minor(self) -> int:
        return sum(row.amount_minor for row in self.rows if row.direction == "in")

    @property
    def reconciled(self) -> bool:
        """Google leaves self transfers out of its totals; every other row must add up exactly."""
        return self.paid_minor == self.sent_minor and self.got_minor == self.received_minor

    @property
    def accounts(self) -> tuple[str, ...]:
        return tuple(sorted({account_label(row.bank, row.last4) for row in self.rows}))


def account_label(bank: str, last4: str | None) -> str:
    return f"{bank} ••{last4}" if last4 else bank


@dataclass(frozen=True)
class _Word:
    text: str
    left: float
    right: float
    top: float
    bottom: float


@dataclass(frozen=True)
class _Layout:
    details_left: float
    amount_left: float
    table_top: float
    footer_top: float


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _words(page: pdfium.PdfPage) -> list[_Word]:
    textpage = page.get_textpage()
    try:
        words = []
        for index in range(textpage.count_rects()):
            left, bottom, right, top = textpage.get_rect(index)
            text = textpage.get_text_bounded(left, bottom, right, top)
            if text.strip():
                words.append(_Word(text, left, right, top, bottom))
        return words
    finally:
        textpage.close()


@dataclass(frozen=True)
class _Line:
    top: float
    text: str


def _grouped(words: Sequence[_Word]) -> list[_Line]:
    """Group words into visual lines, top to bottom, keeping the spaces PDFium found.

    A word joins a line when its vertical middle falls inside the line's band: short glyphs such
    as "-" sit lower than their neighbours, so comparing top edges alone would split the line.
    """
    lines: list[list[_Word]] = []
    for word in sorted(words, key=lambda item: -item.top):
        middle = (word.top + word.bottom) / 2
        if lines and min(w.bottom for w in lines[-1]) <= middle <= max(w.top for w in lines[-1]):
            lines[-1].append(word)
        else:
            lines.append([word])
    grouped = []
    for line in lines:
        text, previous = "", None
        for word in sorted(line, key=lambda item: item.left):
            gap = word.left - previous.right if previous else 0
            if text and not text[-1].isspace() and not word.text[0].isspace() and gap > 1.0:
                text += " "
            text += word.text
            previous = word
        if clean := _clean(text):
            grouped.append(_Line(max(word.top for word in line), clean))
    return grouped


def _lines(words: Sequence[_Word]) -> list[str]:
    return [line.text for line in _grouped(words)]


def _find(words: Sequence[_Word], test: Callable[[_Word], bool]) -> _Word | None:
    return next((word for word in words if test(word)), None)


def _layout(words: Sequence[_Word], *, page: int, pages: int) -> _Layout:
    # PDFium may give a header as single words ("Date ", "&") or as runs ("Date &").
    label = _find(words, lambda word: word.text.strip().startswith("Date") and word.left < 80)
    amount = label and _find(
        words, lambda word: word.text.strip().startswith("Amoun") and abs(word.top - label.top) < 4
    )
    details = label and _find(
        words,
        lambda word: (
            word.text.strip().startswith("Transaction")
            and label.top - 14 < word.top <= label.top + 2
            and word.left > label.right
        ),
    )
    note = _find(words, lambda word: word.text.startswith("Note:") and word.left < 80)
    if not (label and amount and details and note):
        raise StatementError("not_gpay_statement")
    footer_top = note.top + 3
    footer = " ".join(_lines([word for word in words if word.top <= footer_top]))
    numbering = PAGE.search(footer)
    if "Google Pay" not in footer or numbering is None:
        raise StatementError("not_gpay_statement")
    if (int(numbering.group(1)), int(numbering.group(2))) != (page, pages):
        raise StatementError("statement_unreadable")
    header = [word for word in words if word.top >= label.top - 14 and word.top <= label.top + 2]
    return _Layout(
        details_left=details.left,
        amount_left=amount.left,
        table_top=min(word.bottom for word in header) - 0.5,
        footer_top=footer_top,
    )


def _money(text: str) -> int | None:
    match = AMOUNT.match(text.replace(" ", ""))
    if match is None:
        return None
    try:
        value = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    minor = value * 100
    return int(minor) if minor == minor.to_integral_value() and minor >= 0 else None


def _header(words: Sequence[_Word], layout: _Layout) -> tuple[date, date, int, int, str | None]:
    top = [word for word in words if word.top > layout.table_top]
    text = " ".join(_lines(top))
    period = PERIOD.search(text)
    if "Transaction statement" not in text or period is None:
        raise StatementError("not_gpay_statement")
    try:
        start, end = (datetime.strptime(item, "%d %B %Y").date() for item in period.groups())
    except ValueError:
        raise StatementError("not_gpay_statement") from None

    def total(name: str) -> int:
        label = _find(top, lambda word: word.text.strip() == name)
        if label is None:
            raise StatementError("not_gpay_statement")
        centre = (label.left + label.right) / 2
        below = [
            word
            for word in top
            if word.text.startswith("₹") and label.top - 40 < word.top < label.top - 2
        ]
        if not below:
            raise StatementError("not_gpay_statement")
        nearest = min(below, key=lambda word: abs((word.left + word.right) / 2 - centre))
        value = _money(nearest.text.strip())
        if value is None:
            raise StatementError("statement_unreadable")
        return value

    phone = next((m.group(1) for word in top if (m := PHONE.match(word.text.strip()))), None)
    if start > end:
        raise StatementError("not_gpay_statement")
    return start, end, total("Sent"), total("Received"), phone


def _row(page: int, position: int, dates: list[str], details: list[str], amount: str) -> Row:
    when = WHEN.match(" ".join(dates))
    reference_at = next((i for i, line in enumerate(details) if REFERENCE.match(line)), None)
    if when is None or reference_at is None or reference_at == 0:
        raise StatementError("statement_unreadable")
    detail = _clean(" ".join(details[:reference_at]))
    account = ACCOUNT.match(_clean(" ".join(details[reference_at + 1 :])))
    minor = _money(amount)
    reference = REFERENCE.match(details[reference_at])
    if account is None or minor is None or minor == 0 or reference is None:
        raise StatementError("statement_unreadable")
    day, month, year, hour, minute, half = when.groups()
    try:
        occurred_at = datetime.strptime(
            f"{day} {month} {year} {hour}:{minute} {half}", "%d %b %Y %I:%M %p"
        ).replace(tzinfo=IST)
    except ValueError:
        raise StatementError("statement_unreadable") from None
    direction: Direction = "other"
    name = detail
    for prefix, value in (("Paid to ", "out"), ("Received from ", "in")):
        if detail.startswith(prefix) and len(detail) > len(prefix):
            direction, name = value, detail[len(prefix) :]  # type: ignore[assignment]
    return Row(
        page=page,
        position=position,
        occurred_at=occurred_at,
        direction=direction,
        name=name,
        detail=detail,
        upi_id=reference.group(1),
        bank=account.group(1),
        last4=account.group(2),
        amount_minor=minor,
    )


def _rows(words: Sequence[_Word], layout: _Layout, *, page: int) -> list[Row]:
    table = [word for word in words if layout.footer_top < word.top < layout.table_top]
    columns: tuple[list[_Word], list[_Word], list[_Word]] = ([], [], [])
    for word in table:
        if word.left < layout.details_left - 10:
            columns[0].append(word)
        elif word.left >= layout.amount_left - 20:
            columns[2].append(word)
        else:
            columns[1].append(word)
    # A row starts where a date ("01 Apr,") opens a line in the first column; every word below
    # it, in any column, belongs to that row until the next date.
    starts = [line.top for line in _grouped(columns[0]) if DATE_START.match(line.text)]
    blocks: list[tuple[list[_Word], list[_Word], list[_Word]]] = [([], [], []) for _ in starts]
    for index, column in enumerate(columns):
        for word in column:
            owners = [i for i, top in enumerate(starts) if top >= word.top - LINE]
            if not owners:
                raise StatementError("statement_unreadable")
            blocks[owners[-1]][index].append(word)
    rows = []
    for position, (dates, details, amounts) in enumerate(blocks, start=1):
        # A narrow column wraps long amounts: "₹12,50" then "0".
        amount = "".join(_lines(amounts)).replace(" ", "")
        rows.append(_row(page, position, _lines(dates), _lines(details), amount))
    return rows


def parse_statement(data: bytes) -> Statement:
    if not data or len(data) > MAX_BYTES:
        raise StatementError("upload_limit")
    if not data.startswith(b"%PDF-"):
        raise StatementError("not_gpay_statement")
    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        locked = getattr(exc, "err_code", None) == pdfium_c.FPDF_ERR_PASSWORD
        raise StatementError("statement_locked" if locked else "not_gpay_statement") from None
    try:
        pages = len(document)
        if pages == 0:
            raise StatementError("not_gpay_statement")
        if pages > MAX_PAGES:
            raise StatementError("upload_limit")
        rows: list[Row] = []
        header = None
        for index in range(pages):
            page = document[index]
            try:
                words = _words(page)
            finally:
                page.close()
            layout = _layout(words, page=index + 1, pages=pages)
            if index == 0:
                header = _header(words, layout)
            rows.extend(_rows(words, layout, page=index + 1))
            if len(rows) > MAX_ROWS:
                raise StatementError("upload_limit")
    finally:
        document.close()
    if header is None:
        raise StatementError("not_gpay_statement")
    start, end, sent, received, phone = header
    if any(not start <= row.occurred_at.date() <= end for row in rows):
        raise StatementError("statement_unreadable")
    return Statement(
        period_start=start,
        period_end=end,
        sent_minor=sent,
        received_minor=received,
        pages=pages,
        rows=tuple(rows),
        phone=phone,
    )


def _limit_resources() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (PARSE_SECONDS, PARSE_SECONDS + 5))
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    except ImportError, ValueError, OSError:
        pass


def _encode(statement: Statement) -> dict[str, object]:
    return {
        "period_start": statement.period_start.isoformat(),
        "period_end": statement.period_end.isoformat(),
        "sent_minor": statement.sent_minor,
        "received_minor": statement.received_minor,
        "pages": statement.pages,
        "phone": statement.phone,
        "rows": [
            {**row.__dict__, "occurred_at": row.occurred_at.isoformat()} for row in statement.rows
        ],
    }


def _decode(value: dict[str, object]) -> Statement:
    rows = value["rows"]
    assert isinstance(rows, list)
    return Statement(
        period_start=date.fromisoformat(str(value["period_start"])),
        period_end=date.fromisoformat(str(value["period_end"])),
        sent_minor=int(str(value["sent_minor"])),
        received_minor=int(str(value["received_minor"])),
        pages=int(str(value["pages"])),
        rows=tuple(
            Row(**{**row, "occurred_at": datetime.fromisoformat(row["occurred_at"])})
            for row in rows
        ),
        phone=str(value["phone"]) if value["phone"] is not None else None,
    )


def main() -> None:
    """`python -I -m finboy.services.statements.gpay`: a PDF on stdin, JSON on stdout."""
    _limit_resources()
    try:
        result: dict[str, object] = {"ok": _encode(parse_statement(sys.stdin.buffer.read()))}
    except StatementError as exc:
        result = {"error": exc.code}
    except Exception:
        # Library messages may quote PDF content; only a fixed code crosses back.
        result = {"error": "statement_unreadable"}
    sys.stdout.write(json.dumps(result))


def read_statement(data: bytes, *, seconds: float = PARSE_SECONDS) -> Statement:
    """Parse in a fresh, short-lived Python process with an empty environment.

    A hostile PDF can't hang or crash the API, and the parser never sees the API's secrets.
    """
    if not data or len(data) > MAX_BYTES:
        raise StatementError("upload_limit")
    try:
        done = subprocess.run(
            [sys.executable, "-I", "-m", __name__],
            input=data,
            capture_output=True,
            timeout=seconds,
            env={},
            check=False,
        )
        result = json.loads(done.stdout)
    except subprocess.TimeoutExpired, OSError, ValueError:
        raise StatementError("statement_unreadable") from None
    if isinstance(result, dict) and isinstance(result.get("ok"), dict):
        try:
            return _decode(result["ok"])
        except KeyError, TypeError, ValueError, AssertionError:
            raise StatementError("statement_unreadable") from None
    code = result.get("error") if isinstance(result, dict) else None
    raise StatementError(code if code in get_args(Problem) else "statement_unreadable")


if __name__ == "__main__":
    main()
